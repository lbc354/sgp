from django.conf import settings
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
from datetime import date, datetime, timedelta
from demands.models import Demands, DemandsHistory
from demands.forms import DemandsForm
from django.db.models import Q
from django.db import transaction
import logging


logger = logging.getLogger(__name__)
signer = TimestampSigner()


def get_demands(request, is_completed, can_manage_users=None):
    # query
    q = request.GET.get("q", "").strip().lower()
    # date_query
    dq = request.GET.get("dq", "").strip()  # "YYYY-MM" format

    base_filter = Q(completed=is_completed)  # true or false
    # query = Q()

    if not can_manage_users:
        base_filter &= Q(assigned_to=request.user)

    # filtering by search bar
    if q:
        base_filter &= (
            Q(category__icontains=q)
            | Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(assigned_to__username__icontains=q)
            | Q(assigned_by__username__icontains=q)
        )

    # filtering by date input
    if dq:
        try:
            datetime.strptime(dq, "%Y-%m")
            base_filter &= (
                Q(due_date__startswith=dq)
                | Q(created_at__startswith=dq)
                | Q(updated_at__startswith=dq)
            )
        except ValueError:
            pass

    return Demands.objects.filter(base_filter).order_by("-updated_at", "-created_at")


# demands list
@login_required
def demands_view(request):
    can_manage_users = user_is_in_group(request, "manage_users")

    # incomplete demands
    demands = get_demands(request, False, can_manage_users)

    # final list after applying the filters
    demands_list = []

    for demand in demands:

        demands_list.append(
            {
                "demand": demand,
            }
        )

    page_obj, pagination_range = make_pagination(
        request, demands_list, settings.PER_PAGE
    )

    return render(
        request,
        "demands/demands.html",
        {
            "page_obj": page_obj,
            "pagination_range": pagination_range,
        },
    )


# completed demands list
@login_required
def demands_completed_view(request):
    can_manage_users = user_is_in_group(request, "manage_users")

    # completed demands
    demands = get_demands(request, True, can_manage_users)

    # final list after applying the filters
    demands_list = []

    for demand in demands:

        demands_list.append(
            {
                "demand": demand,
            }
        )

    page_obj, pagination_range = make_pagination(
        request, demands_list, settings.PER_PAGE
    )

    return render(
        request,
        "demands/demands.html",
        {
            "page_obj": page_obj,
            "pagination_range": pagination_range,
        },
    )


