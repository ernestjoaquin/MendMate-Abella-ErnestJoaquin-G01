from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse


class Category(models.Model):
    """What kind of help a task needs (tutoring, plumbing, errands, ...)."""

    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Task(models.Model):
    """Core feature: a small task that a Task Poster needs help with and a Helper can accept."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACCEPTED = "accepted", "Accepted"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    MAX_ACTIVE_JOBS_PER_HELPER = 3  # business rule: a helper can only hold 3 accepted tasks at once

    # Relationships (ERD): Task -> User (poster), Task -> User (helper), Task -> Category
    poster = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posted_tasks")
    helper = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="accepted_tasks"
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="tasks")

    title = models.CharField(max_length=120)
    description = models.TextField(max_length=1000)
    location_area = models.CharField("barangay / area", max_length=100)
    budget = models.DecimalField(
        "budget (PHP)",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(1), MaxValueValidator(100000)],
    )
    preferred_date = models.DateField("preferred date")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("task_detail", args=[self.pk])

    @property
    def is_open(self):
        return self.status == self.Status.OPEN

    @property
    def is_accepted(self):
        return self.status == self.Status.ACCEPTED
