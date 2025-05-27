from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class PasswordResetToken(models.Model):
    class Meta:
        db_table = "pswd_reset"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        from django.utils.timezone import now

        return (now() - self.created_at).total_seconds() < 3600  # Expira em 1 hora


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True, null=False, blank=False)

    mfa_secret = models.CharField(max_length=100, blank=True, null=True)
    mfa_enabled = models.BooleanField(default=False)

    def __str__(self):
        return self.get_full_name() or self.username
