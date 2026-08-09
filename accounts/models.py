import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Modèle utilisateur personnalisé avec gestion RBAC pour la plateforme DONIA.
    """
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrateur'
        RESPONSABLE = 'responsable', 'Responsable d\'orphelinat'
        DONATEUR = 'donateur', 'Donateur'

    email = models.EmailField(unique=True, verbose_name="Adresse email")
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.DONATEUR,
        verbose_name="Rôle utilisateur"
    )
    phone = models.CharField(
        max_length=25,
        blank=True,
        null=True,
        verbose_name="Numéro de téléphone"
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Adresse / Ville"
    )
    profile_picture = models.ImageField(
        upload_to='profiles/',
        blank=True,
        null=True,
        verbose_name="Photo de profil"
    )
    
    # Validation pour les comptes responsables d'orphelinats
    is_approved = models.BooleanField(
        default=True,
        verbose_name="Compte approuvé"
    )
    
    # Informations complémentaires d'identification orphelinat à l'inscription
    orphanage_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Nom de l'orphelinat"
    )
    orphanage_document = models.FileField(
        upload_to='orphanage_docs/',
        blank=True,
        null=True,
        verbose_name="Justificatif officiel / Agrément"
    )
    id_card_front = models.ImageField(
        upload_to='responsable_cni/',
        blank=True,
        null=True,
        verbose_name="Carte d'identité (CNI) - Recto"
    )
    id_card_back = models.ImageField(
        upload_to='responsable_cni/',
        blank=True,
        null=True,
        verbose_name="Carte d'identité (CNI) - Verso"
    )
    onboarding_completed = models.BooleanField(
        default=False,
        verbose_name="Profil de l'orphelinat complété",
        help_text="Coché une fois que le responsable a renseigné les informations de sa structure (nom, adresse, justificatif, CNI)."
    )

    # Comptes multiples par structure : un membre d'équipe pointe vers le compte
    # responsable principal (celui qui a complété l'onboarding) et hérite de ses droits.
    organization_owner = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_members',
        limit_choices_to={'role': 'responsable'},
        verbose_name="Responsable principal de l'orphelinat",
        help_text="Si renseigné, ce compte gère l'orphelinat de ce responsable principal en tant que membre d'équipe."
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'inscription")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_responsable_role(self):
        return self.role == self.Role.RESPONSABLE

    @property
    def is_donateur_role(self):
        return self.role == self.Role.DONATEUR

    @property
    def is_team_member(self):
        return self.organization_owner_id is not None

    @property
    def organization_account(self):
        """Le compte qui possède réellement l'orphelinat (soi-même, ou le responsable principal si membre d'équipe)."""
        return self.organization_owner or self


class TeamInvite(models.Model):
    """Invitation permettant à un responsable principal d'ajouter un membre à son équipe."""
    organization_owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='team_invites',
        limit_choices_to={'role': 'responsable'},
        verbose_name="Invité par"
    )
    email = models.EmailField(verbose_name="Email de la personne invitée")
    token = models.CharField(max_length=64, unique=True, editable=False)
    is_used = models.BooleanField(default=False, verbose_name="Utilisée")
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Invitation d'équipe"
        verbose_name_plural = "Invitations d'équipe"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invitation pour {self.email} ({self.organization_owner})"
