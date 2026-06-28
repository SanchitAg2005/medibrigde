from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.models import CustomUser
from common.models import AsyncTask, AuditLog

def admin_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_superuser and request.user.role != CustomUser.Roles.ADMIN:
            messages.error(request, "Access denied. Administrator privileges required.")
            return redirect('landing')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

import socket
import requests
import datetime
from django.db import connection
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum
from appointments.models import Booking, AvailabilitySlot

@admin_required
def dashboard_view(request):
    # Fetch pending, approved, and rejected doctors separately
    pending_doctors = CustomUser.objects.filter(role=CustomUser.Roles.DOCTOR, approval_status=CustomUser.ApprovalStatus.PENDING)
    approved_doctors = CustomUser.objects.filter(role=CustomUser.Roles.DOCTOR, approval_status=CustomUser.ApprovalStatus.APPROVED)
    rejected_doctors = CustomUser.objects.filter(role=CustomUser.Roles.DOCTOR, approval_status=CustomUser.ApprovalStatus.REJECTED)
    suspended_doctors = CustomUser.objects.filter(role=CustomUser.Roles.DOCTOR, approval_status=CustomUser.ApprovalStatus.SUSPENDED)
    removed_doctors = CustomUser.objects.filter(role=CustomUser.Roles.DOCTOR, approval_status=CustomUser.ApprovalStatus.REMOVED)
    
    # Audit log and task logs for monitoring
    recent_tasks = AsyncTask.objects.all().order_by('-created_at')[:10]
    recent_audits = AuditLog.objects.all().order_by('-timestamp')[:10]
    
    # 1. PostgreSQL Status
    try:
        connection.ensure_connection()
        db_status = "Healthy"
    except Exception:
        db_status = "Unreachable"

    # 2. Mailpit SMTP Status
    try:
        smtp_host = getattr(settings, 'SMTP_HOST', 'mailpit') or 'mailpit'
        smtp_port = int(getattr(settings, 'SMTP_PORT', 1025) or 1025)
        with socket.create_connection((smtp_host, smtp_port), timeout=1):
            mailpit_status = "Healthy"
    except Exception:
        mailpit_status = "Unreachable"

    # 3. Google Calendar Configuration Status
    google_config = "Configured" if (
        getattr(settings, 'GOOGLE_CLIENT_ID', None) and
        getattr(settings, 'GOOGLE_CLIENT_SECRET', None)
    ) else "Not Configured"

    # 4. Serverless Email Service status
    try:
        email_url = getattr(settings, 'EMAIL_SERVICE_URL', 'http://serverless:3000/dev/send-email')
        health_url = email_url.replace('/send-email', '/health').replace('/local/send-email', '/local/health')
        r = requests.get(health_url, timeout=1)
        email_status = "Healthy" if r.status_code == 200 else "Degraded"
    except Exception:
        email_status = "Unreachable"

    # 5. Async Worker stats
    worker_pending = AsyncTask.objects.filter(status=AsyncTask.Statuses.PENDING).count()
    worker_processed = AsyncTask.objects.filter(status=AsyncTask.Statuses.SUCCESS).count()
    worker_failed = AsyncTask.objects.filter(status=AsyncTask.Statuses.FAILED).count()
    worker_running = AsyncTask.objects.filter(status=AsyncTask.Statuses.RUNNING).count()
    worker_retries = AsyncTask.objects.aggregate(Sum('retry_count'))['retry_count__sum'] or 0
    
    recent_active = AsyncTask.objects.filter(
        updated_at__gte=timezone.now() - datetime.timedelta(minutes=5)
    ).exists()
    worker_status = "Active" if (worker_running > 0 or recent_active) else "Idle"

    system_health = {
        'django': 'Healthy',
        'postgres': db_status,
        'mailpit': mailpit_status,
        'google_calendar': google_config,
        'serverless_email': email_status,
        'worker': {
            'status': worker_status,
            'pending': worker_pending,
            'processed': worker_processed,
            'failed': worker_failed,
            'retries': worker_retries
        }
    }

    # Administrative overrides lists
    all_bookings_admin = Booking.objects.all().order_by('-slot__start_datetime')

    context = {
        'pending_doctors': pending_doctors,
        'approved_doctors': approved_doctors,
        'rejected_doctors': rejected_doctors,
        'suspended_doctors': suspended_doctors,
        'removed_doctors': removed_doctors,
        'recent_tasks': recent_tasks,
        'recent_audits': recent_audits,
        'system_health': system_health,
        'all_bookings_admin': all_bookings_admin,
    }
    return render(request, 'admin_panel/dashboard.html', context)

@admin_required
def doctor_detail_view(request, pk):
    from doctors.models import Review
    doctor = get_object_or_404(CustomUser, pk=pk, role=CustomUser.Roles.DOCTOR)
    profile = doctor.doctor_profile
    appointments = Booking.objects.filter(slot__doctor=profile).order_by('-slot__start_datetime')
    reviews = Review.objects.filter(doctor=profile).order_by('-created_at')
    
    context = {
        'doctor': doctor,
        'profile': profile,
        'appointments': appointments,
        'reviews': reviews
    }
    return render(request, 'admin_panel/doctor_detail.html', context)