# create demand
@login_required
@transaction.atomic
@group_required("manage_users")
def demand_create(request):
    # calculation of current, previous and next weeks
    today = now().date()
    current_year, current_week, _ = today.isocalendar()

    # previous week
    if current_week == 1:
        previous_year = current_year - 1
        previous_week = date(previous_year, 12, 28).isocalendar()[1]
    else:
        previous_year = current_year
        previous_week = current_week - 1

    # next week
    if current_week in [52, 53]:  # depending on the year, it can have 52 or 53 weeks
        next_year = current_year + 1
        next_week = 1
    else:
        next_year = current_year
        next_week = current_week + 1

    # getting demand count by user
    demands = Demands.objects.filter(completed=False, due_date__isnull=False)
    demands_current_week = demands.filter(
        due_date__week=current_week, due_date__year=current_year
    )
    demands_previous_week = demands.filter(
        due_date__week=previous_week,
        due_date__year=previous_year,
    )
    demands_next_week = demands.filter(
        due_date__week=next_week,
        due_date__year=next_year,
    )

    demand_count = []
    users = get_user_model().objects.filter(is_superuser=False, is_active=True)

    for user in users:
        demands_current_week_filtered = demands_current_week.filter(
            Q(assigned_to=user)
        ).distinct()
        demands_previous_week_filtered = demands_previous_week.filter(
            Q(assigned_to=user)
        ).distinct()
        demands_next_week_filtered = demands_next_week.filter(
            Q(assigned_to=user)
        ).distinct()

        amount_current = demands_current_week_filtered.count()
        amount_previous = demands_previous_week_filtered.count()
        amount_next = demands_next_week_filtered.count()
        total = amount_current + amount_previous + amount_next
        demand_count.append(
            {
                "user": user.get_full_name() or user.username,
                "amount_current": amount_current,
                "amount_previous": amount_previous,
                "amount_next": amount_next,
                "total": total,
            }
        )

    demand_count.sort(key=lambda x: (x["total"], x["user"]))

    if request.method == "POST":
        form = DemandsForm(
            request.POST,
            assigned_to_filter={},
        )

        if form.is_valid():
            demand = form.save(commit=False)
            demand.assigned_by = request.user
            demand.save()

            # prepare data for history
            history_data = {
                field.name: getattr(demand, field.name)
                for field in DemandsHistory._meta.fields
                if field.name
                # ignore these fields:
                not in [
                    "id",
                    "demand",
                ]
            }
            DemandsHistory.objects.create(
                demand=demand,
                **history_data,
            )

            if (
                settings.SEND_EMAILS == True
                and demand
                and (getattr(demand, "assigned_to", None))
            ):
                try:
                    user = get_user_model().objects.get(id=demand.assigned_to.id)
                except get_user_model().DoesNotExist:
                    messages.error(request, "Usuário não encontrado.")
                    return redirect("demand_create")

                assigned_to_email = getattr(user, "email", None)

                if assigned_to_email:
                    try:
                        current_site = get_current_site(request)
                        domain = current_site.domain
                        url = f"http://{domain}{reverse('demand_history', args=[demand.id])}"

                        creation_date = demand.created_at.strftime("%d/%m/%Y")

                        subject = f"Nova Demanda"
                        sender = settings.EMAIL_SENDER
                        recipient_list = [f"{assigned_to_email}"]

                        email_content = f"""\
                        <html>
                            <body>
                                <p>Olá, {user}. Uma nova demanda foi distribuída à você em {creation_date} por {demand.assigned_by}.</p>
                                <p>Veja mais detalhes em: <a href="{url}" target="_blank" rel="noopener noreferrer">Demanda</a></p>
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
                                request, f"Email enviado para {recipient_list}"
                            )
                        except Exception as e:
                            logger.error(
                                f"DEMAND_CREATE | Erro no envio do email para {recipient_list}: {str(e)}"
                            )
                            messages.error(
                                request,
                                f"Erro no envio do email para {recipient_list}",
                            )

                    except Exception as e:
                        logger.error(f"DEMAND_CREATE | Erro ao enviar email: {str(e)}")
                        messages.error(request, f"Erro ao enviar email")

            messages.success(request, "Demanda cadastrada.")
            return redirect("consultivo_view")

        else:
            messages.error(request, f"Dados inválidos, tente novamente")
            return render(
                request,
                "demands/demand_create.html",
                {
                    "form": form,
                    "demand_count": demand_count,
                    "current_year": current_year,
                    "previous_week": previous_week,
                    "next_week": next_week,
                },
            )

    else:
        form = DemandsForm(
            assigned_to_filter={},
        )

    return render(
        request,
        "consultivo/consultivo_cadastro.html",
        {
            "form": form,
            "demand_count": demand_count,
            "current_year": current_year,
            "previous_week": previous_week,
            "next_week": next_week,
        },
    )


# edit demand
# @login_required
# def demand_edit(request, pk):
#     form_action = reverse("consultivo_edit", args=[pk])

#     demanda = get_object_or_404(DemandaConsultivo, pk=pk)

#     if demanda.concluida and request.method == "POST":
#         return redirect("consultivo_view")  # Impedir edição de demandas concluídas

#     if request.method == "POST":
#         form = DemandaConsultivoForm(
#             request.POST,
#             instance=demanda,
#             vinculacao_filter={},
#             procurador_filter={},
#             coordenador_aprovacao_filter={},
#             assessor_manifestacao_filter={},
#             assessor_despacho_coordenador_filter={},
#             assessor_despacho_procurador_geral_filter={},
#         )

#         if form.is_valid():
#             demanda = form.save(commit=False)
#             demanda.responsavel = request.user
#             demanda = form.save()
#             messages.success(request, "Demanda Editada")

#             # Preparar dados para o histórico
#             historico_data = {
#                 field.name: getattr(demanda, field.name)
#                 for field in HistoricoDemandaConsultivo._meta.fields
#                 if field.name
#                 not in [
#                     "id",
#                     "demanda",
#                     "criado_em",
#                     "atualizado_em",
#                 ]
#             }

#             HistoricoDemandaConsultivo.objects.create(
#                 demanda=demanda,  # Passar explicitamente a demanda relacionada
#                 **historico_data,
#             )

#             historico = HistoricoDemandaConsultivo.objects.filter(
#                 demanda=demanda
#             ).order_by("-atualizado_em")

#             page_obj, pagination_range = make_pagination(request, historico, PER_PAGE)

#             return render(
#                 request,
#                 "consultivo/consultivo_historico.html",
#                 {
#                     "demanda": demanda,
#                     "page_obj": page_obj,
#                     "pagination_range": pagination_range,
#                 },
#             )
#         else:
#             messages.error(request, f"Dados inválidos, tente novamente")
#             return render(
#                 request,
#                 "consultivo/consultivo_detalhes.html",
#                 {"form": form, "form_action": form_action, "demanda": demanda},
#             )

#     else:
#         form = DemandaConsultivoForm(
#             instance=demanda,
#             vinculacao_filter={},
#             procurador_filter={},
#             coordenador_aprovacao_filter={},
#             assessor_manifestacao_filter={},
#             assessor_despacho_coordenador_filter={},
#             assessor_despacho_procurador_geral_filter={},
#         )

#     return render(
#         request,
#         "consultivo/consultivo_detalhes.html",
#         {"form": form, "form_action": form_action, "demanda": demanda},
#     )


# conclude demand
# @login_required
# def demand_conclude(request, pk):
#     if request.method == "POST":
#         demanda = get_object_or_404(DemandaConsultivo, pk=pk)
#         demanda.concluida = True
#         if not demanda.data_destino:
#             demanda.data_destino = now().date()
#         demanda.save()
#         messages.success(request, "Demanda Concluída")

#         historico_data = {
#             field.name: getattr(demanda, field.name)
#             for field in HistoricoDemandaConsultivo._meta.fields
#             if field.name
#             not in [
#                 "id",
#                 "demanda",
#                 "criado_em",
#                 "atualizado_em",
#             ]
#         }
#         HistoricoDemandaConsultivo.objects.create(
#             demanda=demanda,
#             **historico_data,
#         )

#         # if (
#         #     ENVIAR_EMAILS == True
#         #     and demanda
#         #     and (
#         #         getattr(demanda, "procurador", None)
#         #         or getattr(demanda, "vinculacao", None)
#         #     )
#         # ):
#         #     email_procurador = getattr(demanda.procurador, "email", None)
#         #     email_vinculacao = getattr(demanda.vinculacao, "email", None)

#         #     if email_procurador or email_vinculacao:
#         #         try:
#         #             # Obtém o domínio absoluto
#         #             current_site = get_current_site(request)
#         #             domain = current_site.domain
#         #             url = f"http://{domain}{reverse('consultivo_historico', args=[demanda.id])}"

#         #             data_atualizacao = demanda.ultima_atualizacao.strftime("%d/%m/%Y")
#         #             procurador = None
#         #             if email_procurador:
#         #                 procurador = get_object_or_404(
#         #                     get_user_model(), pk=demanda.procurador_id
#         #                 )
#         #             elif email_vinculacao:
#         #                 procurador = get_object_or_404(
#         #                     get_user_model(), pk=demanda.vinculacao_id
#         #                 )

#         #             if procurador:
#         #                 corpo_envio = f"""\
#         #                 <html>
#         #                     <body>
#         #                         <p>Olá, {procurador}. Uma demanda foi concluída em {data_atualizacao} por {demanda.responsavel}.</p>
#         #                         <p>Veja em: <a href="{url}" target="_blank" rel="noopener noreferrer">Demanda</a></p>
#         #                     </body>
#         #                 </html>
#         #                 """

