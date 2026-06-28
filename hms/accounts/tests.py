from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from doctors.models import DoctorProfile

User = get_user_model()

class UserAuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.signup_url = reverse('signup')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')

    def test_patient_signup_success(self):
        response = self.client.post(self.signup_url, {
            'email': 'patient@example.com',
            'password': 'patientpassword123',
            'confirm_password': 'patientpassword123',
            'full_name': 'Test Patient',
            'role': User.Roles.PATIENT
        })
        self.assertEqual(response.status_code, 302)  # Should redirect to dashboard
        self.assertTrue(User.objects.filter(email='patient@example.com').exists())
        user = User.objects.get(email='patient@example.com')
        self.assertEqual(user.role, User.Roles.PATIENT)
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'Patient')
        self.assertEqual(user.approval_status, User.ApprovalStatus.APPROVED)

    def test_doctor_signup_missing_docs_fails(self):
        # Trying to sign up as DOCTOR without document files and specialization
        response = self.client.post(self.signup_url, {
            'email': 'doctor@example.com',
            'password': 'doctorpassword123',
            'confirm_password': 'doctorpassword123',
            'full_name': 'Test Doctor',
            'role': User.Roles.DOCTOR
        })
        self.assertEqual(response.status_code, 200)  # Renders form with errors
        self.assertFalse(User.objects.filter(email='doctor@example.com').exists())

    def test_doctor_signup_success(self):
        # Create mock file uploads
        mock_id = SimpleUploadedFile("id.pdf", b"file_content", content_type="application/pdf")
        mock_license = SimpleUploadedFile("license.pdf", b"file_content", content_type="application/pdf")
        mock_degree = SimpleUploadedFile("degree.pdf", b"file_content", content_type="application/pdf")

        response = self.client.post(self.signup_url, {
            'email': 'doctor@example.com',
            'password': 'doctorpassword123',
            'confirm_password': 'doctorpassword123',
            'full_name': 'Test Doctor',
            'role': User.Roles.DOCTOR,
            'specialization': 'Cardiology',
            'experience_years': 8,
            'hospital_name': 'Heart Clinic',
            'gov_id_file': mock_id,
            'medical_license_file': mock_license,
            'degree_certificate_file': mock_degree
        })
        
        self.assertEqual(response.status_code, 302)  # Should redirect to verification pending
        self.assertRedirects(response, reverse('verification_pending'))
        self.assertTrue(User.objects.filter(email='doctor@example.com').exists())
        
        user = User.objects.get(email='doctor@example.com')
        self.assertEqual(user.role, User.Roles.DOCTOR)
        self.assertEqual(user.approval_status, User.ApprovalStatus.PENDING)
        self.assertTrue(DoctorProfile.objects.filter(user=user).exists())

    def test_login_pending_doctor_redirects(self):
        # Create a pending doctor
        doctor = User.objects.create_user(
            email='pending@example.com',
            password='doctorpassword123',
            role=User.Roles.DOCTOR
        )
        self.assertEqual(doctor.approval_status, User.ApprovalStatus.PENDING)

        response = self.client.post(self.login_url, {
            'username': 'pending@example.com',
            'password': 'doctorpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('verification_pending'))

    def test_login_approved_doctor_succeeds(self):
        doctor = User.objects.create_user(
            email='approved@example.com',
            password='doctorpassword123',
            role=User.Roles.DOCTOR
        )
        doctor.approval_status = User.ApprovalStatus.APPROVED
        doctor.save()
        DoctorProfile.objects.create(user=doctor, specialization='General Medicine')

        response = self.client.post(self.login_url, {
            'username': 'approved@example.com',
            'password': 'doctorpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('dashboard'))
        
        # Follow to /dashboard/ and check it redirects to /doctors/dashboard/
        dashboard_response = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard_response.status_code, 302)
        self.assertEqual(dashboard_response['Location'], reverse('doctors:dashboard'))
        
        # Follow to /doctors/dashboard/ and check it returns 200
        final_response = self.client.get(reverse('doctors:dashboard'))
        self.assertEqual(final_response.status_code, 200)

    def test_login_rejected_doctor_fails(self):
        doctor = User.objects.create_user(
            email='rejected@example.com',
            password='doctorpassword123',
            role=User.Roles.DOCTOR
        )
        doctor.approval_status = User.ApprovalStatus.REJECTED
        doctor.save()

        response = self.client.post(self.login_url, {
            'username': 'rejected@example.com',
            'password': 'doctorpassword123'
        })
        self.assertEqual(response.status_code, 200) # Re-renders login with errors
        self.assertContains(response, "Your registration request has been rejected")

    def test_logout_terminates_session(self):
        patient = User.objects.create_user(
            email='session@example.com',
            password='password123',
            role=User.Roles.PATIENT
        )
        self.client.login(username='session@example.com', password='password123')
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, reverse('landing'))
