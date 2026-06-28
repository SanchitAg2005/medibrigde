import datetime
from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from unittest.mock import patch, MagicMock

from common.models import AsyncTask
from appointments.models import AvailabilitySlot, Booking
from doctors.models import DoctorProfile
from django.contrib.auth import get_user_model

User = get_user_model()

class BackgroundWorkerTests(TestCase):
    def setUp(self):
        # Create standard test data
        self.patient_user = User.objects.create_user(
            username='alice_green',
            email='alice@example.com',
            password='password123',
            role=User.Roles.PATIENT,
            first_name='Alice',
            last_name='Green'
        )
        self.patient_user.approval_status = User.ApprovalStatus.APPROVED
        self.patient_user.save()

        self.doctor_user = User.objects.create_user(
            username='dr_smith',
            email='smith@hospital.local',
            password='password123',
            role=User.Roles.DOCTOR,
            first_name='John',
            last_name='Smith'
        )
        self.doctor_user.approval_status = User.ApprovalStatus.APPROVED
        self.doctor_user.save()

        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            specialization='Cardiology',
            experience_years=12,
            hospital_name='AuraHealth Cardiology Clinic'
        )

        self.slot = AvailabilitySlot.objects.create(
            doctor=self.doctor_profile,
            start_datetime=timezone.now() + datetime.timedelta(days=1),
            end_datetime=timezone.now() + datetime.timedelta(days=1, hours=1),
            status='BOOKED'
        )
        self.booking = Booking.objects.create(
            slot=self.slot,
            patient=self.patient_user,
            reference_id='APT-TEST-REF'
        )

    @patch('requests.post')
    def test_startup_recovery(self, mock_post):
        mock_post.return_value.status_code = 200
        # Create a task in RUNNING state
        task = AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.SEND_EMAIL,
            status=AsyncTask.Statuses.RUNNING,
            payload={"type": "SIGNUP_WELCOME", "recipient_email": "test@example.com"}
        )
        
        # Run worker once
        call_command('process_tasks', once=True)
        
        task.refresh_from_db()
        self.assertEqual(task.status, AsyncTask.Statuses.SUCCESS)

    @patch('requests.post')
    def test_process_email_task_success(self, mock_post):
        mock_post.return_value.status_code = 200
        
        task = AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.SEND_EMAIL,
            status=AsyncTask.Statuses.PENDING,
            payload={
                "type": "BOOKING_CONFIRMATION",
                "booking_id": str(self.booking.id),
                "recipient_email": "alice@example.com"
            }
        )

        call_command('process_tasks', once=True)

        task.refresh_from_db()
        self.assertEqual(task.status, AsyncTask.Statuses.SUCCESS)
        self.assertEqual(task.retry_count, 0)
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_process_email_task_failure_with_retry(self, mock_post):
        # Email endpoint returns 500 error
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "Internal Server Error"

        task = AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.SEND_EMAIL,
            status=AsyncTask.Statuses.PENDING,
            payload={
                "type": "SIGNUP_WELCOME",
                "user_id": str(self.patient_user.id),
                "recipient_email": "alice@example.com"
            }
        )

        call_command('process_tasks', once=True)

        task.refresh_from_db()
        self.assertEqual(task.status, AsyncTask.Statuses.PENDING)
        self.assertEqual(task.retry_count, 1)
        self.assertIn("RuntimeError", task.error_log)

    @patch('requests.post')
    def test_process_email_task_max_retries(self, mock_post):
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "Internal Server Error"

        task = AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.SEND_EMAIL,
            status=AsyncTask.Statuses.PENDING,
            retry_count=4,  # Next failure will make it 5, which is MAX_RETRIES
            payload={
                "type": "SIGNUP_WELCOME",
                "user_id": str(self.patient_user.id),
                "recipient_email": "alice@example.com"
            }
        )

        # Force updated_at to be way in the past to bypass backoff delay check
        AsyncTask.objects.filter(pk=task.pk).update(
            updated_at=timezone.now() - datetime.timedelta(seconds=1000)
        )

        call_command('process_tasks', once=True)

        task.refresh_from_db()
        self.assertEqual(task.status, AsyncTask.Statuses.FAILED)
        self.assertEqual(task.retry_count, 5)

    def test_exponential_backoff(self):
        # Task with retry_count = 1, failed recently (updated_at = now)
        task = AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.SEND_EMAIL,
            status=AsyncTask.Statuses.PENDING,
            retry_count=1,
            payload={
                "type": "SIGNUP_WELCOME",
                "user_id": str(self.patient_user.id),
                "recipient_email": "alice@example.com"
            }
        )
        
        # Manually force updated_at to be exactly timezone.now() (auto_now updates on save)
        # So it is well within backoff_delay = 5 * 2^(1-1) = 5 seconds
        with patch('requests.post') as mock_post:
            call_command('process_tasks', once=True)
            # The task should be skipped because of backoff window, so mock_post not called
            mock_post.assert_not_called()
            task.refresh_from_db()
            self.assertEqual(task.status, AsyncTask.Statuses.PENDING)
            self.assertEqual(task.retry_count, 1)

    @patch('calendar_sync.services.sync_booking_event')
    def test_process_calendar_task_create(self, mock_sync):
        task = AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.CREATE_CALENDAR,
            status=AsyncTask.Statuses.PENDING,
            payload={"booking_id": str(self.booking.id)}
        )

        call_command('process_tasks', once=True)

        task.refresh_from_db()
        self.assertEqual(task.status, AsyncTask.Statuses.SUCCESS)
        mock_sync.assert_called_once_with(self.booking)

    @patch('calendar_sync.services.delete_booking_event')
    def test_process_calendar_task_delete(self, mock_delete):
        task = AsyncTask.objects.create(
            task_type=AsyncTask.TaskTypes.DELETE_CALENDAR,
            status=AsyncTask.Statuses.PENDING,
            payload={"booking_id": str(self.booking.id)}
        )

        call_command('process_tasks', once=True)

        task.refresh_from_db()
        self.assertEqual(task.status, AsyncTask.Statuses.SUCCESS)
        mock_delete.assert_called_once_with(self.booking)


class DoctorLifecycleAndHospitalConfigTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email='admin@hospital.local',
            password='password123'
        )
        self.patient_user = User.objects.create_user(
            username='patient',
            email='patient@example.com',
            password='password123',
            role=User.Roles.PATIENT
        )
        self.doctor_user = User.objects.create_user(
            username='dr_jones',
            email='jones@hospital.local',
            password='password123',
            role=User.Roles.DOCTOR
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            specialization='Pediatrics',
            experience_years=5,
            hospital_name='MediBridge Medical Center'
        )
        
        # Create unbooked slot
        self.avail_slot = AvailabilitySlot.objects.create(
            doctor=self.doctor_profile,
            start_datetime=timezone.now() + datetime.timedelta(days=2),
            end_datetime=timezone.now() + datetime.timedelta(days=2, hours=1),
            status='AVAILABLE'
        )
        
        # Create booked slot & booking
        self.booked_slot = AvailabilitySlot.objects.create(
            doctor=self.doctor_profile,
            start_datetime=timezone.now() + datetime.timedelta(days=3),
            end_datetime=timezone.now() + datetime.timedelta(days=3, hours=1),
            status='BOOKED'
        )
        self.booking = Booking.objects.create(
            slot=self.booked_slot,
            patient=self.patient_user,
            reference_id='APT-JONES-BOOKED'
        )

    def test_hospital_config_singleton(self):
        from common.models import HospitalConfig
        config = HospitalConfig.get_solo()
        self.assertEqual(config.name, 'MediBridge Medical Center')
        
        config.name = 'MediBridge Specialist Clinic'
        config.save()
        
        config2 = HospitalConfig.get_solo()
        self.assertEqual(config2.name, 'MediBridge Specialist Clinic')

    @patch('appointments.services.cancel_booking')
    def test_doctor_removal_workflow(self, mock_cancel):
        # Authenticate admin client
        self.client.login(username='admin@hospital.local', password='password123')
        
        # Trigger remove endpoint
        response = self.client.get(f'/admin-panel/doctor/{self.doctor_user.pk}/remove/')
        self.assertEqual(response.status_code, 302)
        
        self.doctor_user.refresh_from_db()
        self.assertEqual(self.doctor_user.approval_status, User.ApprovalStatus.REMOVED)
        
        # Unbooked availability slot should be deleted
        self.assertFalse(AvailabilitySlot.objects.filter(pk=self.avail_slot.pk).exists())
        
        # Booked slot remains, but transaction cancellation service called
        mock_cancel.assert_called_once()