#         #                 # Configuração do E-mail a ser enviado
#         #                 remetente = "svc.sgda@dnit.gov.br"
#         #                 destinatario = f"{procurador.email}"
#         #                 # destinatario = "lucas.carregozi@dnit.gov.br"
#         #                 assunto = f"Demanda Concluída"

#         #                 # Criar um objeto de mensagem multiparte
#         #                 msg = MIMEMultipart()

#         #                 # Definir cabeçalhos de correio eletrônico
#         #                 msg["From"] = remetente
#         #                 msg["To"] = destinatario
#         #                 msg["Subject"] = assunto

#         #                 # Adicionar o corpo da mensagem de correio eletrônico
#         #                 msg.attach(MIMEText(corpo_envio, "html"))

#         #                 try:
#         #                     server = smtplib.SMTP("10.100.10.45")
#         #                     text = msg.as_string()
#         #                     server.sendmail(remetente, destinatario, text)
#         #                     server.quit()
#         #                     messages.success(
#         #                         request, f"Email enviado para {destinatario}"
#         #                     )
#         #                 except Exception as e:
#         #                     print(
#         #                         f"CONSULTIVO_CONCLUIR | Erro no envio do email para {destinatario}: {str(e)}"
#         #                     )
#         #                     messages.error(
#         #                         request, f"Erro no envio do email para {destinatario}"
#         #                     )

