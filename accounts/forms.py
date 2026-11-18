from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class RegistrationForm(UserCreationForm):
    """Registration form. UserCreationForm checks the two passwords match and hashes the password."""

    role = forms.ChoiceField(
        choices=[(User.Role.POSTER, "Task Poster - I need help with tasks"),
                 (User.Role.HELPER, "Helper - I want to offer my skills")],
        widget=forms.RadioSelect,
        label="I want to join as",
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "contact_number", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True
        self.fields["username"].help_text = "Letters, digits and @/./+/-/_ only."

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_role(self):
        role = self.cleaned_data["role"]
        if role not in (User.Role.POSTER, User.Role.HELPER):  # nobody can register as admin
            raise forms.ValidationError("Choose a valid role.")
        return role


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "contact_number", "location_area", "skills", "bio", "profile_photo")
        widgets = {"bio": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True
        if self.instance.role != User.Role.HELPER:  # skills only apply to helpers
            del self.fields["skills"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email
