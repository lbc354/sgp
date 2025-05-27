from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse
from users.forms import (
    CustomAuthenticationForm,
    CustomUserChangeForm,
    CustomPasswordChangeForm,
)
import pyotp
import qrcode
import io
import base64


@login_required
def home(request):
    return render(request, "global/home.html")


def logout_action(request):
    logout(request)
    messages.info(request, "User logged out")
    return redirect("login")


def login_action(request):
    form_login_action = reverse("login")
    form_mfa_action = reverse("mfa")
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
                messages.danger(request, "User disabled")
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
                    {"user_id": user.id, "form_mfa_action": form_mfa_action},
                )

            # log user in
            login(request, user)
            messages.success(request, "User logged in")

            # check if the user is using the default password
            verify_default_password(request)

            # redirect after login
            next_url = resolve_url(request.GET.get("next", reverse("home")))
            return redirect(next_url)

        # if wrong data
        else:
            messages.error(request, "Incorrect username or password, try again")
            return render(
                request,
                "users/login.html",
                {"form": form, "form_login_action": form_login_action},
            )

    # if GET method
    else:
        form = CustomAuthenticationForm()

    return render(
        request,
        "users/login.html",
        {"form": form, "form_login_action": form_login_action},
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
            "You are using a default and insecure password, change it",
        )
        return redirect("change_password")


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


def mfa(request):
    form_mfa_action = reverse("mfa")

    # get the user id
    user_id = request.POST.get("user_id")

    # if id is not found
    if not user_id:
        messages.error(request, "An error has occurred, try again")
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
                messages.success(request, "MFA activated")
                return redirect("profile")

            # user in mfa page authenticating
            login(request, user)
            messages.success(request, "User logged in")

            # check if the user is using the default password
            verify_default_password(request)

            return redirect("home")

        # if false
        else:
            messages.error(request, "Invalid code, try again")

            # user in profile page failed activating mfa
            if request.user and request.user.is_authenticated:
                return redirect("profile")

            # user in mfa page failed authenticating
            return render(
                request,
                "users/mfa.html",
                {"user_id": user_id, "form_mfa_action": form_mfa_action},
            )

    # if GET method
    return redirect("login")


@login_required
def profile(request):
    user = request.user

    # if user doesn't have mfa enabled, alert them
    if not user.mfa_enabled:
        messages.warning(request, "Enable Two-Factor Authentication")

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


@login_required
def edit_action(request, user_id=None):
    user = get_user_model().objects.get(id=user_id) if user_id else request.user
    return_page_action = reverse("active_users") if user_id else reverse("profile")

    # if an user without permissions (we still have to check the permissions) is trying to access the edit page of an user other than himself, do not allow
    if request.user and request.user.id != user.id:
        messages.error(request, "Without permissions")
        return redirect("profile")

    if request.method == "POST":
        form = CustomUserChangeForm(request.POST, instance=user, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, "User edited")
            return redirect("active_users") if user_id else redirect("profile")
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


# view to change password via profile form
@login_required
def change_password(request):
    return_page_action = reverse("edit")
    if request.method == "POST":
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(
                request, user
            )  # keeps user logged in after changes
            messages.success(request, "Password updated")
            return redirect("profile")
    else:
        form = CustomPasswordChangeForm(user=request.user)

    return render(
        request,
        "users/change_password.html",
        {"form": form, "return_page_action": return_page_action},
    )
