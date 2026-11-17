from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class MendMateUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("MendMate profile", {"fields": ("role", "contact_number", "location_area", "skills", "bio", "profile_photo")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("MendMate profile", {"fields": ("email", "role")}),
    )