#         #         except Exception as e:
#         #             print(
#         #                 f"CONSULTIVO_CONCLUIR | Erro ao enviar email para {destinatario}: {str(e)}"
#         #             )
#         #             messages.error(request, f"Erro ao enviar email para {destinatario}")

#         return redirect("consultivo_view")

#     return redirect("consultivo_view")  # Redirecionar se não for POST


# restore demand
# @login_required
# def demand_restore(request, pk):
#     if request.method == "POST":
#         demanda = get_object_or_404(DemandaConsultivo, pk=pk)
#         demanda.concluida = False
#         if demanda.data_destino:
#             demanda.data_destino = None
#         demanda.save()
#         messages.success(request, "Demanda Restaurada")

#         historico_data = {
#             field.name: getattr(demanda, field.name)
#             for field in HistoricoDemandaConsultivo._meta.fields
#             if field.name
#             not in [
#                 "id",
#                 "demanda",
#                 "criado_em",
#                 "atualizado_em",
#             ]
#         }
#         HistoricoDemandaConsultivo.objects.create(
#             demanda=demanda,
#             **historico_data,
#         )

#         # if (
#         #     ENVIAR_EMAILS == True
#         #     and demanda
#         #     and (
#         #         getattr(demanda, "procurador", None)
#         #         or getattr(demanda, "vinculacao", None)
#         #     )
#         # ):
#         #     email_procurador = getattr(demanda.procurador, "email", None)
#         #     email_vinculacao = getattr(demanda.vinculacao, "email", None)

#         #     if email_procurador or email_vinculacao:
#         #         try:
#         #             # Obtém o domínio absoluto
#         #             current_site = get_current_site(request)
#         #             domain = current_site.domain
#         #             url = f"http://{domain}{reverse('consultivo_historico', args=[demanda.id])}"

#         #             data_atualizacao = demanda.ultima_atualizacao.strftime("%d/%m/%Y")
#         #             procurador = None
#         #             if email_procurador:
#         #                 procurador = get_object_or_404(
#         #                     get_user_model(), pk=demanda.procurador_id
#         #                 )
#         #             elif email_vinculacao:
#         #                 procurador = get_object_or_404(
#         #                     get_user_model(), pk=demanda.vinculacao_id
#         #                 )

#         #             if procurador:
#         #                 corpo_envio = f"""\
#         #                 <html>
#         #                     <body>
#         #                         <p>Olá, {procurador}. Uma demanda foi restaurada em {data_atualizacao} por {demanda.responsavel}.</p>
#         #                         <p>Veja em: <a href="{url}" target="_blank" rel="noopener noreferrer">Demanda</a></p>
#         #                     </body>
#         #                 </html>
#         #                 """

