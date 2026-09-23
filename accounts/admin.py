from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'email', 'username', 'first_name', 'last_name', 
        'role', 'is_approved', 'is_staff', 'date_joined'
    )
    list_filter = ('role', 'is_approved', 'is_staff', 'is_active')
    search_fields = ('email', 'username', 'first_name', 'last_name', 'orphanage_name', 'phone')
    ordering = ('-date_joined',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Informations Rôle & Orphelink', {
            'fields': (
                'role', 'phone', 'address', 'profile_picture', 
                'is_approved', 'orphanage_name', 'orphanage_document'
            )
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informations Rôle & Orphelink', {
            'fields': (
                'email', 'role', 'phone', 'address', 
                'is_approved', 'orphanage_name'
            )
        }),
    )

    actions = ['approve_responsables', 'disapprove_responsables']

    @admin.action(description="Approuver la validation des comptes sélectionnés")
    def approve_responsables(self, request, queryset):
        count = queryset.update(is_approved=True)
        self.message_user(request, f"{count} compte(s) utilisateur(s) approuvé(s) avec succès.")

    @admin.action(description="Suspendre / Désapprouver les comptes sélectionnés")
    def disapprove_responsables(self, request, queryset):
        count = queryset.update(is_approved=False)
        self.message_user(request, f"{count} compte(s) utilisateur(s) suspendu(s) / mis en attente.")
