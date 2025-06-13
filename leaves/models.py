from django.db import models
from django.conf import settings


class Leaves(models.Model):
    class Meta:
        db_table = "leaves"

    DESCRIPTION_CHOICES = [
        ("", "---------"),
        ("F", "Férias"),
        ("L", "Licença"),
        ("R", "Recesso"),
        ("S", "Suspensão"),
    ]

    # the one on leave
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="lea_user",
        null=True,
        blank=False,
    )
    # the one who grants leave
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="lea_responsible",
        null=True,
        blank=False,
    )

    description = models.CharField(
        max_length=25, null=True, blank=False, choices=DESCRIPTION_CHOICES
    )
    observation = models.CharField(max_length=255, null=True, blank=True)
    start_date = models.DateField(null=True, blank=False)
    end_date = models.DateField(null=True, blank=False)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    interrupted = models.BooleanField(default=False)
