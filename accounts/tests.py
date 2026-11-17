import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from django.urls import reverse

from .models import User

PASSWORD = "StrongPass#2026"


def make_user(username, role, email=None, **extra):
    return User.objects.create_user(
        username=username, email=email or f"{username}@example.com", password=PASSWORD, role=role, **extra
    )


class RegistrationTests(TestCase):
    data = {
        "username": "juan", "first_name": "Juan", "last_name": "Cruz", "email": "Juan@Example.com",
        "contact_number": "09171234567", "role": "poster", "password1": PASSWORD, "password2": PASSWORD,
    }

    def test_register_success_hashes_password(self):
        response = self.client.post(reverse("register"), self.data, follow=True)
        self.assertRedirects(response, reverse("login"))
        self.assertContains(response, "Account created successfully")
        user = User.objects.get(username="juan")
        self.assertNotEqual(user.password, PASSWORD)          # never plain text
        self.assertTrue(user.password.startswith("pbkdf2_"))   # hashed by Django
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.email, "juan@example.com")       # stored in lowercase

    def test_required_fields(self):
        response = self.client.post(reverse("register"), {})
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(response, "This field is required")
        self.assertContains(response, "Please fix the errors below")

    def test_invalid_email_format(self):
        response = self.client.post(reverse("register"), {**self.data, "email": "not-an-email"})
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(response, "Enter a valid email address")

    def test_duplicate_username_and_email(self):
        make_user("juan", "poster", email="juan@example.com")
        r1 = self.client.post(reverse("register"), {**self.data, "email": "other@example.com"})
        self.assertContains(r1, "A user with that username already exists")
        r2 = self.client.post(reverse("register"), {**self.data, "username": "juan2"})
        self.assertContains(r2, "An account with this email already exists")
        self.assertEqual(User.objects.count(), 1)

    def test_password_confirmation_must_match(self):
        response = self.client.post(reverse("register"), {**self.data, "password2": "Different#123"})
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(response, "password fields didn")

    def test_cannot_register_as_admin(self):
        response = self.client.post(reverse("register"), {**self.data, "role": "admin"})
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(response, "Select a valid choice")


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.poster = make_user("pat", "poster")
        self.helper = make_user("hal", "helper")
        self.admin = User.objects.create_superuser("boss", "boss@example.com", PASSWORD)

    def test_invalid_login_shows_error(self):
        response = self.client.post(reverse("login"), {"username": "pat", "password": "wrong"})
        self.assertContains(response, "Invalid username or password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_redirects_to_role_dashboard(self):
        for username, url_name in (("pat", "poster_dashboard"), ("hal", "helper_dashboard"), ("boss", "admin_dashboard")):
            self.client.logout()
            response = self.client.post(reverse("login"), {"username": username, "password": PASSWORD}, follow=True)
            self.assertEqual(response.redirect_chain[-1][0], reverse(url_name))
            self.assertEqual(response.status_code, 200)

    def test_superuser_gets_admin_role(self):
        self.assertEqual(self.admin.role, User.Role.ADMIN)

    def test_logout_ends_session(self):
        self.client.login(username="pat", password=PASSWORD)
        response = self.client.post(reverse("logout"), follow=True)
        self.assertRedirects(response, reverse("login"))
        self.assertContains(response, "You have been logged out")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post(self):
        self.client.login(username="pat", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)

    def test_protected_pages_redirect_to_login(self):
        for name in ("dashboard", "poster_dashboard", "helper_dashboard", "admin_dashboard", "profile", "profile_edit"):
            url = reverse(name)
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('login')}?next={url}", msg_prefix=name)