@admin_required
def approve_doctor_view(request, pk):
    doctor = get_object_or_404(CustomUser, pk=pk, role=CustomUser.Roles.DOCTOR)
    if doctor.approval_status != CustomUser.ApprovalStatus.APPROVED:
        doctor.approval_status = CustomUser.ApprovalStatus.APPROVED
        doctor.save()
        
        # Log audit trail
        AuditLog.objects.create(
            actor=request.user,
            action="APPROVE_DOCTOR",
            ip_address=request.META.get('REMOTE_ADDR'),
            details={"doctor_username": doctor.username, "doctor_email": doctor.email}
        )
        
        # Enqueue doctor approved notification task
        AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.SEND_EMAIL,
            payload={
                'type': 'DOCTOR_APPROVED',
                'user_id': str(doctor.id),
                'recipient_email': doctor.email
            }
        )
        
        messages.success(request, f"Dr. {doctor.get_full_name() or doctor.username} has been approved. Notification email queued.")
    return redirect('admin_panel:dashboard')


@admin_required
def reject_doctor_view(request, pk):
    doctor = get_object_or_404(CustomUser, pk=pk, role=CustomUser.Roles.DOCTOR)
    if doctor.approval_status != CustomUser.ApprovalStatus.REJECTED:
        doctor.approval_status = CustomUser.ApprovalStatus.REJECTED
        doctor.save()
        
        # Log audit trail
        AuditLog.objects.create(
            actor=request.user,
            action="REJECT_DOCTOR",
            ip_address=request.META.get('REMOTE_ADDR'),
            details={"doctor_username": doctor.username, "doctor_email": doctor.email}
        )

        # Enqueue doctor rejected notification task
        AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.SEND_EMAIL,
            payload={
                'type': 'DOCTOR_REJECTED',
                'user_id': str(doctor.id),
                'recipient_email': doctor.email,
                'reason': 'Provided credentials or documentation did not pass our verification standards.'
            }
        )
        
        messages.warning(request, f"Registration request for Dr. {doctor.get_full_name() or doctor.username} was rejected.")
    return redirect('admin_panel:dashboard')


@admin_required
def suspend_doctor_view(request, pk):
    doctor = get_object_or_404(CustomUser, pk=pk, role=CustomUser.Roles.DOCTOR)
    if doctor.approval_status != CustomUser.ApprovalStatus.SUSPENDED:
        doctor.approval_status = CustomUser.ApprovalStatus.SUSPENDED
        doctor.save()
        
        # Log audit trail
        AuditLog.objects.create(
            actor=request.user,
            action="SUSPEND_DOCTOR",
            ip_address=request.META.get('REMOTE_ADDR'),
            details={"doctor_username": doctor.username, "doctor_email": doctor.email}
        )
        messages.warning(request, f"Dr. {doctor.get_full_name() or doctor.username} has been suspended.")
    return redirect('admin_panel:doctor_detail', pk=pk)


@admin_required
def reactivate_doctor_view(request, pk):
    doctor = get_object_or_404(CustomUser, pk=pk, role=CustomUser.Roles.DOCTOR)
    if doctor.approval_status != CustomUser.ApprovalStatus.APPROVED:
        doctor.approval_status = CustomUser.ApprovalStatus.APPROVED
        doctor.save()
        
        # Log audit trail
        AuditLog.objects.create(
            actor=request.user,
            action="REACTIVATE_DOCTOR",
            ip_address=request.META.get('REMOTE_ADDR'),
            details={"doctor_username": doctor.username, "doctor_email": doctor.email}
        )
        messages.success(request, f"Dr. {doctor.get_full_name() or doctor.username} has been reactivated.")
    return redirect('admin_panel:doctor_detail', pk=pk)


@admin_required
def remove_doctor_view(request, pk):
    from appointments.services import cancel_booking
    
    doctor = get_object_or_404(CustomUser, pk=pk, role=CustomUser.Roles.DOCTOR)
    if doctor.approval_status != CustomUser.ApprovalStatus.REMOVED:
        doctor.approval_status = CustomUser.ApprovalStatus.REMOVED
        doctor.save()
        
        # Delete all future AVAILABLE slots
        doctor_profile = doctor.doctor_profile
        AvailabilitySlot.objects.filter(
            doctor=doctor_profile,
            start_datetime__gte=timezone.now(),
            status='AVAILABLE'
        ).delete()
        
        # Cancel all future BOOKED appointments
        future_bookings = Booking.objects.filter(
            slot__doctor=doctor_profile,
            slot__start_datetime__gte=timezone.now()
        )
        for booking in future_bookings:
            cancel_booking(booking.id, user=booking.patient, actor=request.user)
            
        # Log audit trail
        AuditLog.objects.create(
            actor=request.user,
            action="REMOVE_DOCTOR",
            ip_address=request.META.get('REMOTE_ADDR'),
            details={"doctor_username": doctor.username, "doctor_email": doctor.email}
        )
        messages.error(request, f"Dr. {doctor.get_full_name() or doctor.username} has been permanently removed from clinical service.")
    return redirect('admin_panel:dashboard')


