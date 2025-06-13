from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    class Meta:
        db_table = "users"

    email = models.EmailField(unique=True, null=True, blank=False)

    mfa_secret = models.CharField(max_length=255, null=True, blank=True)
    mfa_enabled = models.BooleanField(default=False)

    # created_at = models.DateTimeField(auto_now_add=True)  # similar to date_joined
    updated_at = models.DateTimeField(auto_now=True)

    # let's pretend the user is not available to do something or to have something linked to him (like time_off)
    available = models.BooleanField(default=True)

    def __str__(self):
        return self.get_full_name() or self.username


class PasswordResetToken(models.Model):
    class Meta:
        db_table = "pswd_reset"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        from django.utils.timezone import now

        return (now() - self.created_at).total_seconds() < 3600  # Expira em 1 hora
