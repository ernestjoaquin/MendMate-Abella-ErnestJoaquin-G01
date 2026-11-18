from django.db import migrations

CATEGORIES = [
    "Tutoring", "Phone / Gadget Repair", "Plumbing", "Electrical", "Cleaning",
    "Errands & Delivery", "Gardening", "Cooking & Baking", "Moving & Carrying", "Other",
]


def add_categories(apps, schema_editor):
    Category = apps.get_model("tasks", "Category")
    for name in CATEGORIES:
        Category.objects.get_or_create(name=name)


def remove_categories(apps, schema_editor):
    apps.get_model("tasks", "Category").objects.filter(name__in=CATEGORIES).delete()


class Migration(migrations.Migration):

    dependencies = [("tasks", "0001_initial")]

    operations = [migrations.RunPython(add_categories, remove_categories)]
