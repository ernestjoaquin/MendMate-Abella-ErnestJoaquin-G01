from django.contrib import admin

from .models import Category, Task


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "poster", "helper", "budget", "preferred_date", "status")
    list_filter = ("status", "category")
    search_fields = ("title", "description", "location_area", "poster__username")
