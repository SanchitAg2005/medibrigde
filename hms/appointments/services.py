import uuid
import datetime
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q
from appointments.models import AvailabilitySlot, Booking
from doctors.models import DoctorProfile, WorkingHours, DoctorLeave
from common.utils import log_event
from common.models import AsyncTask

def generate_slots(doctor, start_date, end_date, actor=None, ip_address=None):
    """
    Automatically generates availability slots for a doctor in a date range.
    """
    # Purge existing AVAILABLE slots within the date range to prevent timezone/schedule mismatch duplicates
    tz = timezone.get_current_timezone()
    start_dt_bound = timezone.make_aware(datetime.datetime.combine(start_date, datetime.time.min), tz)
    end_dt_bound = timezone.make_aware(datetime.datetime.combine(end_date, datetime.time.max), tz)
    AvailabilitySlot.objects.filter(
        doctor=doctor,
        status='AVAILABLE',
        start_datetime__gte=start_dt_bound,
        start_datetime__lte=end_dt_bound
    ).delete()

    slots_created = 0
    current_date = start_date
    delta = datetime.timedelta(days=1)

    while current_date <= end_date:
        # 1. Skip past dates
        if current_date < timezone.localdate():
            current_date += delta
            continue

        # 2. Check if doctor is on leave
        is_on_leave = DoctorLeave.objects.filter(
            doctor=doctor,
            start_date__lte=current_date,
            end_date__gte=current_date
        ).exists()

        if is_on_leave:
            current_date += delta
            continue

        # 3. Check working hours
        weekday = current_date.weekday()
        wh = WorkingHours.objects.filter(doctor=doctor, day_of_week=weekday).first()
        if not wh:
            current_date += delta
            continue

        # 4. Generate slots
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.datetime.combine(current_date, wh.start_time), tz)
        end_dt = timezone.make_aware(datetime.datetime.combine(current_date, wh.end_time), tz)

        duration = datetime.timedelta(minutes=wh.slot_duration_minutes)
        buffer = datetime.timedelta(minutes=wh.buffer_time_minutes)

        current_dt = start_dt
        while current_dt + duration <= end_dt:
            slot_end = current_dt + duration
            
            # Prevent slot starting in the past
            if current_dt > timezone.now():
                # Prevent overlapping / duplicate slots
                overlap = AvailabilitySlot.objects.filter(
                    doctor=doctor,
                    start_datetime__lt=slot_end,
                    end_datetime__gt=current_dt
                ).exists()

                if not overlap:
                    AvailabilitySlot.objects.create(
                        doctor=doctor,
                        start_datetime=current_dt,
                        end_datetime=slot_end,
                        status='AVAILABLE'
                    )
                    slots_created += 1

            current_dt = slot_end + buffer

        current_date += delta

    if slots_created > 0:
        log_event(
            action="SLOTS_GENERATED",
            actor=actor,
            ip_address=ip_address,
            details={
                "doctor_id": str(doctor.id),
                "start_date": str(start_date),
                "end_date": str(end_date),
                "slots_created": slots_created
            }
        )

    return slots_created


