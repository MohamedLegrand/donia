import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.Model):
    """Catégorie de besoin (santé, nutrition, éducation, ...)."""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom")
    icon = models.CharField(
        max_length=50,
        default='tag',
        verbose_name="Icône (Lucide)",
        help_text="Nom de l'icône Lucide utilisée dans l'interface (ex: heart-pulse)."
    )

    class Meta:
        verbose_name = "Catégorie de besoin"
        verbose_name_plural = "Catégories de besoins"
        ordering = ['name']

    def __str__(self):
        return self.name


class Campaign(models.Model):
    """Campagne regroupant plusieurs besoins sous un même objectif (ex : Rentrée scolaire 2026)."""

    orphanage = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='campaigns',
        limit_choices_to={'role': 'responsable'},
        verbose_name="Orphelinat"
    )
    title = models.CharField(max_length=200, verbose_name="Titre de la campagne")
    description = models.TextField(blank=True, verbose_name="Description")
    is_closed = models.BooleanField(default=False, verbose_name="Campagne clôturée")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")

    class Meta:
        verbose_name = "Campagne"
        verbose_name_plural = "Campagnes"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def needs_count(self):
        return self.needs.count()

    @property
    def target_amount_total(self):
        return self.needs.aggregate(total=models.Sum('target_amount'))['total'] or 0

    @property
    def collected_amount_total(self):
        return self.needs.aggregate(total=models.Sum('collected_amount'))['total'] or 0

    @property
    def coverage_percent(self):
        target = self.target_amount_total
        if not target:
            return 0
        return min(100, round((self.collected_amount_total / target) * 100))


class Need(models.Model):
    """Besoin publié par un orphelinat (responsable) et proposé aux donateurs."""

    orphanage = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='needs',
        limit_choices_to={'role': 'responsable'},
        verbose_name="Orphelinat"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='needs',
        verbose_name="Catégorie"
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='needs',
        verbose_name="Campagne associée"
    )
    title = models.CharField(max_length=200, verbose_name="Titre du besoin")
    description = models.TextField(verbose_name="Description détaillée")
    children_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre d'enfants concernés"
    )
    target_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name="Montant cible (FCFA)"
    )
    collected_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Montant collecté (FCFA)"
    )
    is_closed = models.BooleanField(
        default=False,
        verbose_name="Besoin clôturé",
        help_text="Coché lorsque l'orphelinat a confirmé la réception effective du don sur le terrain."
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de publication")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")

    class Meta:
        verbose_name = "Besoin"
        verbose_name_plural = "Besoins"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.orphanage.orphanage_name or self.orphanage})"

    @property
    def coverage_percent(self):
        if not self.target_amount:
            return 0
        return min(100, round((self.collected_amount / self.target_amount) * 100))

    @property
    def is_funded(self):
        return self.collected_amount >= self.target_amount

    @property
    def priority_score(self):
        """
        Score d'urgence calculé automatiquement (0-100) à partir de :
        le nombre d'enfants concernés, l'ancienneté du besoin et son taux de couverture.
        """
        children_factor = min(self.children_count, 100) * 0.3
        days_open = (timezone.now() - self.created_at).days
        age_factor = min(days_open, 30) * 1.2
        coverage_factor = (100 - self.coverage_percent) * 0.4
        score = children_factor + age_factor + coverage_factor
        return round(min(score, 100))

    @property
    def priority_label(self):
        score = self.priority_score
        if score >= 65:
            return "Très urgente"
        elif score >= 35:
            return "Urgente"
        return "Normale"

    @property
    def priority_color(self):
        score = self.priority_score
        if score >= 65:
            return 'red'
        elif score >= 35:
            return 'amber'
        return 'slate'


class NeedPhoto(models.Model):
    """Photo illustrant un besoin (contexte terrain, preuve d'utilisation des dons)."""

    need = models.ForeignKey(Need, on_delete=models.CASCADE, related_name='photos', verbose_name="Besoin")
    image = models.ImageField(upload_to='need_photos/', verbose_name="Photo")
    caption = models.CharField(max_length=200, blank=True, verbose_name="Légende")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")

    class Meta:
        verbose_name = "Photo de besoin"
        verbose_name_plural = "Photos de besoins"
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Photo de {self.need.title}"


class Donation(models.Model):
    """Contribution effectuée par un donateur pour un besoin donné."""

    class DonationType(models.TextChoices):
        FINANCIER = 'financier', 'Don Financier'
        NATURE = 'nature', 'Don en Nature'

    class Status(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente de réception'
        RECEPTIONNE = 'receptionne', 'Réceptionné & Confirmé'

    reference = models.CharField(max_length=30, unique=True, editable=False, verbose_name="Référence")
    donateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='donations',
        limit_choices_to={'role': 'donateur'},
        verbose_name="Donateur"
    )
    need = models.ForeignKey(
        Need,
        on_delete=models.CASCADE,
        related_name='donations',
        verbose_name="Besoin concerné"
    )
    donation_type = models.CharField(
        max_length=20, choices=DonationType.choices,
        default=DonationType.FINANCIER, verbose_name="Type de don"
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="Montant (FCFA)"
    )
    item_description = models.CharField(
        max_length=255, blank=True,
        verbose_name="Description des articles (don en nature)"
    )
    message = models.TextField(blank=True, verbose_name="Message du donateur")
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.EN_ATTENTE, verbose_name="Statut"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date du don")
    received_at = models.DateTimeField(null=True, blank=True, verbose_name="Date de réception confirmée")

    class Meta:
        verbose_name = "Don"
        verbose_name_plural = "Dons"
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"DON-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    @property
    def amount_display(self):
        if self.donation_type == self.DonationType.FINANCIER and self.amount is not None:
            return f"{self.amount:,.0f} FCFA".replace(',', ' ')
        return self.item_description or "Don en nature"


class NeedFollow(models.Model):
    """Suivi (favori) d'un besoin par un donateur, pour être notifié de sa progression."""

    donateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='followed_needs',
        limit_choices_to={'role': 'donateur'},
        verbose_name="Donateur"
    )
    need = models.ForeignKey(Need, on_delete=models.CASCADE, related_name='followers', verbose_name="Besoin")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de suivi")

    class Meta:
        verbose_name = "Besoin suivi"
        verbose_name_plural = "Besoins suivis"
        unique_together = ('donateur', 'need')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.donateur} suit « {self.need.title} »"


class Notification(models.Model):
    """Notification adressée à un utilisateur de la plateforme."""

    class Level(models.TextChoices):
        INFO = 'info', 'Information'
        SUCCESS = 'success', 'Succès'
        WARNING = 'warning', 'Avertissement'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Destinataire"
    )
    title = models.CharField(max_length=150, verbose_name="Titre")
    message = models.CharField(max_length=255, verbose_name="Message")
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INFO, verbose_name="Niveau")
    is_read = models.BooleanField(default=False, verbose_name="Lue")
    link = models.CharField(max_length=255, blank=True, verbose_name="Lien associé")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de réception")

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} → {self.user}"
