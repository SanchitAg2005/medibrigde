from django.urls import path
from . import views

app_name = 'patients'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('book-appointment/', views.book_appointment_page_view, name='book_appointment'),
]
