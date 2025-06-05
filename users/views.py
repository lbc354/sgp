from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.db import transaction, IntegrityError
from django.contrib.auth import login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse
from utils.pagination import make_pagination
from users.models import PasswordResetToken
from users.forms import (
    CustomAuthenticationForm,
    CustomUserCreationForm,
    CustomUserChangeForm,
    CustomPasswordChangeForm,
)
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import pyotp
import qrcode
import io
import base64
import logging


logger = logging.getLogger(__name__)
signer = TimestampSigner()


# home page
@login_required
def home(request):
    return render(request, "global/home.html")


# log out user
def logout_action(request):
    logout(request)
    messages.success(request, "Usuário saiu")
    return redirect("login")


# login page and login action
def login_action(request):
    form_mfa_action = reverse("mfa")
    next_url = resolve_url(request.GET.get("next", reverse("home")))
    # if user is authenticated, redirect to home
    if request.user and request.user.is_authenticated:
        return redirect("home")

    # if POST method
    if request.method == "POST":
        form = CustomAuthenticationForm(data=request.POST)

        if form.is_valid():
            # get the user
            user = form.get_user()

            # if user is NOT active, don't allow to log in
            if not user.is_active:
                messages.warning(request, "Usuário desativado")
                return redirect("login")

            # if user has no mfa enabled and no mfa secret (e.g., it's their first login), generate a secret key for them
            if not user.mfa_secret:
                # each user needs an unique mfa secret to generate authentication codes. if mfa_secret doesn't already exist in database, it is generated with pyotp.random_base32(), assigned to the user and saved. this secret is required to generate authentication tokens that change every 30 seconds.
                user.mfa_secret = pyotp.random_base32()
                user.save()

            # if user has mfa enabled, ask for the code
            if user.mfa_enabled:
                return render(
                    request,
                    "users/mfa.html",
                    {
                        "user_id": user.id,
                        "form_mfa_action": form_mfa_action,
                        "next_url": next_url,
                    },
                )

            # log user in
            login(request, user)
            messages.success(request, "Usuário entrou")

            # redirect after login
            return (
                redirect("reset_password")
                if verify_default_password(request)
                else redirect(next_url)
            )

        # if wrong data
        else:
            messages.error(request, "Usuário ou senha incorretos, tente novamente")
            return render(
                request,
                "users/login.html",
                {
                    "form": form,
                },
            )

    # if GET method
    else:
        form = CustomAuthenticationForm()

    return render(
        request,
        "users/login.html",
        {
            "form": form,
        },
    )


def verify_default_password(request):
    # user has to be logged in
    if (
        request.user
        and request.user.is_authenticated
        and request.POST.get("password") == settings.DEFAULT_USER_PASSWORD
    ):
        messages.warning(
            request,
            "Você está usando uma senha padrão e insegura, mude-a",
        )
        return True
    return False


def verify_mfa_otp(user, otp):
    # create a totp object using the user's mfa secret
    totp = pyotp.TOTP(user.mfa_secret)

    # verify the provided otp
    if totp.verify(otp):
        # if otp is valid, enable mfa and return true
        user.mfa_enabled = True
        user.save()
        return True

    # if otp is invalid, return false
    return False


# activate on profile page or verify during login
def mfa(request):
    # get the values ​​of the hidden inputs
    user_id = request.POST.get("user_id")
    next_url = request.POST.get("next_url")
    # next_url = resolve_url(request.GET.get("next", reverse("home")))

    # if id is not found
    if not user_id:
        messages.error(request, "Ocorreu um erro, tente novamente")
        return redirect("login")

    # if POST method
    if request.method == "POST":
        # get the otp code
        otp = request.POST.get("otp_code")

        # get user by id
        user = get_user_model().objects.get(id=user_id)

        # if true
        if verify_mfa_otp(user, otp):
            # user in profile page activating mfa
            if request.user and request.user.is_authenticated:
                messages.success(request, "MFA ativado")
                return redirect("profile")

            # user in mfa page authenticating
            login(request, user)
            messages.success(request, "Usuário entrou")

            return (
                redirect("reset_password")
                if verify_default_password(request)
                else redirect(next_url)
            )

        # if false
        else:
            messages.error(request, "Código inválido, tente novamente")

            # user in profile page failed activating mfa
            if request.user and request.user.is_authenticated:
                return redirect("profile")

            # user in mfa page failed authenticating
            return render(
                request,
                "users/mfa.html",
                {
                    "user_id": user_id,
                    "next_url": next_url,
                },
            )

    # if GET method
    return redirect("login")


