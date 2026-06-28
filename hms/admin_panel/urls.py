from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('doctor/<int:pk>/', views.doctor_detail_view, name='doctor_detail'),
    path('doctor/<int:pk>/approve/', views.approve_doctor_view, name='approve_doctor'),
    path('doctor/<int:pk>/reject/', views.reject_doctor_view, name='reject_doctor'),
    path('doctor/<int:pk>/suspend/', views.suspend_doctor_view, name='suspend_doctor'),
    path('doctor/<int:pk>/reactivate/', views.reactivate_doctor_view, name='reactivate_doctor'),
    path('doctor/<int:pk>/remove/', views.remove_doctor_view, name='remove_doctor'),
    path('doctor/<int:pk>/edit/', views.admin_edit_doctor_view, name='admin_edit_doctor'),
    path('doctor/<int:pk>/working-hours/', views.admin_manage_working_hours_view, name='admin_manage_working_hours'),
    path('doctor/<int:pk>/leaves/', views.admin_manage_leaves_view, name='admin_manage_leaves'),
    path('hospital-config/edit/', views.edit_hospital_config_view, name='edit_hospital_config'),
]
