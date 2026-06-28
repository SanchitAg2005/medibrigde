import datetime
import threading
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from doctors.models import DoctorProfile, WorkingHours, DoctorLeave, Review
from appointments.models import AvailabilitySlot, Booking
from appointments.services import (
    generate_slots,
    create_manual_slot,
    book_appointment,
    cancel_booking
)
from doctors.services import create_review
from common.models import AsyncTask

User = get_user_model()

class SlotAndBookingTests(TestCase):
    def setUp(self):
        # 1. Create a doctor user and profile
        self.doctor_user = User.objects.create_user(
            username='drsmith',
            email='smith@hospital.local',
            password='password123',
            role=User.Roles.DOCTOR,
            first_name='John',
            last_name='Smith'
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            specialization='General Medicine',
            experience_years=10,
            hospital_name='City Clinic'
        )

        # 2. Create patient users
        self.patient_user1 = User.objects.create_user(
            username='patient1',
            email='p1@example.com',
            password='password123',
            role=User.Roles.PATIENT,
            first_name='Alice',
            last_name='Green'
        )
        self.patient_user2 = User.objects.create_user(
            username='patient2',
            email='p2@example.com',
            password='password123',
            role=User.Roles.PATIENT,
            first_name='Bob',
            last_name='Blue'
        )

        # 3. Create working hours (Monday: 09:00 - 11:00)
        self.working_hours = WorkingHours.objects.create(
            doctor=self.doctor_profile,
            day_of_week=0, # Monday
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            slot_duration_minutes=30,
            buffer_time_minutes=10
        )

    def test_automatic_slot_generation(self):
        # Generate slots for next Monday (we ensure the date is Monday and in the future)
        today = timezone.now().date()
        next_monday = today + datetime.timedelta(days=(0 - today.weekday() + 7) % 7)
        if next_monday == today:
            next_monday += datetime.timedelta(days=7)

        slots_created = generate_slots(self.doctor_profile, next_monday, next_monday)
        
        # Working hours are 09:00 - 11:00 (120 minutes)
        # Each slot is 30 mins with 10 mins buffer -> 40 mins per slot cycle
        # Slot 1: 09:00 - 09:30
        # Slot 2: 09:40 - 10:10
        # Slot 3: 10:20 - 10:50
        # Total = 3 slots
        self.assertEqual(slots_created, 3)
        self.assertEqual(AvailabilitySlot.objects.filter(doctor=self.doctor_profile).count(), 3)

    def test_slot_generation_excludes_leave(self):
        today = timezone.now().date()
        next_monday = today + datetime.timedelta(days=(0 - today.weekday() + 7) % 7)
        if next_monday == today:
            next_monday += datetime.timedelta(days=7)

        # Create leave for next Monday
        DoctorLeave.objects.create(
            doctor=self.doctor_profile,
            start_date=next_monday,
            end_date=next_monday,
            reason="Vacation"
        )

        slots_created = generate_slots(self.doctor_profile, next_monday, next_monday)
        self.assertEqual(slots_created, 0)

    def test_manual_slot_validation_past_date_fails(self):
        past_dt = timezone.now() - datetime.timedelta(hours=2)
        with self.assertRaises(ValidationError):
            create_manual_slot(self.doctor_profile, past_dt, past_dt + datetime.timedelta(minutes=30))

    def test_booking_and_async_task_queuing(self):
        # Create a single slot in the future
        future_start = timezone.now() + datetime.timedelta(days=2)
        future_end = future_start + datetime.timedelta(minutes=30)
        
        slot = AvailabilitySlot.objects.create(
            doctor=self.doctor_profile,
            start_datetime=future_start,
            end_datetime=future_end,
            status='AVAILABLE'
        )

        # Book the slot
        booking = book_appointment(slot.id, self.patient_user1)
        
        # Verify status changed and booking exists
        slot.refresh_from_db()
        self.assertEqual(slot.status, 'BOOKED')
        self.assertEqual(booking.patient, self.patient_user1)
        self.assertTrue(booking.reference_id.startswith("APT-"))

        # Verify async tasks are queued
        self.assertEqual(AsyncTask.objects.filter(task_type=AsyncTask.TaskTypes.CREATE_CALENDAR).count(), 1)
        self.assertEqual(AsyncTask.objects.filter(task_type=AsyncTask.TaskTypes.SEND_EMAIL).count(), 1)

    def test_patient_can_cancel_booking(self):
        future_start = timezone.now() + datetime.timedelta(days=2)
        future_end = future_start + datetime.timedelta(minutes=30)
        slot = AvailabilitySlot.objects.create(
            doctor=self.doctor_profile,
            start_datetime=future_start,
            end_datetime=future_end,
            status='AVAILABLE'
        )
        booking = book_appointment(slot.id, self.patient_user1)

        # Cancel as patient
        cancel_booking(booking.id, self.patient_user1)
        slot.refresh_from_db()
        self.assertEqual(slot.status, 'CANCELLED')

    def test_invalid_role_cannot_start_consultation(self):
        future_start = timezone.now() + datetime.timedelta(days=2)
        slot = AvailabilitySlot.objects.create(
            doctor=self.doctor_profile,
            start_datetime=future_start,
            end_datetime=future_start + datetime.timedelta(minutes=30),
            status='AVAILABLE'
        )
        booking = book_appointment(slot.id, self.patient_user1)

        # Patient cannot mark IN_CONSULTATION
        is_allowed, _ = booking.can_transition_to('IN_CONSULTATION', self.patient_user1)
        self.assertFalse(is_allowed)

        # Doctor can mark IN_CONSULTATION
        is_allowed, _ = booking.can_transition_to('IN_CONSULTATION', self.doctor_user)
        self.assertTrue(is_allowed)

    def test_review_only_for_completed_appointment(self):
        future_start = timezone.now() + datetime.timedelta(days=2)
        slot = AvailabilitySlot.objects.create(
            doctor=self.doctor_profile,
            start_datetime=future_start,
            end_datetime=future_start + datetime.timedelta(minutes=30),
            status='AVAILABLE'
        )
        booking = book_appointment(slot.id, self.patient_user1)

        # Trying to review a BOOKED appointment fails
        with self.assertRaises(ValidationError):
            create_review(booking.id, self.patient_user1, rating=5)

        # Complete the appointment
        slot.status = 'COMPLETED'
        slot.save()

        # Review succeeds
        review = create_review(booking.id, self.patient_user1, rating=4, comment="Good doctor")
        self.assertEqual(review.rating, 4)
        
        # Verify doctor average rating updated
        self.doctor_profile.refresh_from_db()
        self.assertEqual(self.doctor_profile.average_rating, 4.00)
        self.assertEqual(self.doctor_profile.total_reviews, 1)