# profile page
@login_required
def profile(request):
    user = request.user

    # if user doesn't have mfa enabled, alert them
    if not user.mfa_enabled:
        messages.warning(request, "Ative Autenticação de Dois Fatores")

    # pyotp.totp.TOTP(user.mfa_secret) -> creates a totp generator based on the user's secret
    # provisioning_uri(...) -> generates an uri in otpauth://totp/... format that can be scanned by apps like google authenticator
    # name=user.email -> shows user's email in authenticator app.
    # issuer_name="app_name" -> shows application's name in authenticator app
    otp_uri = pyotp.totp.TOTP(user.mfa_secret).provisioning_uri(
        name=user.email, issuer_name="sgp_app"
    )

    # generates a qr code from "otpauth://totp/..." uri
    qr = qrcode.make(otp_uri)

    # converting the qr code to a base64 string so it can be displayed in html without saving it as a file:

    # creates a buffer in memory to store the qr code image
    buffer = io.BytesIO()
    # saves the qr code to the buffer in png format
    qr.save(buffer, format="PNG")
    # moves the cursor to the beginning of the buffer for reading
    buffer.seek(0)
    # buffer.getvalue() -> gets image bytes
    # base64.b64encode(...).decode("utf-8") -> converts the bytes to a base64 encoded string
    qr_code = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # generates a data uri that allows the qr code to be displayed in html without needing to save as a file
    qr_code_data_uri = f"data:image/png;base64,{qr_code}"
    # passes the base64-encoded image of the qr code to the template in the 'qrcode' variable
    return render(request, "users/profile.html", {"qrcode": qr_code_data_uri})


# edit page and edit action
@login_required
def edit(request, user_id=None):
    # example of how we can control paths in the front-end by the back-end
    return_page_action = reverse("active_users") if user_id else reverse("profile")

    # if there is id in url, try to get user
    if user_id:
        try:
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            messages.error(request, "Usuário não encontrado")
            return redirect("active_users")
    # if no id in url, the instance gonna be the authenticated user
    else:
        user = request.user

    # if an user without permissions (we still have to check the permissions) is trying to access the edit page of an user other than himself, do not allow
    if request.user and request.user.id != user.id and not request.user.is_superuser:
        messages.error(request, "Sem permissões")
        return redirect("profile")

    if request.method == "POST":
        form = CustomUserChangeForm(request.POST, instance=user, request=request)
        if form.is_valid():
            try:
                # transactional context example
                with transaction.atomic():
                    form.save()
                    messages.success(request, "Usuário editado")
                return redirect("active_users") if user_id else redirect("profile")
            except IntegrityError as ie:
                messages.error(request, "Erro transacional, tente novamente")
                logger.error("Erro transacional: ", str(ie))
            except Exception as e:
                messages.error(request, "Ocorreu um erro, tente novamente")
                logger.error("Erro genérico: ", str(e))

    else:
        form = CustomUserChangeForm(instance=user, request=request)

    return render(
        request,
        "users/edit.html",
        {
            "form": form,
            "user": user,
            "return_page_action": return_page_action,
        },
    )


# register page and register action
@login_required
def register(request):
    # example of how we can control paths in the front-end by the back-end
    return_page_action = reverse("active_users")

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            try:
                # transactional context example
                with transaction.atomic():
                    # user = form.save(commit=False)
                    # user.save()
                    # form.save_m2m()
                    form.save()
                    messages.success(request, "Usuário cadastrado")
                return redirect("register")
            except IntegrityError as ie:
                messages.error(request, "Erro transacional, tente novamente")
                logger.error("Erro transacional: ", str(ie))
            except Exception as e:
                messages.error(request, "Ocorreu um erro, tente novamente")
                logger.error("Erro genérico: ", str(e))

    else:
        form = CustomUserCreationForm()

    return render(
        request,
        "users/register.html",
        {"form": form, "return_page_action": return_page_action},
    )


