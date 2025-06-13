from django.conf import settings
from django.db import transaction
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import render, redirect
from django.urls import reverse
from utils.pagination import make_pagination
from utils.decorators import group_required, deny_if_not_in_group, user_is_in_group
from django.utils.timezone import now
from django.utils.html import strip_tags
from django.core.signing import TimestampSigner
from django.core.mail import EmailMultiAlternatives
from datetime import datetime, timedelta
from leaves.models import Leaves
from leaves.forms import LeavesForm
import logging


logger = logging.getLogger(__name__)
signer = TimestampSigner()


"""
The distribution shall be suspended on the days immediately preceding the start of vacation, leave, or any other legally granted absence, in accordance with current legislation, in order to provide the User with a period during which they may complete the review of matters under their responsibility.

§ 1º The suspension period provided for in the main clause shall be:
I - two business days, when the leave period is equal to or less than ten days;
II - three business days, when the leave period is between eleven and twenty days; and
III - four business days, when the leave period is between twenty-one and thirty days.

§ 2º No User may begin a vacation period while having urgent matters or deadlines falling during the vacation period.
"""


def get_users(id_user=None):
    if id_user:
        return get_user_model().objects.filter(
            is_superuser=False, is_staff=False, is_active=True, id=id_user
        )
    return get_user_model().objects.filter(
        is_superuser=False, is_staff=False, is_active=True
    )


def order_users(users_data):
    users_data.sort(
        key=lambda x: (
            not bool(x["availability"]),  # unavailable comes first
            (
                datetime.strptime(x["next_leave"]["start_date"], "%d/%m/%Y")
                if x["next_leave"]
                else datetime.max
            ),  # nearest next leave comes first
            str(x["user"].username).lower(),  # alphabetical order
        ),
    )


def process_leave(user, users_data):
    current_leave = search_current_leave(user)

    if current_leave:
        make_user_unavailable(user)
    else:
        make_user_available(user)

    next_leave = search_next_leave(user)
    last_leave = search_last_leave(user)
    availability = determine_availability(current_leave)

    add_user_data(
        users_data,
        user,
        current_leave,
        next_leave,
        last_leave,
        availability,
    )


# § 1º
def search_current_leave(user):
    today = now().date()
    next_leave = search_next_leave(user)

    if next_leave:
        unavailability_start_date = next_leave.start_date
        leave_period_days = (next_leave.end_date - next_leave.start_date).days

        adjustment = 0
        if leave_period_days <= 10:
            adjustment = 2
        elif 10 < leave_period_days <= 20:
            adjustment = 3
        elif leave_period_days > 20:
            adjustment = 4

        unavailability_start_date -= timedelta(days=adjustment)

        if unavailability_start_date <= today <= next_leave.start_date:
            return next_leave

    return Leaves.objects.filter(
        user=user,
        interrupted=False,
        start_date__lte=today,
        end_date__gte=today,
    ).first()


def search_next_leave(user):
    return (
        Leaves.objects.filter(
            user=user,
            interrupted=False,
            start_date__gt=now().date(),
        )
        .order_by("start_date")
        .first()
    )


def search_last_leave(user):
    return (
        Leaves.objects.filter(
            user=user,
            interrupted=False,
            end_date__lt=now().date(),
        )
        .order_by("-end_date")
        .first()
    )


# @transaction.atomic
def make_user_available(user):
    # making the leave inactive and the user available
    try:
        Leaves.objects.filter(
            user=user,
            is_active=True,
        ).update(is_active=False)
        if hasattr(user, "available"):
            user.available = True
            user.save()
    except Exception as e:
        logger.error(
            f"LEAVES_MAKE_USER_AVAILABLE | Erro disponibilizando usuário: {str(e)}"
        )


# @transaction.atomic
def make_user_unavailable(user):
    # making the leave active and the user unavailable
    try:
        Leaves.objects.filter(
            user=user,
            is_active=False,
        ).update(is_active=True)
        if hasattr(user, "available"):
            user.available = False
            user.save()
    except Exception as e:
        logger.error(
            f"LEAVES_MAKE_USER_AVAILABLE | Erro indisponibilizando usuário: {str(e)}"
        )


def determine_availability(current_leave):
    if current_leave:
        return (
            f"{current_leave.start_date.strftime('%d/%m/%Y')} "
            f"- {current_leave.end_date.strftime('%d/%m/%Y')} "
            f"| {current_leave.get_description_display()}"
        )
    return None


