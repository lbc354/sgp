from django import forms
from django.conf import settings
from django.contrib.auth.forms import (
    AuthenticationForm,
    # UserCreationForm,
    UserChangeForm,
    PasswordChangeForm,
)
from users.models import CustomUser
from utils.decorators import user_is_in_group


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Usuário"}
        ),
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Senha"}
        ),
    )


# class CustomUserCreationForm(UserCreationForm):
class CustomUserCreationForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "groups",
        )
        labels = {
            "first_name": "Nome",
            "last_name": "Sobrenome",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("password1", None)
        self.fields.pop("password2", None)
        for field_name, field in self.fields.items():
            if field.widget.attrs.get("class"):
                field.widget.attrs["class"] += " form-control"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned_data = super().clean()  # calls the parent class's clean method

        # clean whitespace from all fields in the form
        for campo, valor in cleaned_data.items():
            if isinstance(valor, str):  # check if the value is a string
                cleaned_data[campo] = (
                    valor.strip()
                )  # remove leading and trailing spaces

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(settings.DEFAULT_USER_PASSWORD)  # pattern password
        if commit:
            user.save()
            self.save_m2m()  # ensures groups are assigned correctly
        return user


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "groups",
        )
        labels = {
            "first_name": "Nome",
            "last_name": "Sobrenome",
        }

    def __init__(self, *args, request=None, **kwargs):
        is_itself = kwargs.pop("is_itself", None)
        super().__init__(*args, **kwargs)

        # adds css class
        for field_name, field in self.fields.items():
            if field.widget.attrs.get("class"):
                field.widget.attrs["class"] += " form-control"
            else:
                field.widget.attrs["class"] = "form-control"

        if request is not None:
            self.fields.pop("password", None)
            # user can't edit groups/permissions if he doesn't have permission to
            # user can't edit own groups/permissions
            if not user_is_in_group(request, "manage_users") or is_itself:
                self.fields.pop("groups", None)

    def clean(self):
        cleaned_data = super().clean()  # calls the parent class's clean method

        # clean whitespace from all fields in the form
        for campo, valor in cleaned_data.items():
            if isinstance(valor, str):  # check if the value is a string
                cleaned_data[campo] = (
                    valor.strip()
                )  # remove leading and trailing spaces

        return cleaned_data


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # adds css class
        for field_name, field in self.fields.items():
            if field.widget.attrs.get("class"):
                field.widget.attrs["class"] += " form-control"
            else:
                field.widget.attrs["class"] = "form-control"
