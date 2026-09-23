from django.urls import path
from . import views_orphelinat as views

urlpatterns = [
    path('', views.orphelinat_dashboard_view, name='orphelinat_dashboard'),
    path('onboarding/', views.orphanage_onboarding_view, name='orphanage_onboarding'),
    path('equipe/', views.team_view, name='team_manage'),
    path('equipe/<int:pk>/retirer/', views.team_remove_member_view, name='team_remove_member'),
    path('besoins/', views.my_needs_view, name='my_needs'),
    path('besoins/nouveau/', views.need_create_view, name='need_create'),
    path('besoins/generer-description/', views.need_generate_description_view, name='need_generate_description'),
    path('besoins/<int:pk>/modifier/', views.need_edit_view, name='need_edit'),
    path('besoins/<int:pk>/supprimer/', views.need_delete_view, name='need_delete'),
    path('besoins/<int:pk>/cloturer/', views.need_toggle_close_view, name='need_toggle_close'),
    path('besoins/<int:pk>/photos/', views.need_photos_view, name='need_photos'),
    path('besoins/<int:pk>/photos/<int:photo_pk>/supprimer/', views.need_photo_delete_view, name='need_photo_delete'),
    path('campagnes/', views.campaigns_list_view, name='campaigns_list'),
    path('campagnes/nouvelle/', views.campaign_create_view, name='campaign_create'),
    path('campagnes/<int:pk>/modifier/', views.campaign_edit_view, name='campaign_edit'),
    path('campagnes/<int:pk>/supprimer/', views.campaign_delete_view, name='campaign_delete'),
    path('campagnes/<int:pk>/cloturer/', views.campaign_toggle_close_view, name='campaign_toggle_close'),
    path('dons/', views.received_donations_view, name='received_donations'),
    path('dons/<int:pk>/valider/', views.validate_donation_view, name='validate_donation'),
    path('statistiques/', views.statistics_view, name='orphelinat_statistics'),
    path('rapports/', views.reports_view, name='orphelinat_reports'),
    path('rapports/telecharger/', views.download_report_view, name='download_report'),
]
