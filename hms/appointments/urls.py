from django.urls import path
from . import views

app_name = 'appointments'

urlpatterns = [
    path('book/<int:slot_id>/', views.book_appointment_view, name='book_slot'),
    path('cancel/<uuid:booking_id>/', views.cancel_booking_view, name='cancel_booking'),
    path('start-consultation/<uuid:booking_id>/', views.start_consultation_view, name='start_consultation'),
    path('mark-no-show/<uuid:booking_id>/', views.mark_no_show_view, name='mark_no_show'),
    path('detail-json/<uuid:booking_id>/', views.booking_detail_json_view, name='booking_detail_json'),
]
