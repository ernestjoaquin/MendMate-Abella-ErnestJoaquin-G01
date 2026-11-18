from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .models import Category, Task

PASSWORD = "StrongPass#2026"


def make_user(username, role, **extra):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD, role=role, **extra
    )


class TaskTestCase(TestCase):
    def setUp(self):
        self.pat = make_user("pat", "poster", contact_number="09171111111")
        self.pam = make_user("pam", "poster")
        self.hal = make_user("hal", "helper", contact_number="09172222222")
        self.hank = make_user("hank", "helper")
        self.boss = make_user("boss", "admin")
        self.category = Category.objects.get(name="Tutoring")

    def login(self, user):
        self.client.login(username=user.username, password=PASSWORD)

    def make_task(self, poster=None, **extra):
        data = dict(
            poster=poster or self.pat, category=self.category, title="Fix my laptop",
            description="The laptop will not turn on since yesterday.", location_area="Lahug",
            budget=Decimal("500"), preferred_date=timezone.localdate() + timedelta(days=3),
        )
        data.update(extra)
        return Task.objects.create(**data)

    def form_data(self, **extra):
        data = {
            "category": self.category.pk, "title": "Fix my laptop", "location_area": "Lahug",
            "description": "The laptop will not turn on since yesterday.", "budget": "500.00",
            "preferred_date": (timezone.localdate() + timedelta(days=3)).isoformat(),
        }
        data.update(extra)
        return data


class AccessTests(TaskTestCase):
    def test_logged_out_users_are_sent_to_login(self):
        task = self.make_task()
        for name, args in (("task_list", []), ("task_create", []), ("my_jobs", []), ("task_detail", [task.pk]),
                           ("task_update", [task.pk]), ("task_delete", [task.pk])):
            response = self.client.get(reverse(name, args=args))
            self.assertRedirects(response, f"{reverse('login')}?next={reverse(name, args=args)}", msg_prefix=name)

    def test_only_posters_can_create_tasks(self):
        for user in (self.hal, self.boss):
            self.login(user)
            response = self.client.get(reverse("task_create"), follow=True)
            self.assertContains(response, "You do not have access to that page")
            self.client.logout()
        self.assertEqual(Task.objects.count(), 0)

    def test_my_jobs_is_for_helpers_only(self):
        self.login(self.pat)
        self.assertContains(self.client.get(reverse("my_jobs"), follow=True), "You do not have access")


class CreateTests(TaskTestCase):
    def test_poster_creates_task_linked_to_self(self):
        self.login(self.pat)
        response = self.client.post(reverse("task_create"), self.form_data(), follow=True)
        task = Task.objects.get()
        self.assertRedirects(response, reverse("task_detail", args=[task.pk]))
        self.assertContains(response, "Your task was posted")
        self.assertEqual(task.poster, self.pat)
        self.assertEqual(task.status, Task.Status.OPEN)
        self.assertEqual(task.budget, Decimal("500.00"))

    def test_required_fields(self):
        self.login(self.pat)
        response = self.client.post(reverse("task_create"), {})
        self.assertEqual(Task.objects.count(), 0)
        self.assertContains(response, "This field is required")
        self.assertContains(response, "Please fix the errors below")

    def test_business_rules(self):
        self.login(self.pat)
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        cases = {
            "title": ("Hi", "at least 5 characters"),
            "description": ("too short", "at least 15 characters"),
            "budget": ("0", "greater than or equal to 1"),
            "preferred_date": (yesterday, "cannot be in the past"),
        }
        for field, (value, message) in cases.items():
            response = self.client.post(reverse("task_create"), self.form_data(**{field: value}))
            self.assertContains(response, message, msg_prefix=field)
        self.assertContains(self.client.post(reverse("task_create"), self.form_data(budget="999999")), "less than or equal to")
        self.assertContains(self.client.post(reverse("task_create"), self.form_data(budget="abc")), "Enter a number")
        self.assertEqual(Task.objects.count(), 0)


