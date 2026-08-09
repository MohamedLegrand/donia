from django.urls import path
from . import views_orphelinat as views

urlpatterns = [
    path('', views.orphelinat_dashboard_view, name='orphelinat_dashboard'),
    path('besoins/', views.my_needs_view, name='my_needs'),
    path('besoins/nouveau/', views.need_create_view, name='need_create'),
    path('besoins/<int:pk>/modifier/', views.need_edit_view, name='need_edit'),
    path('besoins/<int:pk>/supprimer/', views.need_delete_view, name='need_delete'),
    path('besoins/<int:pk>/cloturer/', views.need_toggle_close_view, name='need_toggle_close'),
    path('dons/', views.received_donations_view, name='received_donations'),
    path('dons/<int:pk>/valider/', views.validate_donation_view, name='validate_donation'),
    path('statistiques/', views.statistics_view, name='orphelinat_statistics'),
    path('rapports/', views.reports_view, name='orphelinat_reports'),
    path('rapports/telecharger/', views.download_report_view, name='download_report'),
]