#         #                 # Configuração do E-mail a ser enviado
#         #                 remetente = "svc.sgda@dnit.gov.br"
#         #                 destinatario = f"{procurador.email}"
#         #                 # destinatario = "lucas.carregozi@dnit.gov.br"
#         #                 assunto = f"Demanda Restaurada"

#         #                 # Criar um objeto de mensagem multiparte
#         #                 msg = MIMEMultipart()

#         #                 # Definir cabeçalhos de correio eletrônico
#         #                 msg["From"] = remetente
#         #                 msg["To"] = destinatario
#         #                 msg["Subject"] = assunto

#         #                 # Adicionar o corpo da mensagem de correio eletrônico
#         #                 msg.attach(MIMEText(corpo_envio, "html"))

#         #                 try:
#         #                     server = smtplib.SMTP("10.100.10.45")
#         #                     text = msg.as_string()
#         #                     server.sendmail(remetente, destinatario, text)
#         #                     server.quit()
#         #                     messages.success(
#         #                         request, f"Email enviado para {destinatario}"
#         #                     )
#         #                 except Exception as e:
#         #                     print(
#         #                         f"CONSULTIVO_RESTAURAR | Erro no envio do email para {destinatario}: {str(e)}"
#         #                     )
#         #                     messages.error(
#         #                         request, f"Erro no envio do email para {destinatario}"
#         #                     )

#         #         except Exception as e:
#         #             print(
#         #                 f"CONSULTIVO_RESTAURAR | Erro ao enviar email para {destinatario}: {str(e)}"
#         #             )
#         #             messages.error(request, f"Erro ao enviar email para {destinatario}")

#         return redirect("consultivo_concluidas_view")

#     return redirect("consultivo_concluidas_view")  # Redirecionar se não for POST


# general history
# @login_required
# def demand_history(request, pk):
#     demanda = get_object_or_404(DemandaConsultivo, pk=pk)
#     historico = HistoricoDemandaConsultivo.objects.filter(demanda=demanda).order_by(
#         "-atualizado_em"
#     )

#     page_obj, pagination_range = make_pagination(request, historico, PER_PAGE)

#     return render(
#         request,
#         "consultivo/consultivo_historico.html",
#         {
#             "demanda": demanda,
#             "page_obj": page_obj,
#             "pagination_range": pagination_range,
#         },
#     )


# specific history
# @login_required
# def demand_history_details(request, pk, historico_id):
#     # Obtém o histórico específico e a demanda associada
#     historico = get_object_or_404(
#         HistoricoDemandaConsultivo, pk=historico_id, demanda__id=pk
#     )

#     # pk = historico.demanda.id = id da demanda (demanda_id na tabela de histórico)
#     # historico_id = historico.id = id do histórico da demanda na tabela de histórico)

#     # Buscar o histórico anterior (o mais recente antes do atual)
#     historico_anterior = (
#         HistoricoDemandaConsultivo.objects.filter(
#             demanda=historico.demanda, atualizado_em__lt=historico.atualizado_em
#         )
#         .order_by("-atualizado_em")
#         .first()
#     )

#     # Criar um dicionário de diferenças
#     campos_alterados = {}
#     if historico_anterior:
#         for field in historico._meta.get_fields():
#             nome_campo = field.name
#             if hasattr(historico, nome_campo) and hasattr(
#                 historico_anterior, nome_campo
#             ):
#                 valor_atual = getattr(historico, nome_campo)
#                 valor_anterior = getattr(historico_anterior, nome_campo)

#                 if valor_atual != valor_anterior:
#                     campos_alterados[nome_campo] = True

#     form = DemandaConsultivoForm(
#         instance=historico,
#         readonly=True,
#         vinculacao_filter={},
#         procurador_filter={},
#         coordenador_aprovacao_filter={},
#         assessor_manifestacao_filter={},
#         assessor_despacho_coordenador_filter={},
#         assessor_despacho_procurador_geral_filter={},
#     )

#     return render(
#         request,
#         "consultivo/consultivo_historico_detalhes.html",
#         {
#             "historico": historico,
#             "form": form,
#             "campos_alterados": campos_alterados,
#         },
#     )
