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
