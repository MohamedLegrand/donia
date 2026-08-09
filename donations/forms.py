from django import forms
from .models import Donation, Need

INPUT_CLASSES = (
    "w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-800 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-brand-500 transition-all placeholder:text-slate-400"
)


class DonationForm(forms.ModelForm):
    """Formulaire de contribution à un besoin (financier ou en nature)."""

    class Meta:
        model = Donation
        fields = ['donation_type', 'amount', 'item_description', 'message']
        widgets = {
            'donation_type': forms.RadioSelect(),
            'amount': forms.NumberInput(attrs={
                'class': INPUT_CLASSES, 'placeholder': 'Ex : 25000', 'min': '500', 'step': '500'
            }),
            'item_description': forms.TextInput(attrs={
                'class': INPUT_CLASSES, 'placeholder': 'Ex : 2 cartons de vêtements enfants, 10 kg de riz...'
            }),
            'message': forms.Textarea(attrs={
                'class': INPUT_CLASSES, 'rows': 3,
                'placeholder': "Un mot d'encouragement pour l'orphelinat (optionnel)"
            }),
        }
        labels = {
            'donation_type': 'Type de contribution',
            'amount': 'Montant (FCFA)',
            'item_description': 'Détail des articles',
            'message': 'Message (optionnel)',
        }

    def clean(self):
        cleaned_data = super().clean()
        donation_type = cleaned_data.get('donation_type')
        amount = cleaned_data.get('amount')
        item_description = cleaned_data.get('item_description')

        if donation_type == Donation.DonationType.FINANCIER:
            if not amount or amount <= 0:
                self.add_error('amount', "Veuillez indiquer un montant supérieur à 0 FCFA.")
        elif donation_type == Donation.DonationType.NATURE:
            if not item_description:
                self.add_error('item_description', "Veuillez décrire les articles que vous souhaitez donner.")

        return cleaned_data


class NeedForm(forms.ModelForm):
    """Formulaire de publication / modification d'un besoin par un responsable d'orphelinat."""

    class Meta:
        model = Need
        fields = ['category', 'title', 'description', 'children_count', 'target_amount']
        widgets = {
            'category': forms.Select(attrs={'class': INPUT_CLASSES}),
            'title': forms.TextInput(attrs={
                'class': INPUT_CLASSES, 'placeholder': 'Ex : Médicaments de première nécessité'
            }),
            'description': forms.Textarea(attrs={
                'class': INPUT_CLASSES, 'rows': 5,
                'placeholder': 'Décrivez précisément le besoin, les quantités et le délai souhaité...'
            }),
            'children_count': forms.NumberInput(attrs={
                'class': INPUT_CLASSES, 'placeholder': 'Ex : 25', 'min': '0'
            }),
            'target_amount': forms.NumberInput(attrs={
                'class': INPUT_CLASSES, 'placeholder': 'Ex : 250000', 'min': '1000', 'step': '500'
            }),
        }
        labels = {
            'category': 'Catégorie',
            'title': 'Titre du besoin',
            'description': 'Description détaillée',
            'children_count': "Nombre d'enfants concernés",
            'target_amount': 'Montant cible (FCFA)',
        }

    def clean_target_amount(self):
        target_amount = self.cleaned_data.get('target_amount')
        if target_amount is not None and target_amount <= 0:
            raise forms.ValidationError("Le montant cible doit être supérieur à 0 FCFA.")
        return target_amount