def add_user_data(
    users_data,
    user,
    current_leave,
    next_leave,
    last_leave,
    availability,
):
    users_data.append(
        {
            "user": user,
            "available": not current_leave,
            "availability": availability,
            "next_leave": (
                {
                    "description": next_leave.get_description_display(),
                    "start_date": next_leave.start_date.strftime("%d/%m/%Y"),
                    "end_date": next_leave.end_date.strftime("%d/%m/%Y"),
                }
                if next_leave
                else None
            ),
            "last_leave": (
                {
                    "description": last_leave.get_description_display(),
                    "start_date": last_leave.start_date.strftime("%d/%m/%Y"),
                    "end_date": last_leave.end_date.strftime("%d/%m/%Y"),
                }
                if last_leave
                else None
            ),
        }
    )


@login_required
def leaves_view(request):
    # check if user has permissions
    can_manage_users = user_is_in_group(request, "manage_users")

    # get search filter in url (/?q=abc)
    query = request.GET.get("q", "").strip().lower()

    users_data = []
    # user views all users data or only his own data
    users = get_users() if can_manage_users else get_users(request.user.id)

    for user in users:
        process_leave(user, users_data)

    # filters data based on search
    if query:
        users_data = [
            data
            for data in users_data
            if any(query in str(data[key]).lower() for key in data)
        ]

    order_users(users_data)

    page_obj, pagination_range = make_pagination(request, users_data, settings.PER_PAGE)

    return render(
        request,
        "leaves/leaves.html",
        {
            "page_obj": page_obj,
            "pagination_range": pagination_range,
            "can_manage_users": can_manage_users,
        },
    )


@login_required
@transaction.atomic
@group_required("manage_users")
def leave_create(request, user_id=None):
    if user_id:
        user_filter = {"id": user_id}
        initial_data = {"user": user_id}
        return_page_action = reverse("leaves_active_history", args=[user_id])
        # get user
        try:
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            messages.error(request, "Usuário não encontrado.")
            return redirect("leaves_view")
    else:
        user_filter = {}
        initial_data = {}
        return_page_action = reverse("leaves_view")

    if request.method == "POST":
        form = LeavesForm(
            request.POST,
            user_filter=user_filter,
            initial=initial_data,
        )

        if form.is_valid():
            leave = form.save(commit=False)
            leave.responsible = request.user
            if user_id:
                leave.user = user
            leave.save()
            current_leave = search_current_leave(leave.user)
            if current_leave:
                make_user_unavailable(leave.user)
            else:
                make_user_available(leave.user)

            if settings.SEND_EMAILS == True:
                if leave.user.email:
                    try:
                        start_date = leave.start_date.strftime("%d/%m/%Y")
                        end_date = leave.end_date.strftime("%d/%m/%Y")
                        leave_description = leave.get_description_display()

                        current_site = get_current_site(request)
                        domain = current_site.domain
                        url = f"http://{domain}{reverse('leaves_active_history', args=[leave.user.id])}"

                        subject = f"Registro de {leave_description}"
                        sender = settings.EMAIL_SENDER
                        recipient_list = [f"{leave.user.email}"]

                        email_content = f"""
                        <html>
                            <body>
                                <p>Olá, {leave.user}. Um novo registro de {leave_description} ({start_date} - {end_date}) foi distribuído à você por {leave.responsible}.</p>
                                <p>Veja em: <a href="{url}" target="_blank" rel="noopener noreferrer">Afastamentos</a></p>
                            </body>
                        </html>
                        """

                        text_content = strip_tags(
                            email_content
                        )  # generates text version

                        try:
                            email = EmailMultiAlternatives(
                                subject, text_content, sender, recipient_list
                            )
                            email.attach_alternative(email_content, "text/html")
                            email.send()
                            messages.success(
                                request, f"E-mail enviado para {recipient_list}."
                            )

                        except Exception as e:
                            logger.error(
                                f"LEAVE_CREATE | Erro no envio do email para {recipient_list}: {str(e)}."
                            )
                            messages.error(
                                request,
                                f"Erro no envio do email para {recipient_list}.",
                            )

                    except Exception as e:
                        logger.error(
                            f"LEAVE_CREATE | Erro ao enviar email para {recipient_list}: {str(e)}."
                        )
                        messages.error(
                            request, f"Erro ao enviar email para {recipient_list}."
                        )

            messages.success(request, "Afastamento cadastrado.")
            return redirect("leaves_active_history", leave.user.id)

        else:
            messages.error(request, f"Dados inválidos, tente novamente.")
            return render(
                request,
                "leaves/create.html",
                {
                    "form": form,
                    "return_page_action": return_page_action,
                },
            )

    else:
        form = LeavesForm(
            user_filter=user_filter,
            initial=initial_data,
        )

    return render(
        request,
        "leaves/create.html",
        {
            "form": form,
            "return_page_action": return_page_action,
        },
    )