# active users list
@login_required
def active_users(request):
    # get query from url (.../?q=str)
    query = request.GET.get("q", "").strip().lower()

    # list
    users_data = []
    # queryset
    users = (
        get_user_model()
        .objects.filter(is_superuser=False, is_staff=False, is_active=True)
        .order_by("-updated_at", "-date_joined")
    )

    # add each element in the queryset to the list
    for user in users:
        # use timezone.localtime to put the time registered in the database in the correct time zone
        users_data.append(
            {
                "user": user,
                "last_login": (
                    timezone.localtime(user.last_login).strftime("%d/%m/%Y %H:%M")
                    if user.last_login
                    else "---------"
                ),
                "date_joined": (
                    timezone.localtime(user.date_joined).strftime("%d/%m/%Y %H:%M")
                    if user.date_joined
                    else "---------"
                ),
                "updated_at": (
                    timezone.localtime(user.updated_at).strftime("%d/%m/%Y %H:%M")
                    if user.updated_at
                    else "---------"
                ),
            }
        )

    # filters data based on search
    if query:
        users_data = [
            data
            for data in users_data
            if any(query in str(data[key]).lower() for key in data)
        ]

    # pagination
    page_obj, pagination_range = make_pagination(request, users_data, settings.PER_PAGE)

    return render(
        request,
        "users/users_list.html",
        {
            "page_obj": page_obj,
            "pagination_range": pagination_range,
        },
    )


# deactivated users list
@login_required
def deactivated_users(request):
    # get query from url (.../?q=str)
    query = request.GET.get("q", "").strip().lower()

    # list
    users_data = []
    # queryset
    users = (
        get_user_model()
        .objects.filter(is_superuser=False, is_staff=False, is_active=False)
        .order_by("-updated_at", "-date_joined")
    )

    # add each element in the queryset to the list
    for user in users:
        # use timezone.localtime to put the time registered in the database in the correct time zone
        users_data.append(
            {
                "user": user,
                "last_login": (
                    timezone.localtime(user.last_login).strftime("%d/%m/%Y %H:%M")
                    if user.last_login
                    else "---------"
                ),
                "date_joined": (
                    timezone.localtime(user.date_joined).strftime("%d/%m/%Y %H:%M")
                    if user.date_joined
                    else "---------"
                ),
                "updated_at": (
                    timezone.localtime(user.updated_at).strftime("%d/%m/%Y %H:%M")
                    if user.updated_at
                    else "---------"
                ),
            }
        )

    # filters data based on search
    if query:
        users_data = [
            data
            for data in users_data
            if any(query in str(data[key]).lower() for key in data)
        ]

    # pagination
    page_obj, pagination_range = make_pagination(request, users_data, settings.PER_PAGE)

    return render(
        request,
        "users/users_list.html",
        {
            "page_obj": page_obj,
            "pagination_range": pagination_range,
            "inactive": "inactive",
        },
    )


# activate deactivated user
@login_required
def activate_user(request, user_id):
    # try to get user
    try:
        user = get_user_model().objects.get(id=user_id)
    except get_user_model().DoesNotExist:
        messages.error(request, "Usuário não encontrado")
        return redirect("deactivated_users")

    # activate user
    if not user.is_active:
        user.is_active = True
        user.save()
        messages.success(request, "Usuário ativado")
    else:
        messages.info(request, "Usuário já está ativado")

    return redirect("deactivated_users")


# deactivate active user
@login_required
def deactivate_user(request, user_id):
    # try to get user
    try:
        user = get_user_model().objects.get(id=user_id)
    except get_user_model().DoesNotExist:
        messages.error(request, "Usuário não encontrado")
        return redirect("active_users")

    # deactivate user
    if user.is_active:
        user.is_active = False
        user.save()
        messages.success(request, "Usuário desativado")
    else:
        messages.info(request, "Usuário já está desativado")

    return redirect("active_users")


# disable user's mfa
@login_required
def disable_mfa(request, user_id):
    # try to get user
    try:
        user = get_user_model().objects.get(id=user_id)
    except get_user_model().DoesNotExist:
        messages.error(request, "Usuário não encontrado")
        return redirect("active_users")

    # disable mfa
    if user.mfa_enabled:
        user.mfa_enabled = False
        user.save()
        messages.success(request, "MFA desabilitado")
    else:
        messages.info(request, "MFA já está desabilitado")

    return redirect("active_users")


