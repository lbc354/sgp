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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="lea_user", null=True, blank=False)
    # the one who grants leave
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="lea_resp", null=True, blank=False)

    description = models.CharField(max_length=25, null=True, blank=False, choices=DESCRIPTION_CHOICES)
    observation = models.CharField(max_length=255, null=True, blank=False)
    start_date = models.DateField(null=True, blank=False)
    end_date = models.DateField(null=True, blank=False)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    interrupted = models.BooleanField(default=False)

    # updates leave status (active or not) and user's availability (yes or no)
    # current_leave value is None, True or False
    def update_leave_status(self, current_leave=None):
        # if current_leave is True, the leave is activated and the user is NOT available
        if current_leave:
            self.is_active = True
            if hasattr(self.user, "available"):
                self.user.available = False
        # if current_leave is False, the leave is NOT activated and the user is available
        else:
            self.is_active = False
            if hasattr(self.user, "available"):
                self.user.available = True
        if hasattr(self.user, "save"):
            self.user.save()
        self.save()
