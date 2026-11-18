from django import forms
from django.utils import timezone

from .models import Category, Task


class TaskForm(forms.ModelForm):
    """Create / edit a task, with the business rules for MendMate tasks."""

    class Meta:
        model = Task
        fields = ("category", "title", "description", "location_area", "budget", "preferred_date")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "preferred_date": forms.DateInput(attrs={"type": "date"}),
            "budget": forms.NumberInput(attrs={"step": "0.01", "min": "1"}),
        }

    def clean_title(self):
        title = " ".join(self.cleaned_data["title"].split())  # trims and collapses spaces
        if len(title) < 5:
            raise forms.ValidationError("The title must be at least 5 characters long.")
        return title

    def clean_description(self):
        description = self.cleaned_data["description"].strip()
        if len(description) < 15:
            raise forms.ValidationError("Please describe the task in at least 15 characters.")
        return description

    def clean_location_area(self):
        area = self.cleaned_data["location_area"].strip()
        if len(area) < 2:
            raise forms.ValidationError("Enter the barangay or area where the task will be done.")
        return area

    def clean_preferred_date(self):
        date = self.cleaned_data["preferred_date"]
        unchanged = self.instance.pk and date == self.instance.preferred_date
        if date < timezone.localdate() and not unchanged:
            raise forms.ValidationError("The preferred date cannot be in the past.")
        return date


class TaskFilterForm(forms.Form):
    """Search and filter box on the task list (submitted with GET)."""

    q = forms.CharField(required=False, label="Search", widget=forms.TextInput(attrs={"placeholder": "Title, details or area"}))
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, empty_label="All categories")
    status = forms.ChoiceField(required=False, choices=[("", "All statuses")] + list(Task.Status.choices))
