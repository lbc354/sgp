from django import forms
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from .models import Leaves
# from demands.models import Demands


class LeavesForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Usuário",
        required=True,
    )

    description = forms.ChoiceField(
        choices=Leaves.DESCRIPTION_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Descrição",
    )

    def __init__(self, *args, **kwargs):
        # extracting filters
        user_filter = kwargs.pop("user_filter", None)

        super().__init__(*args, **kwargs)

        # applying filters
        if user_filter:
            self.fields["user"].queryset = get_user_model().objects.filter(
                **user_filter, is_superuser=False, is_active=True
            )
        else:
            self.fields["user"].queryset = get_user_model().objects.filter(
                is_superuser=False, is_active=True
            )

        # formats the existing date to ISO 8601 format (yyyy-MM-dd)
        if self.initial.get("start_date"):
            self.initial["start_date"] = self.initial["start_date"].strftime("%Y-%m-%d")
        if self.initial.get("end_date"):
            self.initial["end_date"] = self.initial["end_date"].strftime("%Y-%m-%d")

    class Meta:
        model = Leaves
        fields = [
            "user",
            "description",
            "start_date",
            "end_date",
            "observation",
        ]

        widgets = {
            "start_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                },
            ),
            "end_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                },
            ),
            "observation": forms.TextInput(attrs={"class": "form-control"}),
        }

        labels = {
            "user": "Usuário",
            "description": "Descrição",
            "start_date": "Data início",
            "end_date": "Data fim",
            "observation": "Observação",
        }

    def clean(self):
        cleaned_data = super().clean()

        # validating date
        today = now().date()
        limit_years = 2
        limit_months = 2
        # before saving the leave, check if there is any demand with a deadline that falls within the period of the leave to be registered
        user = cleaned_data.get("user")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        def validate_date(field, date, past_limit, future_limit, message):
            if date:
                if date < (today - past_limit) or date > (today + future_limit):
                    raise forms.ValidationError({field: message})

        if start_date and end_date:
            if start_date > end_date:
                raise forms.ValidationError(
                    {
                        "end_date": "A data de término não pode ser menor que a data de início."
                    }
                )

            # start_date validation
            validate_date(
                "start_date",
                start_date,
                relativedelta(years=limit_years),
                relativedelta(years=limit_years),
                f"Fora do prazo de tempo.",
            )

            # end_date validation
            if end_date > start_date + relativedelta(months=limit_months):
                raise forms.ValidationError(
                    {
                        "end_date": f"Fora do prazo de até {limit_months} meses."
                    }
                )

            if user:
                pending_demand = Demands.objects.filter(
                    responsible=user,
                    filed=False,
                    demand_deadline__range=(start_date, end_date),
                )
                if pending_demand.exists():
                    raise forms.ValidationError({"start_date": "Demanda com prazo pendente neste período."})

        else:
            raise forms.ValidationError(
                {"user": f"Preencha todos os campos obrigatórios."}
            )

        return cleaned_data