class ReadTests(TaskTestCase):
    def test_poster_only_sees_own_tasks(self):
        mine = self.make_task(title="My own task")
        other = self.make_task(poster=self.pam, title="Someone else task")
        self.login(self.pat)
        response = self.client.get(reverse("task_list"))
        self.assertContains(response, "My own task")
        self.assertNotContains(response, "Someone else task")
        self.assertEqual(self.client.get(reverse("task_detail", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("task_detail", args=[mine.pk])).status_code, 200)

    def test_helper_sees_only_open_tasks_and_own_jobs(self):
        open_task = self.make_task(title="Open one")
        taken = self.make_task(title="Taken by hank", status="accepted", helper=self.hank)
        self.login(self.hal)
        response = self.client.get(reverse("task_list"))
        self.assertContains(response, "Open one")
        self.assertNotContains(response, "Taken by hank")
        self.assertEqual(self.client.get(reverse("task_detail", args=[taken.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("task_detail", args=[open_task.pk])).status_code, 200)

    def test_admin_sees_everything(self):
        self.make_task(title="Task A")
        self.make_task(poster=self.pam, title="Task B", status="completed")
        self.login(self.boss)
        response = self.client.get(reverse("task_list"))
        self.assertContains(response, "Task A")
        self.assertContains(response, "Task B")

    def test_search_and_filters(self):
        self.make_task(title="Fix leaking pipe")
        self.make_task(title="Math tutoring", category=Category.objects.get(name="Plumbing"))
        self.login(self.pat)
        self.assertNotContains(self.client.get(reverse("task_list"), {"q": "pipe"}), "Math tutoring")
        plumbing = Category.objects.get(name="Plumbing").pk
        response = self.client.get(reverse("task_list"), {"category": plumbing})
        self.assertContains(response, "Math tutoring")
        self.assertNotContains(response, "Fix leaking pipe")

    def test_contact_numbers_only_shown_to_the_other_party(self):
        task = self.make_task(status="accepted", helper=self.hal)
        self.login(self.hal)
        self.assertContains(self.client.get(reverse("task_detail", args=[task.pk])), "09171111111")
        self.client.logout()
        self.login(self.pat)
        self.assertContains(self.client.get(reverse("task_detail", args=[task.pk])), "09172222222")


class UpdateDeleteTests(TaskTestCase):
    def test_owner_can_edit_open_task(self):
        task = self.make_task()
        self.login(self.pat)
        response = self.client.post(reverse("task_update", args=[task.pk]), self.form_data(title="Fix my desktop PC"), follow=True)
        self.assertContains(response, "Task updated")
        task.refresh_from_db()
        self.assertEqual(task.title, "Fix my desktop PC")

    def test_cannot_edit_someone_elses_task(self):
        task = self.make_task()
        self.login(self.pam)
        self.assertEqual(self.client.post(reverse("task_update", args=[task.pk]), self.form_data(title="Hacked title")).status_code, 404)
        task.refresh_from_db()
        self.assertEqual(task.title, "Fix my laptop")

    def test_cannot_edit_once_accepted(self):
        task = self.make_task(status="accepted", helper=self.hal)
        self.login(self.pat)
        response = self.client.get(reverse("task_update", args=[task.pk]), follow=True)
        self.assertContains(response, "Only open tasks can be edited")

    def test_helper_cannot_edit_or_delete(self):
        task = self.make_task()
        self.login(self.hal)
        self.assertContains(self.client.post(reverse("task_update", args=[task.pk]), self.form_data(), follow=True), "You do not have access")
        self.assertContains(self.client.post(reverse("task_delete", args=[task.pk]), follow=True), "You do not have access")
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_owner_can_delete_open_task(self):
        task = self.make_task()
        self.login(self.pat)
        self.assertContains(self.client.get(reverse("task_delete", args=[task.pk])), "Delete this task?")
        response = self.client.post(reverse("task_delete", args=[task.pk]), follow=True)
        self.assertContains(response, "Task deleted")
        self.assertFalse(Task.objects.exists())

    def test_cannot_delete_other_posters_task(self):
        task = self.make_task()
        self.login(self.pam)
        self.assertEqual(self.client.post(reverse("task_delete", args=[task.pk])).status_code, 404)
        self.assertTrue(Task.objects.exists())

    def test_poster_cannot_delete_accepted_task(self):
        task = self.make_task(status="accepted", helper=self.hal)
        self.login(self.pat)
        response = self.client.post(reverse("task_delete", args=[task.pk]), follow=True)
        self.assertContains(response, "already accepted")
        self.assertTrue(Task.objects.exists())

    def test_admin_can_delete_any_task(self):
        task = self.make_task(status="accepted", helper=self.hal)
        self.login(self.boss)
        self.client.post(reverse("task_delete", args=[task.pk]), follow=True)
        self.assertFalse(Task.objects.exists())

    def test_destructive_actions_require_post(self):
        task = self.make_task()
        self.login(self.pat)
        for name in ("task_cancel", "task_complete"):
            self.assertEqual(self.client.get(reverse(name, args=[task.pk])).status_code, 405)


class WorkflowTests(TaskTestCase):
    def test_full_flow_post_accept_complete(self):
        self.login(self.pat)
        self.client.post(reverse("task_create"), self.form_data())
        task = Task.objects.get()
        self.client.logout()

        self.login(self.hal)
        response = self.client.post(reverse("task_accept", args=[task.pk]), follow=True)
        self.assertContains(response, "You accepted this task")
        task.refresh_from_db()
        self.assertEqual((task.status, task.helper), (Task.Status.ACCEPTED, self.hal))
        self.assertContains(self.client.get(reverse("my_jobs")), "Fix my laptop")
        self.client.logout()

        self.login(self.pat)
        response = self.client.post(reverse("task_complete", args=[task.pk]), follow=True)
        self.assertContains(response, "marked as completed")
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.COMPLETED)

    def test_task_can_only_be_accepted_once(self):
        task = self.make_task()
        self.login(self.hal)
        self.client.post(reverse("task_accept", args=[task.pk]))
        self.client.logout()
        self.login(self.hank)
        response = self.client.post(reverse("task_accept", args=[task.pk]), follow=True)
        self.assertContains(response, "no longer available")
        task.refresh_from_db()
        self.assertEqual(task.helper, self.hal)

    def test_helper_active_task_limit(self):
        for i in range(Task.MAX_ACTIVE_JOBS_PER_HELPER):
            self.make_task(title=f"Active job {i}", status="accepted", helper=self.hal)
        extra = self.make_task(title="One too many")
        self.login(self.hal)
        response = self.client.post(reverse("task_accept", args=[extra.pk]), follow=True)
        self.assertContains(response, "already have 3 active tasks")
        extra.refresh_from_db()
        self.assertIsNone(extra.helper)

    def test_posters_cannot_accept_tasks(self):
        task = self.make_task(poster=self.pam)
        self.login(self.pat)
        self.client.post(reverse("task_accept", args=[task.pk]))
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.OPEN)

    def test_helper_can_withdraw_and_task_reopens(self):
        task = self.make_task(status="accepted", helper=self.hal)
        self.login(self.hal)
        response = self.client.post(reverse("task_withdraw", args=[task.pk]), follow=True)
        self.assertContains(response, "You withdrew")
        task.refresh_from_db()
        self.assertEqual((task.status, task.helper), (Task.Status.OPEN, None))

    def test_helper_cannot_withdraw_from_someone_elses_job(self):
        task = self.make_task(status="accepted", helper=self.hal)
        self.login(self.hank)
        self.assertEqual(self.client.post(reverse("task_withdraw", args=[task.pk])).status_code, 404)

    def test_poster_can_cancel_but_not_complete_an_open_task(self):
        task = self.make_task()
        self.login(self.pat)
        self.assertContains(self.client.post(reverse("task_complete", args=[task.pk]), follow=True), "Only an accepted task")
        self.assertContains(self.client.post(reverse("task_cancel", args=[task.pk]), follow=True), "Task cancelled")
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.CANCELLED)

    def test_other_poster_cannot_cancel_or_complete(self):
        task = self.make_task(status="accepted", helper=self.hal)
        self.login(self.pam)
        self.assertEqual(self.client.post(reverse("task_cancel", args=[task.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("task_complete", args=[task.pk])).status_code, 404)


class DashboardIntegrationTests(TaskTestCase):
    def test_dashboards_show_task_data_and_links(self):
        self.make_task(title="Dashboard task")
        self.login(self.pat)
        response = self.client.get(reverse("poster_dashboard"))
        self.assertContains(response, "Dashboard task")
        self.assertContains(response, reverse("task_create"))
        self.client.logout()
        self.login(self.hal)
        response = self.client.get(reverse("helper_dashboard"))
        self.assertContains(response, reverse("task_list"))
        self.assertContains(response, reverse("my_jobs"))
        self.client.logout()
        self.login(self.boss)
        self.assertContains(self.client.get(reverse("admin_dashboard")), "Dashboard task")

    def test_nav_links_depend_on_role(self):
        self.login(self.hal)
        response = self.client.get(reverse("helper_dashboard"))
        self.assertContains(response, "Find Tasks")
        self.assertNotContains(response, "My Tasks")