@login_required
@transaction.atomic
@group_required("manage_users")
def leave_edit(request, user_id, leave_id):
    # get user
    if user_id:
        try:
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            messages.error(request, "Usuário não encontrado.")
            return redirect("leaves_view")
    else:
        messages.error(request, "Forneça o ID do usuário.")
        return redirect("leaves_view")

    # get leave
    if leave_id:
        try:
            leave = Leaves.objects.get(id=leave_id)
        except Leaves.DoesNotExist:
            messages.error(request, "Registro não encontrado.")
            return redirect("leaves_active_history", user_id)
    else:
        messages.error(request, "Forneça o ID do registro.")
        return redirect("leaves_active_history", user_id)

    return_page_action = reverse("leaves_active_history", args=[user_id])
    user_filter = {"id": user_id}
    initial_data = {"user": user}

    if request.method == "POST":
        form = LeavesForm(
            request.POST,
            instance=leave,
            user_filter=user_filter,
            initial=initial_data,
        )

        if form.is_valid():
            leave_form = form.save(commit=False)
            leave_form.responsible = request.user
            leave.user = user_id
            leave_form = form.save()
            current_leave = search_current_leave(leave.user)
            if current_leave:
                make_user_unavailable(leave.user)
            else:
                make_user_available(leave.user)

            if settings.SEND_EMAILS == True:
                # get user
                user = get_user_model().objects.get(id=leave.user)

                if user.email:
                    try:
                        start_date = leave.start_date.strftime("%d/%m/%Y")
                        end_date = leave.end_date.strftime("%d/%m/%Y")
                        leave_description = leave.get_description_display()

                        current_site = get_current_site(request)
                        domain = current_site.domain
                        url = f"http://{domain}{reverse('leaves_active_history', args=[leave.user.id])}"

                        subject = f"Afastamento Editado"
                        sender = settings.EMAIL_SENDER
                        recipient_list = [f"{user.email}"]

                        email_content = f"""\
                        <html>
                            <body>
                                <p>Olá, {leave.user}. Seu afastamento foi alterado: {leave_description} ({start_date} - {end_date}).</p>
                                <p>Veja em: <a href="{url}" target="_blank" rel="noopener noreferrer">Afastamentos</a></p>
                            </body>
                        </html>
                        """

                        text_content = strip_tags(
                            email_content
                        )  # generates text version

                        try:
                            email = EmailMultiAlternatives(
                                subject, text_content, sender, recipient_list
                            )
                            email.attach_alternative(email_content, "text/html")
                            email.send()
                            messages.success(
                                request, f"Email enviado para {recipient_list}."
                            )
                        except Exception as e:
                            logger.error(
                                f"LEAVE_EDIT | Erro no envio do email para {recipient_list}: {str(e)}."
                            )
                            messages.error(
                                request,
                                f"Erro no envio do email para {recipient_list}.",
                            )

                    except Exception as e:
                        logger.error(
                            f"LEAVE_EDIT | Erro ao enviar email para {recipient_list}: {str(e)}."
                        )
                        messages.error(
                            request, f"Erro ao enviar email para {recipient_list}."
                        )

            messages.success(request, "Afastamento editado.")
            return redirect("leaves_active_history", leave.user.id)

        else:
            messages.error(request, "Dados inválidos, tente novamente.")
            return render(
                request,
                "leaves/edit.html",
                {
                    "form": form,
                    "user": user,
                    "leave": leave,
                    "return_page_action": return_page_action,
                },
            )

    else:
        form = LeavesForm(
            instance=leave,
            user_filter=user_filter,
            initial=initial_data,
        )

    return render(
        request,
        "leaves/edit.html",
        {
            "form": form,
            "user": user,
            "leave": leave,
            "return_page_action": return_page_action,
        },
    )


