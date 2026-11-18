from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from .decorators import role_required
from .forms import ProfileForm, RegistrationForm
from .models import User
from tasks.models import Task

def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "home.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created successfully! You can now log in.")
            return redirect("login")
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


class MendMateLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Welcome back, {form.get_user().display_name()}!")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username or password. Please try again.")
        return super().form_invalid(form)


@require_POST
def logout_view(request):
    logout(request)  # ends the session
    messages.success(request, "You have been logged out.")
    return redirect("login")

@login_required
def dashboard(request):
    """Send each user to the dashboard for their role."""
    targets = {
        User.Role.ADMIN: "admin_dashboard",
        User.Role.POSTER: "poster_dashboard",
        User.Role.HELPER: "helper_dashboard",
    }
    return redirect(targets[request.user.role])


@role_required(User.Role.POSTER)
def poster_dashboard(request):
    mine = Task.objects.filter(poster=request.user)
    context = {
        "open_count": mine.filter(status=Task.Status.OPEN).count(),
        "accepted_count": mine.filter(status=Task.Status.ACCEPTED).count(),
        "completed_count": mine.filter(status=Task.Status.COMPLETED).count(),
        "recent_tasks": mine.select_related("category", "helper")[:5],
    }
    return render(request, "dashboards/poster.html", context)


@role_required(User.Role.HELPER)
def helper_dashboard(request):
    skills = [s.strip() for s in request.user.skills.split(",") if s.strip()]
    my_jobs = Task.objects.filter(helper=request.user)
    context = {
        "skills": skills,
        "open_count": Task.objects.filter(status=Task.Status.OPEN).count(),
        "active_jobs": my_jobs.filter(status=Task.Status.ACCEPTED).select_related("category", "poster")[:5],
        "active_count": my_jobs.filter(status=Task.Status.ACCEPTED).count(),
        "completed_count": my_jobs.filter(status=Task.Status.COMPLETED).count(),
        "max_jobs": Task.MAX_ACTIVE_JOBS_PER_HELPER,
    }
    return render(request, "dashboards/helper.html", context)


@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    context = {
        "total_users": User.objects.count(),
        "poster_count": User.objects.filter(role=User.Role.POSTER).count(),
        "helper_count": User.objects.filter(role=User.Role.HELPER).count(),
        "recent_users": User.objects.order_by("-date_joined")[:8],
        "task_total": Task.objects.count(),
        "task_open": Task.objects.filter(status=Task.Status.OPEN).count(),
        "task_accepted": Task.objects.filter(status=Task.Status.ACCEPTED).count(),
        "task_completed": Task.objects.filter(status=Task.Status.COMPLETED).count(),
        "recent_tasks": Task.objects.select_related("category", "poster")[:5],
    }
    return render(request, "dashboards/admin.html", context)


@login_required
def profile(request):
    return render(request, "accounts/profile.html", {"profile_user": request.user})  # always your own profile


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)  # only your own record
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile was updated.")
            return redirect("profile")
        messages.error(request, "Please fix the errors below.")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})
