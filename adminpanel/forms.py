from django import forms
from donations.models import Category

INPUT_CLASSES = (
    "w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-800 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-brand-500 transition-all placeholder:text-slate-400"
)

# Sélection restreinte à des icônes Lucide déjà utilisées dans la plateforme, pour garder une identité visuelle cohérente.
ICON_CHOICES = [
    ('heart-pulse', 'heart-pulse — Santé'),
    ('utensils', 'utensils — Alimentation'),
    ('graduation-cap', 'graduation-cap — Éducation'),
    ('shirt', 'shirt — Vêtements'),
    ('home', 'home — Logement'),
    ('book-open', 'book-open — Livres'),
    ('droplets', 'droplets — Eau & Hygiène'),
    ('tag', 'tag — Générique'),
]


class CategoryForm(forms.ModelForm):
    """Formulaire de gestion des catégories de besoins."""

    icon = forms.ChoiceField(
        choices=ICON_CHOICES, label="Icône",
        widget=forms.Select(attrs={'class': INPUT_CLASSES})
    )

    class Meta:
        model = Category
        fields = ['name', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ex : Santé & Médicaments'}),
        }
        labels = {'name': 'Nom de la catégorie'}
