from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from appointments.models import AvailabilitySlot, Booking
from appointments.services import book_appointment, cancel_booking
from common.utils import log_request_event

@login_required
def book_appointment_view(request, slot_id):
    """
    Patient books an available slot.
    """
    if request.user.role != 'PATIENT':
        messages.error(request, "Only patients are allowed to book appointments.")
        return redirect('dashboard')

    try:
        booking = book_appointment(
            slot_id=slot_id,
            patient=request.user,
            actor=request.user,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        messages.success(request, f"Appointment successfully booked! Your Reference ID is {booking.reference_id}.")
        return redirect('patients:dashboard')
    except ValidationError as e:
        messages.error(request, str(e))
        return redirect('patients:dashboard')
    except Exception as e:
        messages.error(request, "An unexpected error occurred while booking. Please try again.")
        return redirect('patients:dashboard')


@login_required
def cancel_booking_view(request, booking_id):
    """
    Cancels a booking after checking state machine.
    """
    booking = get_object_or_404(Booking, pk=booking_id)
    try:
        cancel_booking(
            booking_id=booking_id,
            user=request.user,
            actor=request.user,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        messages.success(request, "Appointment successfully cancelled.")
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, "An unexpected error occurred while cancelling.")
    
    # Redirect based on user role
    if request.user.role == 'PATIENT':
        return redirect('patients:dashboard')
    elif request.user.role == 'DOCTOR':
        return redirect('doctors:dashboard')
    return redirect('dashboard')


@login_required
def start_consultation_view(request, booking_id):
    """
    Doctor transitions slot state to IN_CONSULTATION when patient is present.
    """
    if request.user.role not in ['DOCTOR', 'ADMIN']:
        messages.error(request, "Only doctors or admins can start consultations.")
        return redirect('dashboard')

    booking = get_object_or_404(Booking, pk=booking_id)
    is_allowed, error_msg = booking.can_transition_to('IN_CONSULTATION', request.user)
    if not is_allowed:
        messages.error(request, f"Cannot start consultation: {error_msg}")
        return redirect('doctors:dashboard')

    # Update slot state
    slot = booking.slot
    slot.status = 'IN_CONSULTATION'
    slot.save()

    log_request_event(
        request=request,
        action="CONSULTATION_STARTED",
        details={"booking_id": str(booking.id), "reference_id": booking.reference_id}
    )

    messages.success(request, f"Consultation started for patient {booking.patient.get_full_name()}.")
    return redirect('medical_records:create_record', booking_id=booking.id)


@login_required
def mark_no_show_view(request, booking_id):
    """
    Doctor marks appointment as NO_SHOW if the patient didn't show up.
    """
    if request.user.role not in ['DOCTOR', 'ADMIN']:
        messages.error(request, "Only doctors or admins can mark an appointment as a no-show.")
        return redirect('dashboard')

    booking = get_object_or_404(Booking, pk=booking_id)
    is_allowed, error_msg = booking.can_transition_to('NO_SHOW', request.user)
    if not is_allowed:
        messages.error(request, f"Cannot mark as no-show: {error_msg}")
        return redirect('doctors:dashboard')

    slot = booking.slot
    slot.status = 'NO_SHOW'
    slot.save()

    log_request_event(
        request=request,
        action="BOOKING_MARKED_NO_SHOW",
        details={"booking_id": str(booking.id), "reference_id": booking.reference_id}
    )

    messages.success(request, f"Appointment {booking.reference_id} marked as No Show.")
    return redirect('doctors:dashboard')


from django.http import JsonResponse

@login_required
def booking_detail_json_view(request, booking_id):
    """
    Returns appointment metadata as JSON for the Side Details Drawer.
    """
    booking = get_object_or_404(Booking, pk=booking_id)
    slot = booking.slot
    doctor = slot.doctor
    
    # Map backend status to user interface labels
    status_labels = {
        'AVAILABLE': 'Available',
        'BOOKED': 'Confirmed',
        'IN_CONSULTATION': 'In Consultation',
        'COMPLETED': 'Completed',
        'CANCELLED': 'Cancelled',
        'NO_SHOW': 'No Show'
    }
    
    # EMR status
    has_emr = hasattr(booking, 'medical_record')
    emr_status = "Completed" if has_emr else "Not Created"
    emr_id = str(booking.medical_record.id) if has_emr else None
    
    # Google sync status
    google_sync = "Synced" if (booking.google_event_id_doctor or booking.google_event_id_patient) else "Unsynced"
    
    # Determine allowed actions based on current user role and status
    role = getattr(request.user, 'role', None)
    is_admin = (role == 'ADMIN') or request.user.is_superuser
    
    can_cancel = booking.can_transition_to('CANCELLED', request.user)[0]
    can_start_consultation = booking.can_transition_to('IN_CONSULTATION', request.user)[0]
    can_mark_no_show = booking.can_transition_to('NO_SHOW', request.user)[0]
    
    # Doctor/Admin can write EMR if status is IN_CONSULTATION and no EMR exists
    can_create_emr = slot.status == 'IN_CONSULTATION' and not has_emr and (role in ['DOCTOR', 'ADMIN'])
    if role == 'DOCTOR' and doctor.user != request.user:
        can_create_emr = False
        
    # Anyone associated (Patient, Doctor of booking, Admin) can view EMR if it exists
    can_view_emr = has_emr and (
        is_admin or 
        booking.patient == request.user or 
        doctor.user == request.user
    )
    
    data = {
        "id": str(booking.id),
        "reference_id": booking.reference_id,
        "patient_name": booking.patient.get_full_name() or booking.patient.username,
        "patient_email": booking.patient.email,
        "doctor_name": doctor.user.get_full_name() or doctor.user.username,
        "specialization": doctor.specialization,
        "hospital_name": doctor.hospital_name,
        "date": slot.start_datetime.strftime('%Y-%m-%d'),
        "start_time": slot.start_datetime.strftime('%H:%M'),
        "end_time": slot.end_datetime.strftime('%H:%M'),
        "status": slot.status,
        "status_label": status_labels.get(slot.status, slot.status),
        "google_sync_status": google_sync,
        "emr_status": emr_status,
        "emr_id": emr_id,
        "created_at": booking.created_at.strftime('%Y-%m-%d %H:%M'),
        "updated_at": slot.start_datetime.strftime('%Y-%m-%d %H:%M'),
        "actions": {
            "can_cancel": can_cancel,
            "can_start_consultation": can_start_consultation,
            "can_mark_no_show": can_mark_no_show,
            "can_create_emr": can_create_emr,
            "can_view_emr": can_view_emr
        }
    }
    return JsonResponse(data)