import unittest
from django.conf import settings

class BookingConcurrencyTests(TransactionTestCase):
    @unittest.skipIf(settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3', "Skipping concurrency test on SQLite")
    def setUp(self):
        self.doctor_user = User.objects.create_user(
            username='concdoc',
            email='concdoc@hospital.local',
            password='password123',
            role=User.Roles.DOCTOR
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            specialization='Cardiology'
        )
        self.patient1 = User.objects.create_user(
            username='patienta',
            email='pa@example.com',
            password='password123',
            role=User.Roles.PATIENT
        )
        self.patient2 = User.objects.create_user(
            username='patientb',
            email='pb@example.com',
            password='password123',
            role=User.Roles.PATIENT
        )
        # Create a single available slot
        future_start = timezone.now() + datetime.timedelta(days=2)
        self.slot = AvailabilitySlot.objects.create(
            doctor=self.doctor_profile,
            start_datetime=future_start,
            end_datetime=future_start + datetime.timedelta(minutes=30),
            status='AVAILABLE'
        )

    def test_concurrent_booking_race_condition(self):
        results = []
        lock = threading.Lock()

        def run_booking(patient):
            # Each thread uses a new database connection
            from django.db import connection
            connection.connect()
            try:
                booking = book_appointment(self.slot.id, patient)
                with lock:
                    results.append(('success', patient.username, booking))
            except Exception as e:
                with lock:
                    results.append(('error', patient.username, e))
            finally:
                connection.close()

        # Create two parallel threads trying to book the same slot
        t1 = threading.Thread(target=run_booking, args=(self.patient1,))
        t2 = threading.Thread(target=run_booking, args=(self.patient2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r[0] == 'success']
        errors = [r for r in results if r[0] == 'error']

        # Verify that exactly one thread succeeds and the other fails
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)
        
        # Verify slot status in DB is BOOKED
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.status, 'BOOKED')
