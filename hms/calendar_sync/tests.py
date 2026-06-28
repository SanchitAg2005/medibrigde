import datetime
# pyrefly: ignore [missing-import]
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock

from calendar_sync.models import GoogleOAuthToken
from calendar_sync.services import (
    get_google_credentials,
    sync_booking_event,
    delete_booking_event
)
from doctors.models import DoctorProfile
from appointments.models import AvailabilitySlot, Booking

User = get_user_model()

class GoogleCalendarIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.connect_url = reverse('calendar_sync:connect')
        self.callback_url = reverse('calendar_sync:callback')

        # Create Patient User
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

        # Create Doctor User
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

        # Create Slot & Booking
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

    def test_oauth_redirect_requires_login(self):
        response = self.client.get(self.connect_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response['Location'])

    @patch('django.conf.settings.GOOGLE_CLIENT_ID', None)
    def test_oauth_redirect_missing_settings(self):
        self.client.login(username='alice@example.com', password='password123')
        response = self.client.get(self.connect_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    @patch('django.conf.settings.GOOGLE_CLIENT_ID', 'test-client-id')
    @patch('django.conf.settings.GOOGLE_CLIENT_SECRET', 'test-client-secret')
    @patch('django.conf.settings.GOOGLE_REDIRECT_URI', 'http://testserver/callback')
    @patch('google_auth_oauthlib.flow.Flow.from_client_config')
    def test_oauth_redirect_success(self, mock_flow_init):
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ('https://accounts.google.com/o/oauth2/auth?state=xyz', 'xyz')
        mock_flow_init.return_value = mock_flow

        self.client.login(username='alice@example.com', password='password123')
        response = self.client.get(self.connect_url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://accounts.google.com/o/oauth2/auth?state=xyz')
        self.assertEqual(self.client.session['oauth_state'], 'xyz')

    def test_oauth_callback_requires_login(self):
        response = self.client.get(self.callback_url)
        self.assertEqual(response.status_code, 302)

    def test_oauth_callback_missing_state(self):
        self.client.login(username='alice@example.com', password='password123')
        response = self.client.get(self.callback_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    @patch('django.conf.settings.GOOGLE_CLIENT_ID', 'test-client-id')
    @patch('django.conf.settings.GOOGLE_CLIENT_SECRET', 'test-client-secret')
    @patch('django.conf.settings.GOOGLE_REDIRECT_URI', 'http://testserver/callback')
    @patch('google_auth_oauthlib.flow.Flow.from_client_config')
    def test_oauth_callback_success(self, mock_flow_init):
        # Mocking credentials object returned by flow
        mock_creds = MagicMock()
        mock_creds.token = 'mock-access-token'
        mock_creds.refresh_token = 'mock-refresh-token'
        mock_creds.expiry = timezone.now() + datetime.timedelta(hours=1)

        mock_flow = MagicMock()
        mock_flow.credentials = mock_creds
        mock_flow_init.return_value = mock_flow

        self.client.login(username='alice@example.com', password='password123')
        
        # Set state in session
        session = self.client.session
        session['oauth_state'] = 'xyz'
        session.save()

        response = self.client.get(self.callback_url + '?state=xyz&code=auth-code')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

        # Verify GoogleOAuthToken was saved
        token_record = GoogleOAuthToken.objects.get(user=self.patient_user)
        self.assertEqual(token_record.access_token, 'mock-access-token')
        self.assertEqual(token_record.refresh_token, 'mock-refresh-token')

    def test_get_google_credentials_no_token(self):
        creds = get_google_credentials(self.patient_user)
        self.assertIsNone(creds)

    def test_get_google_credentials_valid_token(self):
        expiry = timezone.now() + datetime.timedelta(hours=1)
        GoogleOAuthToken.objects.create(
            user=self.patient_user,
            access_token='access',
            refresh_token='refresh',
            token_expiry=expiry
        )
        creds = get_google_credentials(self.patient_user)
        self.assertIsNotNone(creds)
        self.assertEqual(creds.token, 'access')

    @patch('requests.post')
    def test_get_google_credentials_auto_refresh_success(self, mock_post):
        # Token is expired (expired 10 mins ago)
        expiry = timezone.now() - datetime.timedelta(minutes=10)
        token_record = GoogleOAuthToken.objects.create(
            user=self.patient_user,
            access_token='old_access',
            refresh_token='refresh',
            token_expiry=expiry
        )

        # Mock the requests.post response for refreshing token
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_access',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response

        creds = get_google_credentials(self.patient_user)
        self.assertIsNotNone(creds)
        self.assertEqual(creds.token, 'new_access')

        # Verify database was updated
        token_record.refresh_from_db()
        self.assertEqual(token_record.access_token, 'new_access')
        self.assertTrue(token_record.token_expiry > timezone.now())

    @patch('requests.post')
    def test_get_google_credentials_auto_refresh_failure(self, mock_post):
        expiry = timezone.now() - datetime.timedelta(minutes=10)
        token_record = GoogleOAuthToken.objects.create(
            user=self.patient_user,
            access_token='old_access',
            refresh_token='refresh',
            token_expiry=expiry
        )

        # Mock the requests.post response to return a 400 Bad Request
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = 'invalid_grant'
        mock_post.return_value = mock_response

        creds = get_google_credentials(self.patient_user)
        self.assertIsNone(creds)

    @patch('calendar_sync.services.get_google_credentials')
    @patch('calendar_sync.services.build')
    def test_sync_booking_event_success(self, mock_build, mock_get_creds):
        # Set up mock credentials for doctor and patient
        mock_creds = MagicMock()
        mock_get_creds.side_effect = lambda user: mock_creds

        # Mock Google Calendar API client
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        
        # mock insert return value
        mock_events.insert.return_value.execute.side_effect = [
            {'id': 'event-id-doctor'}, # Doctor's calendar event ID
            {'id': 'event-id-patient'}, # Patient's calendar event ID
        ]
        mock_build.return_value = mock_service

        # Invoke sync_booking_event
        sync_booking_event(self.booking)

        # Refresh from database and check event IDs saved
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.google_event_id_doctor, 'event-id-doctor')
        self.assertEqual(self.booking.google_event_id_patient, 'event-id-patient')

    @patch('calendar_sync.services.get_google_credentials')
    @patch('calendar_sync.services.build')
    def test_delete_booking_event_success(self, mock_build, mock_get_creds):
        self.booking.google_event_id_doctor = 'event-id-doctor'
        self.booking.google_event_id_patient = 'event-id-patient'
        self.booking.save()

        mock_creds = MagicMock()
        mock_get_creds.side_effect = lambda user: mock_creds

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_build.return_value = mock_service

        # Invoke delete_booking_event
        delete_booking_event(self.booking)

        # Refresh from database and check event IDs are deleted/cleared
        self.booking.refresh_from_db()
        self.assertIsNone(self.booking.google_event_id_doctor)
        self.assertIsNone(self.booking.google_event_id_patient)
        
        mock_events.delete.assert_any_call(calendarId='primary', eventId='event-id-doctor')
        mock_events.delete.assert_any_call(calendarId='primary', eventId='event-id-patient')
