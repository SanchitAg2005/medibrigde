from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from doctors.models import DoctorProfile
from appointments.models import Booking, AvailabilitySlot
from medical_records.models import MedicalReport
from calendar_sync.models import GoogleOAuthToken
from accounts.models import CustomUser

@login_required
def dashboard_view(request):
    if request.user.role != 'PATIENT':
        return redirect('dashboard')

    # Fetch user's bookings
    user_bookings = Booking.objects.filter(patient=request.user)
    
    # Exclude cancelled from Upcoming
    upcoming_appointments = user_bookings.filter(
        slot__start_datetime__gte=timezone.now(),
        slot__status__in=['BOOKED', 'IN_CONSULTATION']
    ).order_by('slot__start_datetime')
    
    # Recent / history: completed, cancelled, no-show, or past date
    past_appointments = user_bookings.filter(
        Q(slot__start_datetime__lt=timezone.now()) | Q(slot__status__in=['CANCELLED', 'COMPLETED', 'NO_SHOW'])
    ).distinct().order_by('-slot__start_datetime')
    
    # Patient medical reports
    medical_reports = MedicalReport.objects.filter(patient=request.user).order_by('-uploaded_at')
    
    # Check Google Calendar Connection
    has_calendar_connected = GoogleOAuthToken.objects.filter(user=request.user).exists()
    
    # Quick statistics
    completed_count = user_bookings.filter(slot__status='COMPLETED').count()
    upcoming_count = upcoming_appointments.count()
    reports_count = medical_reports.count()
    
    context = {
        'upcoming_appointments': upcoming_appointments,
        'past_appointments': past_appointments,
        'medical_reports': medical_reports,
        'has_calendar_connected': has_calendar_connected,
        'completed_count': completed_count,
        'upcoming_count': upcoming_count,
        'reports_count': reports_count,
    }
    return render(request, 'patients/dashboard.html', context)

@login_required
def book_appointment_page_view(request):
    if request.user.role != 'PATIENT':
        return redirect('dashboard')

    # Active doctors for booking wizard (only APPROVED status)
    doctors = DoctorProfile.objects.filter(user__approval_status=CustomUser.ApprovalStatus.APPROVED)
    
    # Preload available slots for booking wizard (only for APPROVED doctors)
    available_slots = AvailabilitySlot.objects.filter(
        status='AVAILABLE', 
        start_datetime__gte=timezone.now(),
        doctor__user__approval_status=CustomUser.ApprovalStatus.APPROVED
    ).order_by('start_datetime')
    
    context = {
        'doctors': doctors,
        'available_slots': available_slots,
    }
    return render(request, 'patients/book_appointment.html', context)

