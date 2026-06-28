from django.urls import path
from . import views

app_name = 'doctors'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('submit-review/<uuid:booking_id>/', views.submit_review_view, name='submit_review'),
    path('working-hours/configure/', views.configure_working_hours_view, name='configure_working_hours'),
]
