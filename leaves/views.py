from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.timezone import now
from utils.pagination import make_pagination
from utils.decorators import group_required, deny_if_not_in_group, user_is_in_group
from leaves.models import Leaves
from leaves.forms import LeavesForm
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib


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
        current_leave.update_leave_status(current_leave=True)
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
        leave_period_days = (
            next_leave.end_date - next_leave.start_date
        ).days

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


def make_user_available(user):
    Leaves.objects.filter(
        user=user,
        is_active=True,
    ).update(is_active=False)
    if hasattr(user, "available"):
        user.available = True
        user.save()


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
@group_required('manage_users')
def leave_edit(request, user_id, leave_id):
    # get user
    if user_id:
        try:
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            messages.error(request, "Usuário não encontrado")
            return redirect("leaves_view")
    else:
        messages.error(request, "Forneça o ID o usuário")
        return redirect("leaves_view")

    # get leave
    if leave_id:
        try:
            leave = Leaves.objects.get(id=leave_id)
        except Leaves.DoesNotExist:
            messages.error(request, "Registro não encontrado")
            return redirect("leaves_active_history", args=[user_id])
    else:
        messages.error(request, "Forneça o ID do registro")
        return redirect("leaves_active_history", args=[user_id])

    # buttons
    return_page_action = reverse("leaves_active_history", args=[user_id])

    # checking if end_date is before today
    difference = leave.end_date - now().date()
    gte_hoje = difference.days >= 0
    if gte_hoje == False and request.method == "POST":
        return redirect('leave_edit', user_id=user_id, leave_id=leave_id)

    user_filter = {"id": user_id} if user_id else {}
    initial_data = {"user": user} if user_id else {}

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
            if user_id:
                leave.user = user_id
            leave_form = form.save()
            current_leave = search_current_leave(leave.user)
            if current_leave:
                current_leave.update_leave_status(current_leave=True)
            else:
                make_user_available(leave.user)
            messages.success(request, "Afastamento editado")

            if settings.SEND_EMAILS == True:
                # get user
                try:
                    user = get_user_model().objects.get(id=leave.user)
                except get_user_model().DoesNotExist:
                    messages.error(request, "Usuário não encontrado")
                    return redirect("leave_edit", args=[user_id, leave_id])
                
                if user and user.email:
                    try:
                        start_date = leave.start_date.strftime("%d/%m/%Y")
                        end_date = leave.end_date.strftime("%d/%m/%Y")
                        leave_description = leave.get_description_display()

                        current_site = get_current_site(request)
                        domain = current_site.domain
                        url = f"http://{domain}{reverse('leaves_active_history', args=[leave.user])}"

                        email_content = f"""\
                        <html>
                            <body>
                                <p>Olá, {leave.user}. Seu afastamento foi alterado: {leave_description} ({start_date} - {end_date}).</p>
                                <p>Veja em: <a href="{url}" target="_blank" rel="noopener noreferrer">Afastamentos</a></p>
                            </body>
                        </html>
                        """

                        subject = f"Afastamento Editado"
                        sender = "svc.app@dnit.gov.br"
                        recipient = f"{user.email}"

                        msg = MIMEMultipart()

                        msg["Subject"] = subject
                        msg["From"] = sender
                        msg["To"] = recipient

                        msg.attach(MIMEText(email_content, "html"))

                        try:
                            server = smtplib.SMTP("10.100.10.45")
                            text = msg.as_string()
                            server.sendmail(sender, recipient, text)
                            server.quit()
                            messages.success(
                                request, f"Email enviado para {recipient}"
                            )
                        except Exception as e:
                            print(
                                f"LEAVE_EDIT | Erro no envio do email para {recipient}: {str(e)}"
                            )
                            messages.error(
                                request, f"Erro no envio do email para {recipient}"
                            )

                    except Exception as e:
                        print(
                            f"LEAVE_EDIT | Erro ao enviar email para {recipient}: {str(e)}"
                        )
                        messages.error(
                            request, f"Erro ao enviar email para {recipient}"
                        )

            return redirect("leaves_active_history", args=[user_id])

        else:
            messages.error(request, "Dados inválidos, tente novamente")
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
@group_required('manage_users')
def leave_create(request, id=None):
    user_filter = {"id": id} if id else {}
    initial_data = {"user": id} if id else {}
    return_page_action = (
        reverse("leaves_active_history", args=[id])
        if id
        else reverse("leaves_view")
    )

    if request.method == "POST":
        form = LeavesForm(
            request.POST,
            user_filter=user_filter,
            initial=initial_data,
        )

        if form.is_valid():
            leave = form.save(commit=False)
            leave.responsible = request.user
            if id:
                leave.user = id
            leave.save()
            current_leave = search_current_leave(leave.user)
            if current_leave:
                current_leave.update_leave_status(current_leave=True)
            else:
                make_user_available(leave.user)
            messages.success(request, "Afastamento Cadastrado")

            if settings.SEND_EMAILS == True:
                # get user
                try:
                    user = get_user_model().objects.get(id=leave.user)
                except get_user_model().DoesNotExist:
                    messages.error(request, "Usuário não encontrado")
                    return redirect("leaves_view")

                if user and user.email:
                    try:
                        start_date = leave.start_date.strftime("%d/%m/%Y")
                        end_date = leave.end_date.strftime("%d/%m/%Y")
                        leave_description = leave.get_description_display()

                        current_site = get_current_site(request)
                        domain = current_site.domain
                        url = f"http://{domain}{reverse('leaves_active_history', args=[leave.user])}"

                        email_content = f"""\
                        <html>
                            <body>
                                <p>Olá, {leave.user}. Um novo registro de {leave_description} ({start_date} - {end_date}) foi distribuído à você por {leave.responsible}.</p>
                                <p>Veja em: <a href="{url}" target="_blank" rel="noopener noreferrer">Afastamentos</a></p>
                            </body>
                        </html>
                        """

                        subject = f"Registro de {leave_description}"
                        sender = "svc.app@dnit.gov.br"
                        recipient = f"{user.email}"

                        msg = MIMEMultipart()

                        msg["Subject"] = subject
                        msg["From"] = sender
                        msg["To"] = recipient

                        msg.attach(MIMEText(email_content, "html"))

                        try:
                            server = smtplib.SMTP("10.100.10.45")
                            text = msg.as_string()
                            server.sendmail(sender, recipient, text)
                            server.quit()
                            messages.success(
                                request, f"Email enviado para {recipient}"
                            )
                        except Exception as e:
                            print(
                                f"LEAVE_CREATE | Erro no envio do email para {recipient}: {str(e)}"
                            )
                            messages.error(
                                request, f"Erro no envio do email para {recipient}"
                            )

                    except Exception as e:
                        print(
                            f"LEAVE_CREATE | Erro ao enviar email para {recipient}: {str(e)}"
                        )
                        messages.error(
                            request, f"Erro ao enviar email para {recipient}"
                        )

        else:
            messages.error(request, f"Dados inválidos, tente novamente")
            return render(
                request,
                "leaves/create.html",
                {
                    "form": form,
                    "return_page_action": return_page_action,
                },
            )

        return redirect("leaves_active_history", args=[leave.user])

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
def leaves_active_history(request, pk):
    procurador = get_object_or_404(get_user_model(), pk=pk)
    if procurador:
        current_leave = search_current_leave(procurador)
        if current_leave:
            current_leave.atualizar_status(current_leave=True)
        else:
            make_user_available(procurador)
        registros = Leaves.objects.filter(
            procurador=procurador,
            interrompido=False,
        ).order_by("-data_inicio")

        dados = []

        for registro in registros:
            diferenca = registro.data_fim - now().date()
            dias_restantes = diferenca.days
            show_actions = dias_restantes >= 0

            dados.append(
                {
                    "historico": registro,
                    "data_inicio": registro.data_inicio.strftime("%d/%m/%Y"),
                    "data_fim": registro.data_fim.strftime("%d/%m/%Y"),
                    "descricao": registro.get_descricao_display(),
                    "observacao": (registro.observacao or "---------"),
                    "show_actions": show_actions,
                }
            )

        page_obj, pagination_range = make_pagination(request, dados, settings.PER_PAGE)
        return_page_action = reverse("afastamentos_view")

        return render(
            request,
            "afastamentos/afastamentos_historico.html",
            {
                "procurador": procurador,
                "page_obj": page_obj,
                "pagination_range": pagination_range,
                "return_page_action": return_page_action,
            },
        )

    else:
        return redirect("afastamentos_view")


