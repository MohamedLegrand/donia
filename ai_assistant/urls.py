from django.urls import path

from . import views

urlpatterns = [
    path('chat/', views.chat_message_view, name='ai_chat_message'),
]