@admin_required
def admin_edit_doctor_view(request, pk):
    from .forms import AdminDoctorEditForm
    doctor = get_object_or_404(CustomUser, pk=pk, role=CustomUser.Roles.DOCTOR)
    profile = doctor.doctor_profile
    if request.method == 'POST':
        form = AdminDoctorEditForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, f"Dr. {doctor.get_full_name()} profile information updated.")
            return redirect('admin_panel:doctor_detail', pk=pk)
    else:
        form = AdminDoctorEditForm(instance=profile)
    return render(request, 'admin_panel/doctor_edit.html', {'form': form, 'doctor': doctor})


@admin_required
def admin_manage_working_hours_view(request, pk):
    from doctors.models import WorkingHours
    from doctors.views import generate_slots
    
    doctor = get_object_or_404(CustomUser, pk=pk, role=CustomUser.Roles.DOCTOR)
    profile = doctor.doctor_profile
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save':
            for day_num in range(7):
                is_active = request.POST.get(f'active_{day_num}') == 'on'
                if is_active:
                    start_str = request.POST.get(f'start_{day_num}')
                    end_str = request.POST.get(f'end_{day_num}')
                    duration_str = request.POST.get(f'duration_{day_num}', 30)
                    buffer_str = request.POST.get(f'buffer_{day_num}', 0)
                    
                    if start_str and end_str:
                        start_time = datetime.datetime.strptime(start_str, "%H:%M").time()
                        end_time = datetime.datetime.strptime(end_str, "%H:%M").time()
                        
                        WorkingHours.objects.update_or_create(
                            doctor=profile,
                            day_of_week=day_num,
                            defaults={
                                'start_time': start_time,
                                'end_time': end_time,
                                'slot_duration_minutes': int(duration_str),
                                'buffer_time_minutes': int(buffer_str)
                              }
                          )
                else:
                    WorkingHours.objects.filter(doctor=profile, day_of_week=day_num).delete()
            
            # Regenerate slots option
            if request.POST.get('regenerate_slots') == 'on':
                AvailabilitySlot.objects.filter(doctor=profile, start_datetime__gte=timezone.now(), status='AVAILABLE').delete()
                today = timezone.localdate()
                end_date = today + datetime.timedelta(days=14)
                generate_slots(profile, today, end_date, actor=request.user)
                messages.success(request, "Working hours saved and future slots generated.")
            else:
                messages.success(request, "Working hours saved successfully.")
            return redirect('admin_panel:doctor_detail', pk=pk)
            
    working_hours_list = WorkingHours.objects.filter(doctor=profile).order_by('day_of_week')
    existing_wh = {wh.day_of_week: wh for wh in working_hours_list}
    
    days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    days_data = []
    for i in range(7):
        days_data.append({
            'day_num': i,
            'day_name': days_names[i],
            'wh': existing_wh.get(i)
        })
    
    context = {
        'doctor': doctor,
        'days_data': days_data
    }
    return render(request, 'admin_panel/doctor_working_hours.html', context)


@admin_required
def admin_manage_leaves_view(request, pk):
    from doctors.models import DoctorLeave
    doctor = get_object_or_404(CustomUser, pk=pk, role=CustomUser.Roles.DOCTOR)
    profile = doctor.doctor_profile
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            start_str = request.POST.get('start_date')
            end_str = request.POST.get('end_date')
            reason = request.POST.get('reason', '')
            
            if start_str and end_str:
                start_date = datetime.datetime.strptime(start_str, "%Y-%m-%d").date()
                end_date = datetime.datetime.strptime(end_str, "%Y-%m-%d").date()
                
                DoctorLeave.objects.create(
                    doctor=profile,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason
                )
                # Block/delete AVAILABLE slots in range
                AvailabilitySlot.objects.filter(
                    doctor=profile,
                    start_datetime__date__gte=start_date,
                    start_datetime__date__lte=end_date,
                    status='AVAILABLE'
                ).delete()
                
                messages.success(request, "Leave added and future slots in this range cleared.")
        elif action == 'delete':
            leave_id = request.POST.get('leave_id')
            DoctorLeave.objects.filter(id=leave_id, doctor=profile).delete()
            messages.info(request, "Leave removed.")
        return redirect('admin_panel:admin_manage_leaves', pk=pk)
        
    leaves = DoctorLeave.objects.filter(doctor=profile).order_by('-start_date')
    return render(request, 'admin_panel/doctor_leaves.html', {'doctor': doctor, 'leaves': leaves})


@admin_required
def edit_hospital_config_view(request):
    from common.models import HospitalConfig
    from .forms import HospitalConfigForm
    
    config = HospitalConfig.get_solo()
    if request.method == 'POST':
        form = HospitalConfigForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Hospital Configuration updated successfully.")
            return redirect('admin_panel:dashboard')
    else:
        form = HospitalConfigForm(instance=config)
    return render(request, 'admin_panel/hospital_config.html', {'form': form, 'config': config})


