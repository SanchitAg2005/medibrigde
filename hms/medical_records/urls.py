from django.urls import path
from . import views

app_name = 'medical_records'

urlpatterns = [
    path('create/<uuid:booking_id>/', views.create_medical_record_view, name='create_record'),
    path('upload-report/', views.upload_report_view, name='upload_report'),
]
