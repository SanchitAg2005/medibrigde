import time
import requests
import traceback
import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from common.models import AsyncTask
from common.utils import log_event

class Command(BaseCommand):
    help = "Processes pending async tasks from the AsyncTask table (emails and calendar sync) with backoff and retries."

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run the task loop exactly once instead of running indefinitely.'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("AuraHealth Background Task Worker started..."))
        
        # 1. Recovery on startup: Reset tasks stuck in RUNNING state back to PENDING
        stuck_tasks = AsyncTask.objects.filter(status=AsyncTask.Statuses.RUNNING)
        if stuck_tasks.exists():
            self.stdout.write(self.style.WARNING(f"Recovered {stuck_tasks.count()} tasks stuck in RUNNING state."))
            for task in stuck_tasks:
                task.status = AsyncTask.Statuses.PENDING
                task.save()
        
        MAX_RETRIES = 5
        once = options.get('once', False)

        while True:
            # 2. Fetch pending tasks
            tasks = AsyncTask.objects.filter(status=AsyncTask.Statuses.PENDING).order_by('created_at')
            now = timezone.now()
            
            for task in tasks:
                # 3. Enforce exponential backoff checking
                if task.retry_count > 0:
                    # Delay = 5s * 2^(retry_count - 1) -> e.g. 5s, 10s, 20s, 40s, 80s
                    backoff_delay = 5 * (2 ** (task.retry_count - 1))
                    if now < task.updated_at + datetime.timedelta(seconds=backoff_delay):
                        continue # Skip and check next time
                
                self.stdout.write(f"Processing task #{task.id} (Type: {task.task_type}, Retry: {task.retry_count})...")
                task.status = AsyncTask.Statuses.RUNNING
                task.save()
                
                try:
                    if task.task_type == AsyncTask.TaskTypes.SEND_EMAIL:
                        self.process_email_task(task)
                    elif task.task_type in [AsyncTask.TaskTypes.CREATE_CALENDAR, 
                                            AsyncTask.TaskTypes.UPDATE_CALENDAR, 
                                            AsyncTask.TaskTypes.DELETE_CALENDAR]:
                        self.process_calendar_task(task)
                    else:
                        raise ValueError(f"Unknown task type: {task.task_type}")
                    
                    # Log success
                    task.status = AsyncTask.Statuses.SUCCESS
                    task.error_log = ""
                    task.save()
                    
                    log_event(
                        action="ASYNC_TASK_SUCCESS",
                        details={"task_id": task.id, "task_type": task.task_type}
                    )
                    self.stdout.write(self.style.SUCCESS(f"Task #{task.id} processed successfully."))
                    
                except Exception as e:
                    task.error_log = traceback.format_exc()
                    task.retry_count += 1
                    
                    if task.retry_count >= MAX_RETRIES:
                        task.status = AsyncTask.Statuses.FAILED
                        task.save()
                        # Log permanent failure
                        log_event(
                            action="ASYNC_TASK_FAILED_PERMANENTLY",
                            details={"task_id": task.id, "task_type": task.task_type, "error": str(e), "retries": task.retry_count}
                        )
                        self.stdout.write(self.style.ERROR(f"Task #{task.id} failed permanently after {task.retry_count} retries."))
                    else:
                        task.status = AsyncTask.Statuses.PENDING
                        task.save()
                        # Log retry attempt
                        log_event(
                            action="ASYNC_TASK_RETRY",
                            details={"task_id": task.id, "task_type": task.task_type, "error": str(e), "attempt": task.retry_count}
                        )
                        self.stdout.write(self.style.WARNING(f"Task #{task.id} failed, scheduled for retry in backoff window. Error: {str(e)}"))
            
            if once:
                break

            # Poll database every 3 seconds
            time.sleep(3)

    def process_email_task(self, task):
        url = settings.EMAIL_SERVICE_URL or "http://serverless:3000/dev/send-email"
        payload = task.payload
        trigger_type = payload.get("type") or payload.get("trigger_type")
        recipient_email = payload.get("recipient_email")
        
        # Dynamically build context based on type
        context = {}
        if trigger_type == "BOOKING_CONFIRMATION":
            from appointments.models import Booking
            booking_id = payload.get("booking_id")
            booking = Booking.objects.get(pk=booking_id)
            context = {
                "patient_name": booking.patient.get_full_name() or booking.patient.username,
                "reference_id": booking.reference_id,
                "doctor_name": booking.slot.doctor.user.get_full_name() or booking.slot.doctor.user.username,
                "appointment_time": booking.slot.start_datetime.strftime('%Y-%m-%d %H:%M')
            }
        elif trigger_type == "BOOKING_CANCELLATION":
            from appointments.models import Booking
            booking_id = payload.get("booking_id")
            booking = Booking.objects.get(pk=booking_id)
            context = {
                "patient_name": booking.patient.get_full_name() or booking.patient.username,
                "reference_id": booking.reference_id,
                "doctor_name": booking.slot.doctor.user.get_full_name() or booking.slot.doctor.user.username,
                "appointment_time": booking.slot.start_datetime.strftime('%Y-%m-%d %H:%M')
            }
        elif trigger_type == "SIGNUP_WELCOME":
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user_id = payload.get("user_id")
            # Fallback if signup view payload was custom
            if not user_id and payload.get("context"):
                user_id = payload["context"].get("user_id")
            
            if user_id:
                user = User.objects.get(pk=user_id)
                name = user.get_full_name() or user.username
            else:
                name = payload.get("context", {}).get("name", "User")
                
            context = {
                "name": name,
                "login_url": "http://localhost:8000/auth/login/"
            }
        elif trigger_type in ["DOCTOR_APPROVED", "DOCTOR_REJECTED"]:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user_id = payload.get("user_id")
            user = User.objects.get(pk=user_id)
            context = {
                "name": user.get_full_name() or user.username,
                "reason": payload.get("reason", "Provided credentials did not pass verification."),
                "login_url": "http://localhost:8000/auth/login/"
            }
        else:
            context = payload.get("context", {})

        from common.models import HospitalConfig
        config = HospitalConfig.get_solo()
        context["hospital_config"] = {
            "name": config.name,
            "logo_url": config.logo.url if config.logo else "",
            "address": config.address,
            "phone": config.phone,
            "email": config.email,
            "website": config.website,
            "working_hours": config.working_hours,
            "emergency_contact": config.emergency_contact
        }

        response = requests.post(
            url,
            json={
                "recipient_email": recipient_email,
                "trigger_type": trigger_type,
                "context": context
            },
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Email service returned status {response.status_code}: {response.text}")

    def process_calendar_task(self, task):
        from appointments.models import Booking
        from calendar_sync.services import sync_booking_event, delete_booking_event
        
        booking_id = task.payload.get('booking_id')
        if not booking_id:
            raise ValueError("Task payload is missing booking_id.")
            
        try:
            booking = Booking.objects.get(pk=booking_id)
        except Booking.DoesNotExist:
            self.stdout.write(f"Booking {booking_id} does not exist. Skipping task.")
            return

        if task.task_type in [AsyncTask.TaskTypes.CREATE_CALENDAR, AsyncTask.TaskTypes.UPDATE_CALENDAR]:
            sync_booking_event(booking)
        elif task.task_type == AsyncTask.TaskTypes.DELETE_CALENDAR:
            delete_booking_event(booking)

