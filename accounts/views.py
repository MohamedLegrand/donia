from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .forms import (
    EmailAuthenticationForm,
    DonateurRegistrationForm,
    ResponsableRegistrationForm,
    UserProfileUpdateForm,
    ResponsableProfileUpdateForm,
    TeamMemberJoinForm
)
from .models import User, TeamInvite


def home_view(request):
    """Page d'accueil de la plateforme DONIA."""
    return render(request, 'accounts/home.html')


def register_choice_view(request):
    """Page de sélection du type de compte à créer."""
    if request.user.is_authenticated:
        return redirect('login_redirect')
    return render(request, 'accounts/register_choice.html')


def register_donateur_view(request):
    """Inscription Donateur avec redirection vers la page de connexion."""
    if request.user.is_authenticated:
        return redirect('login_redirect')

    if request.method == 'POST':
        form = DonateurRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Félicitations {user.first_name} ! Votre compte Donateur a été créé avec succès. Veuillez renseigner vos identifiants pour vous connecter."
            )
            return redirect('login')
    else:
        form = DonateurRegistrationForm()

    return render(request, 'accounts/register_donateur.html', {'form': form})


def register_responsable_view(request):
    """Inscription Responsable d'orphelinat avec validation manuelle."""
    if request.user.is_authenticated:
        return redirect('login_redirect')

    if request.method == 'POST':
        form = ResponsableRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Bienvenue {user.first_name} ! Votre compte a été créé avec succès. "
                "Connectez-vous pour compléter le profil de votre orphelinat."
            )
            return redirect('login')
    else:
        form = ResponsableRegistrationForm()

    return render(request, 'accounts/register_responsable.html', {'form': form})


def team_invite_accept_view(request, token):
    """Création de compte pour un membre d'équipe à partir d'un lien d'invitation."""
    if request.user.is_authenticated:
        return redirect('login_redirect')

    invite = get_object_or_404(TeamInvite, token=token)

    if invite.is_used:
        messages.error(request, "Ce lien d'invitation a déjà été utilisé.")
        return redirect('login')

    if request.method == 'POST':
        form = TeamMemberJoinForm(request.POST)
        if form.is_valid():
            user = form.save(organization_owner=invite.organization_owner)
            invite.is_used = True
            invite.accepted_at = timezone.now()
            invite.save(update_fields=['is_used', 'accepted_at'])
            messages.success(
                request,
                f"Bienvenue {user.first_name} ! Vous avez rejoint l'équipe de "
                f"« {invite.organization_owner.orphanage_name or invite.organization_owner} »."
            )
            return redirect('login')
    else:
        form = TeamMemberJoinForm(initial={'email': invite.email})

    return render(request, 'accounts/team_invite_accept.html', {'form': form, 'invite': invite})


def login_view(request):
    """Vue de connexion avec redirection basée sur le rôle."""
    if request.user.is_authenticated:
        return redirect('login_redirect')

    if request.method == 'POST':
        form = EmailAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Ravi de vous revoir, {user.first_name or user.username} !")
            
            # Redirection vers la page suivante si demandée
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('login_redirect')
    else:
        form = EmailAuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Déconnexion de l'utilisateur."""
    logout(request)
    messages.info(request, "Vous avez été déconnecté avec succès.")
    return redirect('login')


@login_required
def login_redirect_view(request):
    """Redirection intelligente selon le rôle de l'utilisateur."""
    user = request.user
    if user.is_superuser or user.role == User.Role.ADMIN:
        return redirect('admin_dashboard')
    elif user.role == User.Role.RESPONSABLE:
        return redirect('orphelinat_dashboard')
    else:
        return redirect('donateur_dashboard')


@login_required
def profile_view(request):
    """Consultation et modification du profil utilisateur (formulaire et template adaptés au rôle)."""
    if request.user.is_responsable_role:
        if request.user.is_team_member:
            form_class = UserProfileUpdateForm
            template_name = 'donations/orphelinat_profile.html'
        elif not request.user.onboarding_completed:
            return redirect('orphanage_onboarding')
        else:
            form_class = ResponsableProfileUpdateForm
            template_name = 'donations/orphelinat_profile.html'
    elif request.user.is_donateur_role:
        form_class = UserProfileUpdateForm
        template_name = 'donations/profile.html'
    else:
        form_class = UserProfileUpdateForm
        template_name = 'accounts/profile.html'

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour avec succès.")
            return redirect('profile')
    else:
        form = form_class(instance=request.user)

    return render(request, template_name, {'form': form})
