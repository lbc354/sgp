from django import forms
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from demands.models import Demands, CATEGORY_CHOICES


class DemandsForm(forms.ModelForm):
    assigned_to = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        widget=forms.Select(attrs={"class": "form-control", "size": 6}),
        required=True,
        label="Executor",
    )
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        widget=forms.Select(attrs={"class": "form-control", "size": 6}),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        # extracting filters
        assigned_to_filter = kwargs.pop("assigned_to_filter", None)

        # checking if fields are readonly
        readonly = kwargs.pop("readonly", False)
        # getting instance of associated demand
        demand = kwargs.get("instance")

        super().__init__(*args, **kwargs)

        # applying filters
        if assigned_to_filter:
            self.fields["assigned_to"].queryset = (
                get_user_model()
                .objects.filter(
                    **assigned_to_filter,
                    is_superuser=False,
                    is_active=True,
                )
                .order_by("username")
            )
        else:
            self.fields["assigned_to"].queryset = (
                get_user_model()
                .objects.filter(
                    is_superuser=False,
                    is_active=True,
                )
                .order_by("username")
            )

        # formats the date to ISO 8601 format (yyyy-MM-dd)
        if self.initial.get("due_date"):
            self.initial["due_date"] = self.inital["due_date"].strftime("%Y-%m-%d")

        # turning fields into readonly if user is in the history page or if demand is completed (can't edit)
        if readonly or demand and demand.completed:
            for field_name, field in self.fields.items():
                old_attrs = field.widget.attrs.copy()

                if isinstance(field, (forms.ModelChoiceField, forms.ChoiceField)):
                    self.fields[field_name].widget = forms.TextInput(
                        attrs={
                            **old_attrs,
                            "disabled": "disabled",
                        }
                    )
                    self.fields[field_name].initial = self.initial.get(field_name)
                else:
                    field.widget.attrs["disabled"] = "disabled"

    class Meta:
        model = Demands

        fields = [
            "category",
            "title",
            "description",
            "due_date",
            "assigned_to",
        ]

        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "size": 12}),
            "description": forms.Textarea(
                attrs={"class": "form-control", "size": 12, "rows": 4}
            ),
            "due_date": forms.DateInput(
                attrs={"class": "form-control", "size": 6, "type": "date"}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        today = now().date()

        if cleaned_data.get("due_date") < today:
            raise forms.ValidationError(
                {"due_date": "A data não pode ser anterior ao dia de hoje."}
            )

        return cleaned_data
