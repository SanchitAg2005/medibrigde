from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('health/', views.health_check, name='health_check'),
]