# reset user's password (default password)
@login_required
def reset_user_password(request, user_id):
    # try to get user
    try:
        user = get_user_model().objects.get(id=user_id)
    except get_user_model().DoesNotExist:
        messages.error(request, "Usuário não encontrado")
        return redirect("active_users")

    # reset password
    user.set_password(settings.DEFAULT_USER_PASSWORD)
    user.save()
    messages.success(request, "Senha redefinida")

    return redirect("active_users")


# reset own password via form
@login_required
def reset_password(request):
    # example of how we can control paths in the front-end by the back-end
    return_page_action = reverse("edit")

    if request.method == "POST":
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            try:
                # transactional context example
                with transaction.atomic():
                    user = form.save()
                    # keeps user logged in after changes
                    update_session_auth_hash(request, user)
                    messages.success(request, "Senha atualizada")
                return redirect("profile")
            except IntegrityError as ie:
                messages.error(request, "Erro transacional, tente novamente")
                logger.error("Erro transacional: ", str(ie))
            except Exception as e:
                messages.error(request, "Ocorreu um erro, tente novamente")
                logger.error("Erro genérico: ", str(e))
    else:
        form = CustomPasswordChangeForm(user=request.user)

    return render(
        request,
        "users/reset_password.html",
        {"form": form, "return_page_action": return_page_action},
    )


# request own password reset via email
def request_password_reset(request):
    if request.method == "POST":
        # try to get user
        try:
            email = request.POST.get("email")
            user = get_user_model().objects.get(email=email)
        except get_user_model().DoesNotExist:
            messages.error(request, "E-mail não encontrado")
            return render(request, "users/request_password_reset.html")

        # create unique token for password reset
        token = signer.sign(user.id)
        PasswordResetToken.objects.create(user=user, token=token)

        # builds password reset URL
        current_site = get_current_site(request)
        reset_url = (
            f"http://{current_site.domain}{reverse('password_reset', args=[token])}"
        )

        email_message = f"""
        <html>
            <body>
                <p>Olá, {user}!</p>
                <p>Você solicitou a redefinição de senha. Para continuar, clique no link abaixo:</p>
                <p><a href="{reset_url}" target="_blank">Redefinir Senha</a></p>
                <strong>Se não foi você, ignore este e-mail.</strong>
            </body>
        </html>
        """

        sender = "svc.sgp@dnit.gov.br"
        recipient = email
        subject = "Redefinição de Senha"

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(email_message, "html"))

        try:
            server = smtplib.SMTP("10.100.10.45")
            server.sendmail(sender, recipient, msg.as_string())
            server.quit()
            messages.success(request, "E-mail de redefinição enviado")
        except Exception as e:
            logger.error(
                f"REQUEST_PASSWORD_RESET | Erro ao enviar email para {recipient}: {str(e)}"
            )
            messages.error(request, f"Erro ao enviar email para {recipient}")

        return redirect("request_password_reset")

    return render(request, "users/request_password_reset.html")


# reset own password via email
def password_reset(request, token):
    try:
        # check and decode token
        user_id = signer.unsign(
            token, max_age=3600
        )  # token expires in 1 hour (3600 seconds)

        # try to get user
        try:
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            messages.error(request, "Usuário não encontrado, tente novamente")
            return redirect("request_password_reset")
    # if the token is changed (invalid signature) or is expired (more than 1 hour), an error will be thrown
    except (BadSignature, SignatureExpired):
        messages.error(request, "Token inválido ou expirado, tente novamente")
        return redirect("request_password_reset")

    if request.method == "POST":
        try:
            # transactional context example
            with transaction.atomic():
                # save new password
                new_password = request.POST.get("password")
                user.set_password(new_password)
                user.save()
                # remove token from database
                PasswordResetToken.objects.filter(user=user, token=token).delete()
                messages.success(request, "Senha atualizada")
            return redirect("login")
        except IntegrityError as ie:
            messages.error(request, "Erro transacional, tente novamente")
            logger.error("Erro transacional: ", str(ie))
        except Exception as e:
            messages.error(request, "Ocorreu um erro, tente novamente")
            logger.error("Erro genérico: ", str(e))

    return render(request, "users/password_reset.html", {"token": token})
