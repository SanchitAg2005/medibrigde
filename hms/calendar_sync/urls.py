from django.urls import path
from . import views

app_name = 'calendar_sync'

urlpatterns = [
    path('connect/', views.google_oauth_redirect_view, name='connect'),
    path('callback/', views.google_oauth_callback_view, name='callback'),
]
