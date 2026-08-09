from django.contrib import admin
from .models import Category, Need, Donation, Notification


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)


@admin.register(Need)
class NeedAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'orphanage', 'category', 'children_count',
        'target_amount', 'collected_amount', 'is_closed', 'created_at'
    )
    list_filter = ('category', 'is_closed')
    search_fields = ('title', 'description', 'orphanage__orphanage_name', 'orphanage__email')
    autocomplete_fields = ['orphanage']


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'donateur', 'need', 'donation_type',
        'amount', 'status', 'created_at'
    )
    list_filter = ('donation_type', 'status')
    search_fields = ('reference', 'donateur__email', 'need__title')
    readonly_fields = ('reference', 'created_at')
    actions = ['mark_as_receptionne']

    @admin.action(description="Marquer les dons sélectionnés comme réceptionnés")
    def mark_as_receptionne(self, request, queryset):
        count = queryset.update(status=Donation.Status.RECEPTIONNE)
        self.message_user(request, f"{count} don(s) marqué(s) comme réceptionné(s).")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'level', 'is_read', 'created_at')
    list_filter = ('level', 'is_read')
    search_fields = ('title', 'message', 'user__email')