@login_required
def leaves_interrupted_history(request, pk):
    procurador = get_object_or_404(get_user_model(), pk=pk)
    registros = Leaves.objects.filter(
        procurador=procurador,
        interrompido=True,
    ).order_by("-data_inicio")

    dados = []

    for registro in registros:
        diferenca = registro.data_fim - now().date()
        dias_restantes = diferenca.days
        show_action = dias_restantes >= 0

        dados.append(
            {
                "historico": registro,
                "data_inicio": registro.data_inicio.strftime("%d/%m/%Y"),
                "data_fim": registro.data_fim.strftime("%d/%m/%Y"),
                "descricao": registro.get_descricao_display(),
                "observacao": (registro.observacao or "---------"),
                "show_action": show_action,
            }
        )

    page_obj, pagination_range = make_pagination(request, dados, settings.PER_PAGE)
    return_page_action = reverse("afastamentos_view")

    return render(
        request,
        "afastamentos/afastamentos_interrompidos.html",
        {
            "hidden": "hidden",
            "procurador": procurador,
            "page_obj": page_obj,
            "pagination_range": pagination_range,
            "return_page_action": return_page_action,
        },
    )


@login_required
@group_required('manage_users')
def leave_interrupt(request, pk, afastamento_id):
    if request.method == "POST":
        afastamento = get_object_or_404(Leaves, pk=afastamento_id)
        afastamento.interrompido = True
        afastamento.save()
        current_leave = search_current_leave(afastamento.procurador_id)
        if current_leave:
            current_leave.atualizar_status(current_leave=True)
        else:
            make_user_available(afastamento.procurador_id)
        messages.success(request, "Afastamento Interrompido")

        if settings.ENVIAR_EMAILS == True:
            procurador = get_object_or_404(
                get_user_model(), pk=afastamento.procurador_id
            )
            if procurador and procurador.email:
                try:
                    data_de_inicio = afastamento.data_inicio.strftime("%d/%m/%Y")
                    data_de_fim = afastamento.data_fim.strftime("%d/%m/%Y")
                    descricao_afastamento = afastamento.get_descricao_display()

                    # Obtém o domínio absoluto
                    current_site = get_current_site(request)
                    domain = current_site.domain
                    url = f"http://{domain}{reverse('afastamentos_interrompidos', args=[afastamento.procurador_id])}"

                    corpo_envio = f"""\
                    <html>
                        <body>
                            <p>Olá, {afastamento.procurador}. {descricao_afastamento} ({data_de_inicio} - {data_de_fim}) foi interrompido por {afastamento.responsavel}.</p>
                            <p>Veja em: <a href="{url}" target="_blank" rel="noopener noreferrer">Afastamentos</a></p>
                        </body>
                    </html>
                    """

                    # Configuração do E-mail a ser enviado
                    remetente = "sv.app@dnit.gov.br"
                    destinatario = f"{procurador.email}"
                    # destinatario = "lucas.carregozi@dnit.gov.br"
                    assunto = f"{descricao_afastamento} Interrompido"

                    # Criar um objeto de mensagem multiparte
                    msg = MIMEMultipart()

                    # Definir cabeçalhos de correio eletrônico
                    msg["From"] = remetente
                    msg["To"] = destinatario
                    msg["Subject"] = assunto

                    # Adicionar o corpo da mensagem de correio eletrônico
                    msg.attach(MIMEText(corpo_envio, "html"))

                    try:
                        server = smtplib.SMTP("10.100.10.45")
                        text = msg.as_string()
                        server.sendmail(remetente, destinatario, text)
                        server.quit()
                        messages.success(request, f"Email enviado para {destinatario}")
                    except Exception as e:
                        print(
                            f"INTERROMPER_AFASTAMENTO | Erro no envio do email para {destinatario}: {str(e)}"
                        )
                        messages.error(
                            request, f"Erro no envio do email para {destinatario}"
                        )

                except Exception as e:
                    print(
                        f"INTERROMPER_AFASTAMENTO | Erro ao enviar email para {destinatario}: {str(e)}"
                    )
                    messages.error(request, f"Erro ao enviar email para {destinatario}")

    return redirect("afastamentos_historico", pk=pk)