def create_manual_slot(doctor, start_datetime, end_datetime, actor=None, ip_address=None):
    """
    Manually creates a single availability slot with full validation.
    """
    # 1. End time must be after start time
    if end_datetime <= start_datetime:
        raise ValidationError("End date/time must be after start date/time.")

    # 2. Cannot be in the past
    if start_datetime < timezone.now():
        raise ValidationError("Cannot create a slot in the past.")

    # 3. Cannot be during a leave period
    date = start_datetime.date()
    is_on_leave = DoctorLeave.objects.filter(
        doctor=doctor,
        start_date__lte=date,
        end_date__gte=date
    ).exists()
    if is_on_leave:
        raise ValidationError("Cannot create a slot during a doctor leave period.")

    # 4. Check working hours configuration for that weekday
    weekday = date.weekday()
    wh = WorkingHours.objects.filter(doctor=doctor, day_of_week=weekday).first()
    if not wh:
        raise ValidationError("No working hours defined for this day of the week.")

    tz = timezone.get_current_timezone()
    wh_start = timezone.make_aware(datetime.datetime.combine(date, wh.start_time), tz)
    wh_end = timezone.make_aware(datetime.datetime.combine(date, wh.end_time), tz)

    if start_datetime < wh_start or end_datetime > wh_end:
        raise ValidationError("Slot time must fall within the configured working hours.")

    # 5. Prevent overlap
    overlap = AvailabilitySlot.objects.filter(
        doctor=doctor,
        start_datetime__lt=end_datetime,
        end_datetime__gt=start_datetime
    ).exists()
    if overlap:
        raise ValidationError("This slot overlaps with an existing slot.")

    slot = AvailabilitySlot.objects.create(
        doctor=doctor,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        status='AVAILABLE'
    )

    log_event(
        action="SLOT_CREATED",
        actor=actor,
        ip_address=ip_address,
        details={
            "slot_id": slot.id,
            "doctor_id": str(doctor.id),
            "start": start_datetime.isoformat(),
            "end": end_datetime.isoformat()
        }
    )

    return slot


def generate_reference_id():
    """
    Generates a unique booking reference ID.
    Example: APT-2026-X8Y2
    """
    import random
    import string
    year = datetime.datetime.now().year
    rand_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"APT-{year}-{rand_part}"


def book_appointment(slot_id, patient, actor=None, ip_address=None):
    """
    Atomically books an available slot using pessimistic locking.
    """
    with transaction.atomic():
        # Lock the slot row
        slot = AvailabilitySlot.objects.select_for_update().get(pk=slot_id)
        if slot.status != 'AVAILABLE':
            raise ValidationError("This slot is no longer available.")

        # Update slot status
        slot.status = 'BOOKED'
        slot.save()

        # Create Booking
        ref_id = generate_reference_id()
        booking = Booking.objects.create(
            slot=slot,
            patient=patient,
            reference_id=ref_id
        )

        # Enforce Audit Logging
        log_event(
            action="BOOKING_CREATED",
            actor=actor or patient,
            ip_address=ip_address,
            details={
                "booking_id": str(booking.id),
                "reference_id": ref_id,
                "slot_id": slot.id,
                "doctor_id": str(slot.doctor.id),
                "patient_id": str(patient.id)
            }
        )

        # Queue background tasks (Google Calendar and Email Sync)
        AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.CREATE_CALENDAR,
            payload={"booking_id": str(booking.id)}
        )

        AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.SEND_EMAIL,
            payload={
                "type": "BOOKING_CONFIRMATION",
                "booking_id": str(booking.id),
                "recipient_email": patient.email,
                "recipient_name": f"{patient.first_name} {patient.last_name}"
            }
        )

        return booking


def cancel_booking(booking_id, user, actor=None, ip_address=None):
    """
    Cancels a booking after validating state machine and user permissions.
    """
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking_id)
        
        # Validate state transition rules
        is_allowed, error_msg = booking.can_transition_to('CANCELLED', user)
        if not is_allowed:
            raise ValidationError(error_msg)

        # Update statuses
        slot = booking.slot
        slot.status = 'CANCELLED'
        slot.save()

        log_event(
            action="BOOKING_CANCELLED",
            actor=actor or user,
            ip_address=ip_address,
            details={
                "booking_id": str(booking.id),
                "reference_id": booking.reference_id,
                "cancelled_by": user.username
            }
        )

        # Queue Google Calendar deletion async task
        if booking.google_event_id_doctor or booking.google_event_id_patient:
            AsyncTask.objects.create(
                task_type=AsyncTask.TaskTypes.DELETE_CALENDAR,
                payload={"booking_id": str(booking.id)}
            )

        # Queue cancellation email
        AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.SEND_EMAIL,
            payload={
                "type": "BOOKING_CANCELLATION",
                "booking_id": str(booking.id),
                "recipient_email": booking.patient.email,
                "recipient_name": f"{booking.patient.first_name} {booking.patient.last_name}"
            }
        )

        return booking
