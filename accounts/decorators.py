from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def role_required(*allowed_roles):
    """Allow only logged-in users with one of the given roles.
    Logged-out users go to the login page; other roles are sent back to their own dashboard."""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                messages.error(request, "You do not have access to that page.")
                return redirect("dashboard")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
