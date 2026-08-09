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
    """Restreint l'accès aux utilisateurs authentifiés ayant le rôle Responsable d'orphelinat.

    N'exige pas que le compte soit déjà validé par un administrateur : utilisé pour la
    vue d'ensemble, seule page accessible tant que le compte est en attente de validation.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_responsable_role:
            messages.error(request, "Cet espace est réservé aux responsables d'orphelinat.")
            return redirect('login_redirect')
        return view_func(request, *args, **kwargs)
    return wrapper


def approved_responsable_required(view_func):
    """Comme responsable_required, mais bloque en plus les comptes en attente de validation."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_responsable_role:
            messages.error(request, "Cet espace est réservé aux responsables d'orphelinat.")
            return redirect('login_redirect')
        if not request.user.organization_account.is_approved:
            messages.info(
                request,
                "Votre compte est en attente de validation par un administrateur. "
                "Cette fonctionnalité sera accessible dès que votre compte sera validé."
            )
            return redirect('orphelinat_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
