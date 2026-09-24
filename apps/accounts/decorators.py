from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def administrator_required(view_func):
    """Decorator that ensures user is logged in and has Administrator role."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_administrator:
            messages.error(request, 'Administrator access required.')
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    return _wrapped
