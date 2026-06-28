from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from doctors.models import DoctorProfile, WorkingHours
from appointments.models import AvailabilitySlot, Booking

User = get_user_model()

class DoctorDashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.doctor_user = User.objects.create_user(
            email='doctor@example.com',
            password='doctorpassword123',
            role=User.Roles.DOCTOR
        )
        self.doctor_user.approval_status = User.ApprovalStatus.APPROVED
        self.doctor_user.save()
        
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            specialization='Cardiology',
            experience_years=10,
            hospital_name='Heart Hospital'
        )
        
        self.dashboard_url = reverse('doctors:dashboard')
        self.config_url = reverse('doctors:configure_working_hours')

    def test_dashboard_requires_login(self):
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)  # Redirects to login

    def test_dashboard_renders_successfully(self):
        self.client.login(username='doctor@example.com', password='doctorpassword123')
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'doctors/dashboard.html')

    def test_configure_working_hours_get(self):
        self.client.login(username='doctor@example.com', password='doctorpassword123')
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'doctors/configure_working_hours.html')
        self.assertIn('days', response.context)

    def test_configure_working_hours_post_generates_slots(self):
        self.client.login(username='doctor@example.com', password='doctorpassword123')
        
        # Configure working hours: active on Monday (0) from 09:00 to 12:00
        # slot duration 30 mins, buffer 0 mins
        response = self.client.post(self.config_url, {
            'active_0': 'on',
            'start_0': '09:00',
            'end_0': '12:00',
            'duration_0': '30',
            'buffer_0': '0',
            # active on Wednesday (2) from 13:00 to 16:00
            'active_2': 'on',
            'start_2': '13:00',
            'end_2': '16:00',
            'duration_2': '30',
            'buffer_2': '10'
        })
        
        self.assertEqual(response.status_code, 302)  # Should redirect with success message
        self.assertRedirects(response, self.dashboard_url)
        
        # Verify WorkingHours records exist
        self.assertTrue(WorkingHours.objects.filter(doctor=self.doctor_profile, day_of_week=0).exists())
        self.assertTrue(WorkingHours.objects.filter(doctor=self.doctor_profile, day_of_week=2).exists())
        
        # Verify AvailabilitySlot objects were automatically generated
        generated_slots = AvailabilitySlot.objects.filter(doctor=self.doctor_profile)
        self.assertTrue(generated_slots.exists())
        # We expect a good count of generated slots for Monday/Wednesday in the next 14 days
        self.assertGreater(generated_slots.count(), 0)
