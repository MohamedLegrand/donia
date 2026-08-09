from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_overview_view, name='donateur_dashboard'),
    path('besoins/', views.needs_list_view, name='needs_list'),
    path('besoins/<int:pk>/', views.need_detail_view, name='need_detail'),
    path('besoins/<int:pk>/don/', views.make_donation_view, name='make_donation'),
    path('besoins/<int:pk>/suivre/', views.toggle_follow_need_view, name='toggle_follow_need'),
    path('favoris/', views.followed_needs_view, name='followed_needs'),
    path('campagnes/<int:pk>/', views.campaign_public_detail_view, name='campaign_public_detail'),
    path('dons/', views.donation_history_view, name='donation_history'),
    path('dons/<int:pk>/recu/', views.download_receipt_view, name='download_receipt'),
    path('notifications/', views.notifications_list_view, name='notifications_list'),
]
