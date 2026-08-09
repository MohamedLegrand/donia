from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def donateur_required(view_func):
    """Restreint l'accès aux utilisateurs authentifiés ayant le rôle Donateur."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_donateur_role:
            messages.error(request, "Cet espace est réservé aux donateurs.")
            return redirect('login_redirect')
        return view_func(request, *args, **kwargs)
    return wrapper


def responsable_required(view_func):
    """Restreint l'accès aux utilisateurs authentifiés ayant le rôle Responsable d'orphelinat."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_responsable_role:
            messages.error(request, "Cet espace est réservé aux responsables d'orphelinat.")
            return redirect('login_redirect')
        return view_func(request, *args, **kwargs)
    return wrapper
