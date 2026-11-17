from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class User(AbstractUser):
    """MendMate user. Uses Django's built-in authentication (passwords are hashed)."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        POSTER = "poster", "Task Poster"
        HELPER = "helper", "Helper"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.POSTER)
    contact_number = models.CharField(
        max_length=15,
        blank=True,
        validators=[RegexValidator(r"^\+?\d{7,14}$", "Enter a valid contact number (digits only, 7 to 14).")],
    )
    location_area = models.CharField("barangay / area", max_length=100, blank=True)
    skills = models.CharField(
        max_length=255, blank=True, help_text="For helpers. Example: tutoring, phone repair, plumbing"
    )
    bio = models.TextField(max_length=500, blank=True)
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)

    REQUIRED_FIELDS = ["email"]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        if self.is_superuser:  # superusers created with createsuperuser are admins
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    def display_name(self):
        return self.get_full_name() or self.username