@login_required
@group_required('manage_users')
def leave_resume(request, pk, afastamento_id):
    if request.method == "POST":
        afastamento = get_object_or_404(Leaves, pk=afastamento_id)
        afastamento.interrompido = False
        afastamento.save()
        current_leave = search_current_leave(afastamento.procurador_id)
        if current_leave:
            current_leave.atualizar_status(current_leave=True)
        else:
            make_user_available(afastamento.procurador_id)
        messages.success(request, "Afastamento Retomado")

        if settings.ENVIAR_EMAILS == True:
            procurador = get_object_or_404(
                get_user_model(), pk=afastamento.procurador_id
            )
            if procurador and procurador.email:
                try:
                    data_de_inicio = afastamento.data_inicio.strftime("%d/%m/%Y")
                    data_de_fim = afastamento.data_fim.strftime("%d/%m/%Y")
                    descricao_afastamento = afastamento.get_descricao_display()

                    # Obtém o domínio absoluto
                    current_site = get_current_site(request)
                    domain = current_site.domain
                    url = f"http://{domain}{reverse('afastamentos_historico', args=[afastamento.procurador_id])}"

                    corpo_envio = f"""\
                    <html>
                        <body>
                            <p>Olá, {afastamento.procurador}. {descricao_afastamento} ({data_de_inicio} - {data_de_fim}) foi retomado por {afastamento.responsavel}.</p>
                            <p>Veja em: <a href="{url}" target="_blank" rel="noopener noreferrer">Afastamentos</a></p>
                        </body>
                    </html>
                    """

                    # Configuração do E-mail a ser enviado
                    remetente = "sv.app@dnit.gov.br"
                    destinatario = f"{procurador.email}"
                    # destinatario = "lucas.carregozi@dnit.gov.br"
                    assunto = f"{descricao_afastamento} Retomado"

                    # Criar um objeto de mensagem multiparte
                    msg = MIMEMultipart()

                    # Definir cabeçalhos de correio eletrônico
                    msg["From"] = remetente
                    msg["To"] = destinatario
                    msg["Subject"] = assunto

                    # Adicionar o corpo da mensagem de correio eletrônico
                    msg.attach(MIMEText(corpo_envio, "html"))

                    try:
                        server = smtplib.SMTP("10.100.10.45")
                        text = msg.as_string()
                        server.sendmail(remetente, destinatario, text)
                        server.quit()
                        messages.success(request, f"Email enviado para {destinatario}")
                    except Exception as e:
                        print(
                            f"RETOMAR_AFASTAMENTO | Erro no envio do email para {destinatario}: {str(e)}"
                        )
                        messages.error(
                            request, f"Erro no envio do email para {destinatario}"
                        )

                except Exception as e:
                    print(
                        f"RETOMAR_AFASTAMENTO | Erro ao enviar email para {destinatario}: {str(e)}"
                    )
                    messages.error(request, f"Erro ao enviar email para {destinatario}")

    return redirect("afastamentos_interrompidos", pk=pk)
