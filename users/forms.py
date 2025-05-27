from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, PasswordChangeForm
from .models import CustomUser


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Username"}
        ),
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password"}
        ),
    )


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
            # "username": "Username",
        }

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)

        # adds css class
        for field_name, field in self.fields.items():
            if field.widget.attrs.get("class"):
                field.widget.attrs["class"] += " form-control"
            else:
                field.widget.attrs["class"] = "form-control"

        if request is not None:
            self.fields.pop("password", None)
            # check if user has permissions
            # has_permissions = check_permissions(request).get("is_allowed", False)
            # if doesn't have required permission, hide inputs
            # if not has_permissions:
            #     self.fields.pop("groups", None)


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # adds css class
        for field_name, field in self.fields.items():
            if field.widget.attrs.get("class"):
                field.widget.attrs["class"] += " form-control"
            else:
                field.widget.attrs["class"] = "form-control"
