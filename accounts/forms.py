from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()

# Classes Tailwind standard pour tous les champs d'input
INPUT_CLASSES = (
    "w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-800 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-donia-400 focus:border-donia-500 transition-all placeholder:text-slate-400 pr-10"
)
FILE_INPUT_CLASSES = (
    "w-full px-3 py-2 text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg "
    "file:border-0 file:text-xs file:font-bold file:bg-donia-50 file:text-donia-700 hover:file:bg-donia-100 cursor-pointer"
)


class EmailAuthenticationForm(forms.Form):
    """Formulaire de connexion par Adresse Email et Mot de passe."""
    email = forms.EmailField(
        label="Adresse Email",
        widget=forms.EmailInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'ex: contact@exemple.com',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': '••••••••'
        })
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        if email and password:
            try:
                user_obj = User.objects.get(email__iexact=email)
                auth_username = user_obj.username
            except User.DoesNotExist:
                auth_username = email

            self.user_cache = authenticate(self.request, username=auth_username, password=password)
            if self.user_cache is None:
                raise ValidationError(
                    "Adresse email ou mot de passe incorrect. Veuillez vérifier vos identifiants.",
                    code='invalid_login'
                )
            else:
                self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError("Ce compte a été désactivé.", code='inactive')
        if user.is_responsable_role and not user.is_approved and not user.is_superuser:
            raise ValidationError(
                "Votre compte Responsable d'orphelinat est en cours de vérification par un administrateur. Vous recevrez un accès dès validation.",
                code='pending_approval'
            )

    def get_user(self):
        return self.user_cache


class DonateurRegistrationForm(forms.ModelForm):
    """Formulaire d'inscription pour les donateurs (sans champ adresse/quartier)."""
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Au moins 8 caractères'})
    )
    password_confirm = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Répétez le mot de passe'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Votre prénom'}),
            'last_name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Votre nom'}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'exemple@email.com'}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': '+221 77 000 00 00'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Un compte avec cette adresse email existe déjà.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Les deux mots de passe ne correspondent pas.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.DONATEUR
        user.is_approved = True
        user.username = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class ResponsableRegistrationForm(forms.ModelForm):
    """Formulaire d'inscription pour les responsables d'orphelinats."""
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Au moins 8 caractères'})
    )
    password_confirm = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Répétez le mot de passe'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'address', 'orphanage_name', 'orphanage_document']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Prénom du responsable'}),
            'last_name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Nom du responsable'}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'contact@orphelinat.org'}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Numéro officiel'}),
            'address': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Adresse géographique'}),
            'orphanage_name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Nom officiel de l\'orphelinat'}),
            'orphanage_document': forms.FileInput(attrs={'class': FILE_INPUT_CLASSES}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Un compte avec cette adresse email existe déjà.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Les deux mots de passe ne correspondent pas.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.RESPONSABLE
        user.is_approved = False
        user.username = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class UserProfileUpdateForm(forms.ModelForm):
    """Formulaire de mise à jour du profil."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'address', 'profile_picture']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'last_name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'address': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'profile_picture': forms.FileInput(attrs={'class': FILE_INPUT_CLASSES}),
        }


class ResponsableProfileUpdateForm(forms.ModelForm):
    """Formulaire de mise à jour du profil pour un responsable d'orphelinat (inclut les infos de la structure)."""
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone', 'address', 'profile_picture',
            'orphanage_name', 'orphanage_document'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'last_name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'address': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'profile_picture': forms.FileInput(attrs={'class': FILE_INPUT_CLASSES}),
            'orphanage_name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'orphanage_document': forms.FileInput(attrs={'class': FILE_INPUT_CLASSES}),
        }
        labels = {
            'orphanage_name': "Nom officiel de l'orphelinat",
            'orphanage_document': 'Justificatif officiel / Agrément',
        }
