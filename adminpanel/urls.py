from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard_view, name='admin_dashboard'),

    path('utilisateurs/', views.users_list_view, name='admin_users'),
    path('utilisateurs/<int:pk>/basculer/', views.user_toggle_active_view, name='admin_user_toggle_active'),

    path('validations/', views.pending_approvals_view, name='admin_pending_approvals'),
    path('validations/<int:pk>/approuver/', views.approve_account_view, name='admin_approve_account'),
    path('validations/<int:pk>/rejeter/', views.reject_account_view, name='admin_reject_account'),

    path('orphelinats/', views.orphanages_list_view, name='admin_orphanages'),

    path('categories/', views.categories_list_view, name='admin_categories'),
    path('categories/nouvelle/', views.category_create_view, name='admin_category_create'),
    path('categories/<int:pk>/modifier/', views.category_edit_view, name='admin_category_edit'),
    path('categories/<int:pk>/supprimer/', views.category_delete_view, name='admin_category_delete'),

    path('dons/', views.donations_supervision_view, name='admin_donations'),

    path('statistiques/', views.admin_statistics_view, name='admin_statistics'),

    path('notifications/', views.notifications_management_view, name='admin_notifications'),

    path('rapports/', views.admin_reports_view, name='admin_reports'),
    path('rapports/telecharger/', views.download_admin_report_view, name='admin_download_report'),

    path('sauvegarde/', views.backup_view, name='admin_backup'),
    path('sauvegarde/telecharger/', views.download_backup_view, name='admin_download_backup'),
]