class RoleAccessTests(TestCase):
    def setUp(self):
        make_user("pat", "poster")
        make_user("hal", "helper")
        User.objects.create_superuser("boss", "boss@example.com", PASSWORD)

    def assert_blocked(self, username, forbidden_urls, own_dashboard):
        self.client.login(username=username, password=PASSWORD)
        for name in forbidden_urls:
            response = self.client.get(reverse(name), follow=True)
            self.assertEqual(response.redirect_chain[-1][0], reverse(own_dashboard), msg=f"{username} -> {name}")
            self.assertContains(response, "You do not have access to that page")

    def test_poster_cannot_open_other_dashboards(self):
        self.assert_blocked("pat", ["helper_dashboard", "admin_dashboard"], "poster_dashboard")

    def test_helper_cannot_open_other_dashboards(self):
        self.assert_blocked("hal", ["poster_dashboard", "admin_dashboard"], "helper_dashboard")

    def test_admin_cannot_open_user_dashboards(self):
        self.assert_blocked("boss", ["poster_dashboard", "helper_dashboard"], "admin_dashboard")

    def test_each_dashboard_has_role_content(self):
        self.client.login(username="pat", password=PASSWORD)
        self.assertContains(self.client.get(reverse("poster_dashboard")), "Post a task")
        self.client.login(username="hal", password=PASSWORD)
        self.assertContains(self.client.get(reverse("helper_dashboard")), "Available tasks")
        self.client.login(username="boss", password=PASSWORD)
        self.assertContains(self.client.get(reverse("admin_dashboard")), "Total users")


class ProfileTests(TestCase):
    def setUp(self):
        self.pat = make_user("pat", "poster", first_name="Pat", last_name="Lim")
        self.hal = make_user("hal", "helper", first_name="Hal", last_name="Tan", skills="tutoring")
        self.client.login(username="pat", password=PASSWORD)

    def test_view_own_profile_only(self):
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "pat@example.com")
        self.assertNotContains(response, "hal@example.com")

    def test_update_profile(self):
        response = self.client.post(reverse("profile_edit"), {
            "first_name": "Patricia", "last_name": "Lim", "email": "patricia@example.com",
            "contact_number": "09181234567", "location_area": "Mandalagan", "bio": "Hello!",
        }, follow=True)
        self.assertRedirects(response, reverse("profile"))
        self.assertContains(response, "Your profile was updated")
        self.pat.refresh_from_db()
        self.assertEqual((self.pat.first_name, self.pat.email, self.pat.location_area), ("Patricia", "patricia@example.com", "Mandalagan"))

    def test_cannot_use_another_users_email(self):
        response = self.client.post(reverse("profile_edit"), {
            "first_name": "Pat", "last_name": "Lim", "email": "hal@example.com"})
        self.assertContains(response, "Another account already uses this email")

    def test_cannot_edit_other_user_or_change_role(self):
        self.client.post(reverse("profile_edit"), {
            "first_name": "Hacked", "last_name": "Name", "email": "pat@example.com", "role": "admin", "username": "hal"})
        self.hal.refresh_from_db(); self.pat.refresh_from_db()
        self.assertEqual(self.hal.first_name, "Hal")           # other user untouched
        self.assertEqual(self.pat.role, User.Role.POSTER)      # role cannot be changed here
        self.assertEqual(self.pat.username, "pat")

    def test_skills_field_only_for_helpers(self):
        self.assertNotContains(self.client.get(reverse("profile_edit")), 'name="skills"')
        self.client.login(username="hal", password=PASSWORD)
        self.assertContains(self.client.get(reverse("profile_edit")), 'name="skills"')

    def test_upload_profile_photo(self):
        media = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media):
                buffer = io.BytesIO()
                Image.new("RGB", (4, 4), "teal").save(buffer, format="PNG")
                png = buffer.getvalue()
                photo = SimpleUploadedFile("me.png", png, content_type="image/png")
                self.client.post(reverse("profile_edit"), {
                    "first_name": "Pat", "last_name": "Lim", "email": "pat@example.com", "profile_photo": photo})
                self.pat.refresh_from_db()
                self.assertTrue(self.pat.profile_photo.name.startswith("profile_photos/"))
        finally:
            shutil.rmtree(media, ignore_errors=True)