@login_required
def leaves_active_history(request, user_id):
    # get user
    if user_id:
        try:
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            messages.error(request, "Usuário não encontrado.")
            return redirect("leaves_view")
    else:
        messages.error(request, "Forneça o ID do usuário.")
        return redirect("leaves_view")

    can_manage_users = user_is_in_group(request, "manage_users")

    # ensures user status update
    current_leave = search_current_leave(user)
    if current_leave:
        make_user_unavailable(user)
    else:
        make_user_available(user)

    records = Leaves.objects.filter(
        user=user,
        interrupted=False,
    ).order_by("-start_date")

    data_list = []

    for record in records:
        start_date = record.start_date.strftime("%d/%m/%Y")
        end_date = record.end_date.strftime("%d/%m/%Y")

        remaining_days = record.end_date - now().date()
        show_actions = remaining_days.days >= 0

        data_list.append(
            {
                "history": record,
                "period": f"{start_date} - {end_date}",
                "description": record.get_description_display(),
                "observation": (record.observation or "---------"),
                "show_actions": show_actions,
            }
        )

    page_obj, pagination_range = make_pagination(request, data_list, settings.PER_PAGE)
    return_page_action = reverse("leaves_view")

    return render(
        request,
        "leaves/leaves_history.html",
        {
            "user": user,
            "page_obj": page_obj,
            "pagination_range": pagination_range,
            "return_page_action": return_page_action,
            "can_manage_users": can_manage_users,
        },
    )


@login_required
def leaves_interrupted_history(request, user_id):
    # get user
    if user_id:
        try:
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            messages.error(request, "Usuário não encontrado.")
            return redirect("leaves_view")
    else:
        messages.error(request, "Forneça o ID do usuário.")
        return redirect("leaves_view")

    can_manage_users = user_is_in_group(request, "manage_users")

    # ensures user status update
    current_leave = search_current_leave(user)
    if current_leave:
        make_user_unavailable(user)
    else:
        make_user_available(user)

    records = Leaves.objects.filter(
        user=user,
        interrupted=True,
    ).order_by("-start_date")

    data_list = []

    for record in records:
        start_date = record.start_date.strftime("%d/%m/%Y")
        end_date = record.end_date.strftime("%d/%m/%Y")

        remaining_days = record.end_date - now().date()
        show_action = remaining_days.days >= 0

        data_list.append(
            {
                "history": record,
                "period": f"{start_date} - {end_date}",
                "description": record.get_description_display(),
                "observation": (record.observation or "---------"),
                "show_action": show_action,
            }
        )

    page_obj, pagination_range = make_pagination(request, data_list, settings.PER_PAGE)
    return_page_action = reverse("leaves_view")

    return render(
        request,
        "leaves/leaves_history.html",
        {
            "user": user,
            "page_obj": page_obj,
            "pagination_range": pagination_range,
            "return_page_action": return_page_action,
            "can_manage_users": can_manage_users,
            "interrupted": "interrupted",
        },
    )


@login_required
@transaction.atomic
@group_required("manage_users")
def leave_interrupt(request, user_id, leave_id):
    if request.method == "POST":
        # get user
        if user_id:
            try:
                user = get_user_model().objects.get(id=user_id)
            except get_user_model().DoesNotExist:
                messages.error(request, "Usuário não encontrado.")
                return redirect("leaves_view")
        else:
            messages.error(request, "Forneça o ID do usuário.")
            return redirect("leaves_view")

        # get leave
        if leave_id:
            try:
                leave = Leaves.objects.get(id=leave_id)
            except Leaves.DoesNotExist:
                messages.error(request, "Registro não encontrado.")
                return redirect("leaves_active_history", user_id)
        else:
            messages.error(request, "Forneça o ID do registro.")
            return redirect("leaves_active_history", user_id)

        if leave.user.id != user_id:
            messages.error(request, "Usuário e afastamento não correspondentes.")
            return redirect("leaves_active_history", user_id)

        leave.interrupted = True
        leave.save()

        # check if status changed
        current_leave = search_current_leave(leave.user)
        if current_leave:
            make_user_unavailable(leave.user)
        else:
            make_user_available(leave.user)

        if settings.SEND_EMAILS == True:
            if leave.user.email:
                try:
                    start_date = leave.start_date.strftime("%d/%m/%Y")
                    end_date = leave.end_date.strftime("%d/%m/%Y")
                    leave_description = leave.get_description_display()

                    current_site = get_current_site(request)
                    domain = current_site.domain
                    url = f"http://{domain}{reverse('leaves_interrupted_history', args=[leave.user.id])}"

                    subject = f"{leave_description} Interrompido"
                    sender = settings.EMAIL_SENDER
                    recipient_list = [f"{leave.user.email}"]

                    email_content = f"""\
                    <html>
                        <body>
                            <p>Olá, {leave.user}. {leave_description} ({start_date} - {end_date}) foi interrompido(a) por {leave.responsible}.</p>
                            <p>Veja em: <a href="{url}" target="_blank" rel="noopener noreferrer">Afastamentos</a></p>
                        </body>
                    </html>
                    """

                    text_content = strip_tags(email_content)  # generates text version

                    try:
                        email = EmailMultiAlternatives(
                            subject, text_content, sender, recipient_list
                        )
                        email.attach_alternative(email_content, "text/html")
                        email.send()
                        messages.success(
                            request, f"Email enviado para {recipient_list}."
                        )
                    except Exception as e:
                        logger.error(
                            f"LEAVE_INTERRUPT | Erro no envio do email para {recipient_list}: {str(e)}."
                        )
                        messages.error(
                            request, f"Erro no envio do email para {recipient_list}."
                        )

                except Exception as e:
                    logger.error(
                        f"LEAVE_INTERRUPT | Erro ao enviar email para {recipient_list}: {str(e)}."
                    )
                    messages.error(
                        request, f"Erro ao enviar email para {recipient_list}."
                    )

        messages.success(request, "Afastamento interrompido.")
    return redirect("leaves_active_history", user_id)


