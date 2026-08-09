from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def admin_required(view_func):
    """Restreint l'accès aux utilisateurs authentifiés ayant le rôle Administrateur (ou superuser)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_admin_role:
            messages.error(request, "Cet espace est réservé aux administrateurs.")
            return redirect('login_redirect')
        return view_func(request, *args, **kwargs)
    return wrapper
