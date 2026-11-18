from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import TaskFilterForm, TaskForm
from .models import Task

POSTER, HELPER, ADMIN = User.Role.POSTER, User.Role.HELPER, User.Role.ADMIN


def visible_tasks(user):
    """Ownership / role rules: which tasks may this user see?"""
    if user.role == ADMIN:
        return Task.objects.all()
    if user.role == POSTER:
        return Task.objects.filter(poster=user)  # posters only see their own tasks
    return Task.objects.filter(Q(status=Task.Status.OPEN) | Q(helper=user))  # helpers: open tasks + their own jobs


def active_job_count(helper):
    return Task.objects.filter(helper=helper, status=Task.Status.ACCEPTED).count()


# ---------------------------------------------------------------- READ
@role_required(POSTER, HELPER, ADMIN)
def task_list(request):
    """Posters: my tasks. Helpers: open tasks to browse. Admin: every task."""
    tasks = Task.objects.select_related("category", "poster", "helper")
    if request.user.role == POSTER:
        tasks = tasks.filter(poster=request.user)
        heading = "My tasks"
    elif request.user.role == HELPER:
        tasks = tasks.filter(status=Task.Status.OPEN)
        heading = "Available tasks"
    else:
        heading = "All tasks"

    filter_form = TaskFilterForm(request.GET)
    if filter_form.is_valid():
        data = filter_form.cleaned_data
        if data["q"]:
            q = data["q"].strip()
            tasks = tasks.filter(
                Q(title__icontains=q) | Q(description__icontains=q) | Q(location_area__icontains=q)
            )
        if data["category"]:
            tasks = tasks.filter(category=data["category"])
        if data["status"] and request.user.role != HELPER:
            tasks = tasks.filter(status=data["status"])

    page = Paginator(tasks, 8).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    context = {
        "page": page,
        "filter_form": filter_form,
        "heading": heading,
        "querystring": params.urlencode(),
    }
    return render(request, "tasks/list.html", context)


@role_required(HELPER)
def my_jobs(request):
    """A helper's accepted tasks (current) and finished ones (history)."""
    mine = Task.objects.filter(helper=request.user).select_related("category", "poster")
    context = {
        "active_jobs": mine.filter(status=Task.Status.ACCEPTED),
        "past_jobs": mine.exclude(status=Task.Status.ACCEPTED),
        "max_jobs": Task.MAX_ACTIVE_JOBS_PER_HELPER,
    }
    return render(request, "tasks/my_jobs.html", context)


@role_required(POSTER, HELPER, ADMIN)
def task_detail(request, pk):
    task = get_object_or_404(visible_tasks(request.user).select_related("category", "poster", "helper"), pk=pk)
    user = request.user
    is_owner = task.poster_id == user.id
    context = {
        "task": task,
        "can_edit": is_owner and task.is_open,
        "can_cancel": is_owner and task.status in (Task.Status.OPEN, Task.Status.ACCEPTED),
        "can_complete": is_owner and task.is_accepted,
        "can_delete": user.role == ADMIN or (is_owner and not task.is_accepted),
        "can_accept": user.role == HELPER and task.is_open,
        "can_withdraw": user.role == HELPER and task.helper_id == user.id and task.is_accepted,
        "jobs_left": Task.MAX_ACTIVE_JOBS_PER_HELPER - active_job_count(user) if user.role == HELPER else None,
    }
    return render(request, "tasks/detail.html", context)


# ---------------------------------------------------------------- CREATE
@role_required(POSTER)
def task_create(request):
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.poster = request.user  # record is linked to the logged-in user
            task.save()
            messages.success(request, "Your task was posted. Helpers can now see it.")
            return redirect(task)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = TaskForm(initial={"location_area": request.user.location_area})
    return render(request, "tasks/form.html", {"form": form, "heading": "Post a task", "submit_label": "Post task"})


# ---------------------------------------------------------------- UPDATE
@role_required(POSTER)
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk, poster=request.user)  # only your own tasks
    if not task.is_open:
        messages.error(request, "Only open tasks can be edited. Once a helper accepts, the details are locked.")
        return redirect(task)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated.")
            return redirect(task)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = TaskForm(instance=task)
    return render(
        request, "tasks/form.html", {"form": form, "heading": "Edit task", "submit_label": "Save changes", "task": task}
    )


@role_required(POSTER)
@require_POST
def task_cancel(request, pk):
    task = get_object_or_404(Task, pk=pk, poster=request.user)
    if task.status not in (Task.Status.OPEN, Task.Status.ACCEPTED):
        messages.error(request, "This task can no longer be cancelled.")
    else:
        task.status = Task.Status.CANCELLED
        task.save()
        messages.success(request, "Task cancelled.")
    return redirect(task)


@role_required(POSTER)
@require_POST
def task_complete(request, pk):
    task = get_object_or_404(Task, pk=pk, poster=request.user)
    if not task.is_accepted:
        messages.error(request, "Only an accepted task can be marked as completed.")
    else:
        task.status = Task.Status.COMPLETED
        task.save()
        messages.success(request, "Task marked as completed. Thank you for using MendMate!")
    return redirect(task)


# ---------------------------------------------------------------- DELETE
@role_required(POSTER, ADMIN)
def task_delete(request, pk):
    if request.user.role == ADMIN:
        task = get_object_or_404(Task, pk=pk)  # admin moderation: any task
    else:
        task = get_object_or_404(Task, pk=pk, poster=request.user)
        if task.is_accepted:
            messages.error(request, "A helper already accepted this task. Cancel it first if you no longer need it.")
            return redirect(task)
    if request.method == "POST":
        task.delete()
        messages.success(request, "Task deleted.")
        return redirect("task_list")
    return render(request, "tasks/confirm_delete.html", {"task": task})


# ---------------------------------------------------------------- HELPER ACTIONS
@role_required(HELPER)
@require_POST
def task_accept(request, pk):
    with transaction.atomic():
        # lock the helper row and the task row so two requests cannot break the rules at the same time
        User.objects.select_for_update().get(pk=request.user.pk)
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if not task.is_open:
            messages.error(request, "Sorry, this task is no longer available.")
            return redirect("task_list")
        if active_job_count(request.user) >= Task.MAX_ACTIVE_JOBS_PER_HELPER:
            messages.error(
                request,
                f"You already have {Task.MAX_ACTIVE_JOBS_PER_HELPER} active tasks. Finish one before accepting another.",
            )
            return redirect(task)
        task.helper = request.user
        task.status = Task.Status.ACCEPTED
        task.save()
    messages.success(request, "You accepted this task. Contact the poster to arrange the details.")
    return redirect(task)


@role_required(HELPER)
@require_POST
def task_withdraw(request, pk):
    task = get_object_or_404(Task, pk=pk, helper=request.user)  # only tasks you accepted
    if not task.is_accepted:
        messages.error(request, "You can only withdraw from a task that is still in progress.")
    else:
        task.helper = None
        task.status = Task.Status.OPEN  # goes back to the board for other helpers
        task.save()
        messages.success(request, "You withdrew from the task. It is open for other helpers again.")
    return redirect("my_jobs")
