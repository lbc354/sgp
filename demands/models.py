from django.db import models
from django.conf import settings


CATEGORY_CHOICES = [
    (None, "---------"),
    ("Suporte Técnico", "Suporte Técnico"),
    ("Administrativo", "Administrativo"),
]


class Demands(models.Model):
    class Meta:
        db_table = "demands"
        # db_table = "demand_assignments"

    category = models.CharField(
        max_length=20, null=True, blank=False, choices=CATEGORY_CHOICES
    )
    title = models.CharField(max_length=255, null=True, blank=False)
    description = models.TextField(null=True, blank=False)
    # deadline for completion
    due_date = models.DateField(null=True, blank=True)

    # user who received the demand
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="dem_assigned_to",
        null=True,
        blank=False,
    )
    # user who made the distribution
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="dem_assigned_by",
        null=True,
        blank=False,
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    completed = models.BooleanField(default=False, null=False, blank=True)
    # archived = models.BooleanField(default=False, null=False, blank=True)


class DemandsHistory(models.Model):
    class Meta:
        db_table = "demands_history"
        # db_table = "demand_assignments_history"

    demand = models.ForeignKey(
        "Demands",
        related_name="history_entries",  # Why use the plural? related_name="history_entries" means that a single Demands may have multiple DemandsHistory entries. Therefore, the name should reflect this grouping behavior.
        on_delete=models.CASCADE,  # use on_delete=models.CASCADE if you want the histories to disappear with the original demand, or SET_NULL with null=True if you want to keep
        null=False,
        blank=False,
    )

    category = models.CharField(
        max_length=20, null=True, blank=False, choices=CATEGORY_CHOICES
    )
    title = models.CharField(max_length=255, null=True, blank=False)
    description = models.TextField(null=True, blank=False)
    # deadline for completion
    due_date = models.DateField(null=True, blank=True)

    # user who received the demand
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="dem_assigned_to",
        null=True,
        blank=False,
    )
    # user who made the distribution
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="dem_assigned_by",
        null=True,
        blank=False,
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    completed = models.BooleanField(default=False, null=False, blank=True)
    # archived = models.BooleanField(default=False, null=False, blank=True)