@login_required
@transaction.atomic
@group_required("manage_users")
def leave_resume(request, user_id, leave_id):
    if request.method == "POST":
        # get user
        if user_id:
            try:
                user = get_user_model().objects.get(id=user_id)
            except get_user_model().DoesNotExist:
                messages.error(request, "Usuário não encontrado.")
                return redirect("leaves_view")
        else:
            messages.error(request, "Forneça o ID do usuário.")
            return redirect("leaves_view")

        # get leave
        if leave_id:
            try:
                leave = Leaves.objects.get(id=leave_id)
            except Leaves.DoesNotExist:
                messages.error(request, "Registro não encontrado.")
                return redirect("leaves_active_history", user_id)
        else:
            messages.error(request, "Forneça o ID do registro.")
            return redirect("leaves_active_history", user_id)

        if leave.user.id != user_id:
            messages.error(request, "Ocorreu um erro.")
            return redirect("leaves_active_history", user_id)

        leave.interrupted = False
        leave.save()

        # check if status changed
        current_leave = search_current_leave(leave.user)
        if current_leave:
            make_user_unavailable(leave.user)
        else:
            make_user_available(leave.user)

        if settings.SEND_EMAILS == True:
            if leave.user.email:
                try:
                    start_date = leave.start_date.strftime("%d/%m/%Y")
                    end_date = leave.end_date.strftime("%d/%m/%Y")
                    leave_description = leave.get_description_display()

                    current_site = get_current_site(request)
                    domain = current_site.domain
                    url = f"http://{domain}{reverse('leaves_active_history', args=[leave.user.id])}"

                    subject = f"{leave_description} Retomado"
                    sender = settings.EMAIL_SENDER
                    recipient_list = [f"{leave.user.email}"]

                    email_content = f"""\
                    <html>
                        <body>
                            <p>Olá, {leave.user}. {leave_description} ({start_date} - {end_date}) foi retomado por {leave.responsible}.</p>
                            <p>Veja em: <a href="{url}" target="_blank" rel="noopener noreferrer">Afastamentos</a></p>
                        </body>
                    </html>
                    """

                    text_content = strip_tags(email_content)  # generates text version

                    try:
                        email = EmailMultiAlternatives(
                            subject, text_content, sender, recipient_list
                        )
                        email.attach_alternative(email_content, "text/html")
                        email.send()
                        messages.success(
                            request, f"Email enviado para {recipient_list}."
                        )
                    except Exception as e:
                        logger.error(
                            f"LEAVE_RESUME | Erro no envio do email para {recipient_list}: {str(e)}."
                        )
                        messages.error(
                            request, f"Erro no envio do email para {recipient_list}."
                        )

                except Exception as e:
                    logger.error(
                        f"LEAVE_RESUME | Erro ao enviar email para {recipient_list}: {str(e)}."
                    )
                    messages.error(
                        request, f"Erro ao enviar email para {recipient_list}."
                    )

        messages.success(request, "Afastamento retomado.")
    return redirect("leaves_interrupted_history", user_id)
