from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_choice_view, name='register_choice'),
    path('register/donateur/', views.register_donateur_view, name='register_donateur'),
    path('register/responsable/', views.register_responsable_view, name='register_responsable'),
    path('equipe/rejoindre/<str:token>/', views.team_invite_accept_view, name='team_invite_accept'),
    path('redirect/', views.login_redirect_view, name='login_redirect'),
    path('profile/', views.profile_view, name='profile'),
]
