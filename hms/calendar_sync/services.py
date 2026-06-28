import datetime
import requests
from django.conf import settings
from django.utils import timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from calendar_sync.models import GoogleOAuthToken
from common.utils import log_event

def get_google_credentials(user):
    """
    Fetches and returns google.oauth2.credentials.Credentials for a user.
    Refreshes the access token automatically if it is expired or expiring soon.
    Returns None if the user hasn't authenticated Google OAuth.
    """
    try:
        token_record = GoogleOAuthToken.objects.get(user=user)
    except GoogleOAuthToken.DoesNotExist:
        return None

    # Check if token is expired or close to expiring (within 5 minutes)
    now = timezone.now()
    if token_record.token_expiry - datetime.timedelta(minutes=5) <= now:
        if token_record.refresh_token:
            # Call Google token endpoint to refresh
            try:
                response = requests.post('https://oauth2.googleapis.com/token', data={
                    'client_id': settings.GOOGLE_CLIENT_ID,
                    'client_secret': settings.GOOGLE_CLIENT_SECRET,
                    'refresh_token': token_record.refresh_token,
                    'grant_type': 'refresh_token',
                }, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    token_record.access_token = data['access_token']
                    expires_in = data.get('expires_in', 3600)
                    token_record.token_expiry = timezone.now() + datetime.timedelta(seconds=expires_in)
                    token_record.save()
                    
                    log_event(
                        action="GOOGLE_TOKEN_REFRESH_SUCCESS",
                        actor=user,
                        details={"user_id": str(user.id)}
                    )
                else:
                    log_event(
                        action="GOOGLE_TOKEN_REFRESH_FAILURE",
                        actor=user,
                        details={"error": response.text, "status_code": response.status_code}
                    )
                    return None
            except Exception as e:
                log_event(
                    action="GOOGLE_TOKEN_REFRESH_ERROR",
                    actor=user,
                    details={"error": str(e)}
                )
                return None
        else:
            # Expiry happened but no refresh token is stored (user needs to re-authenticate)
            return None

    return Credentials(
        token=token_record.access_token,
        refresh_token=token_record.refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET
    )

def sync_booking_event(booking):
    from common.models import HospitalConfig
    config = HospitalConfig.get_solo()
    
    doctor_name = f"{booking.slot.doctor.user.first_name} {booking.slot.doctor.user.last_name}".strip() or booking.slot.doctor.user.username
    patient_name = booking.patient.get_full_name() or booking.patient.username
    
    summary = f"{config.name} — Appointment with Dr. {doctor_name}"
    description = (
        f"Booking Reference: {booking.reference_id}\n"
        f"Patient Name: {patient_name}\n"
        f"Doctor Name: Dr. {doctor_name}\n"
        f"Department: {booking.slot.doctor.specialization}\n"
        f"Hospital Address: {config.address}\n"
        f"Contact Number: {config.phone}"
    )

    # 1. Sync on Doctor's calendar
    doctor_user = booking.slot.doctor.user
    doctor_creds = get_google_credentials(doctor_user)
    if doctor_creds:
        try:
            service = build('calendar', 'v3', credentials=doctor_creds)
            event_body = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': booking.slot.start_datetime.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': booking.slot.end_datetime.isoformat(),
                    'timeZone': 'UTC',
                },
            }

            if booking.google_event_id_doctor:
                # Update existing event
                service.events().update(
                    calendarId='primary',
                    eventId=booking.google_event_id_doctor,
                    body=event_body
                ).execute()
            else:
                # Create new event
                event = service.events().insert(
                    calendarId='primary',
                    body=event_body
                ).execute()
                booking.google_event_id_doctor = event['id']
                booking.save(update_fields=['google_event_id_doctor'])

            log_event(
                action="GOOGLE_CALENDAR_SYNC_DOCTOR_SUCCESS",
                actor=doctor_user,
                details={"booking_id": str(booking.id), "event_id": booking.google_event_id_doctor}
            )
        except Exception as e:
            # Log failure but do not crash the booking
            log_event(
                action="GOOGLE_CALENDAR_SYNC_DOCTOR_FAILURE",
                actor=doctor_user,
                details={"booking_id": str(booking.id), "error": str(e)}
            )
            raise e  # Allow background worker to capture and retry

    # 2. Sync on Patient's calendar
    patient_user = booking.patient
    patient_creds = get_google_credentials(patient_user)
    if patient_creds:
        try:
            service = build('calendar', 'v3', credentials=patient_creds)
            event_body = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': booking.slot.start_datetime.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': booking.slot.end_datetime.isoformat(),
                    'timeZone': 'UTC',
                },
            }

            if booking.google_event_id_patient:
                service.events().update(
                    calendarId='primary',
                    eventId=booking.google_event_id_patient,
                    body=event_body
                ).execute()
            else:
                event = service.events().insert(
                    calendarId='primary',
                    body=event_body
                ).execute()
                booking.google_event_id_patient = event['id']
                booking.save(update_fields=['google_event_id_patient'])

            log_event(
                action="GOOGLE_CALENDAR_SYNC_PATIENT_SUCCESS",
                actor=patient_user,
                details={"booking_id": str(booking.id), "event_id": booking.google_event_id_patient}
            )
        except Exception as e:
            log_event(
                action="GOOGLE_CALENDAR_SYNC_PATIENT_FAILURE",
                actor=patient_user,
                details={"booking_id": str(booking.id), "error": str(e)}
            )
            raise e

def delete_booking_event(booking):
    """
    Deletes the associated Google Calendar events on cancellations.
    """
    # 1. Doctor event deletion
    if booking.google_event_id_doctor:
        doctor_user = booking.slot.doctor.user
        doctor_creds = get_google_credentials(doctor_user)
        if doctor_creds:
            try:
                service = build('calendar', 'v3', credentials=doctor_creds)
                service.events().delete(
                    calendarId='primary',
                    eventId=booking.google_event_id_doctor
                ).execute()
                booking.google_event_id_doctor = None
                booking.save(update_fields=['google_event_id_doctor'])
                
                log_event(
                    action="GOOGLE_CALENDAR_DELETE_DOCTOR_SUCCESS",
                    actor=doctor_user,
                    details={"booking_id": str(booking.id)}
                )
            except Exception as e:
                log_event(
                    action="GOOGLE_CALENDAR_DELETE_DOCTOR_FAILURE",
                    actor=doctor_user,
                    details={"booking_id": str(booking.id), "error": str(e)}
                )
                raise e

    # 2. Patient event deletion
    if booking.google_event_id_patient:
        patient_user = booking.patient
        patient_creds = get_google_credentials(patient_user)
        if patient_creds:
            try:
                service = build('calendar', 'v3', credentials=patient_creds)
                service.events().delete(
                    calendarId='primary',
                    eventId=booking.google_event_id_patient
                ).execute()
                booking.google_event_id_patient = None
                booking.save(update_fields=['google_event_id_patient'])
                
                log_event(
                    action="GOOGLE_CALENDAR_DELETE_PATIENT_SUCCESS",
                    actor=patient_user,
                    details={"booking_id": str(booking.id)}
                )
            except Exception as e:
                log_event(
                    action="GOOGLE_CALENDAR_DELETE_PATIENT_FAILURE",
                    actor=patient_user,
                    details={"booking_id": str(booking.id), "error": str(e)}
                )
                raise e
