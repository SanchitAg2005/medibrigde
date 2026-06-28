import uuid
from django.db import models
from django.conf import settings

class AvailabilitySlot(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('BOOKED', 'Booked'),
        ('IN_CONSULTATION', 'In Consultation'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('NO_SHOW', 'No Show'),
    ]

    doctor = models.ForeignKey(
        'doctors.DoctorProfile',
        on_delete=models.CASCADE,
        related_name='slots'
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='AVAILABLE'
    )

    class Meta:
        ordering = ['start_datetime']

    def __str__(self):
        return f"{self.doctor} - {self.start_datetime.strftime('%Y-%m-%d %H:%M')} ({self.status})"


class Booking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slot = models.OneToOneField(
        AvailabilitySlot,
        on_delete=models.CASCADE,
        related_name='booking'
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    reference_id = models.CharField(unique=True, max_length=50)
    google_event_id_doctor = models.CharField(max_length=255, blank=True, null=True)
    google_event_id_patient = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking {self.reference_id} - Patient: {self.patient} - Doctor: {self.slot.doctor}"

    def can_transition_to(self, new_status, user):
        """
        Validates if a given user can transition the booking status to new_status.
        Returns (bool, str) -> (is_allowed, error_message)
        """
        role = getattr(user, 'role', None)
        is_admin = (role == 'ADMIN') or user.is_superuser
        current_status = self.slot.status

        # Admin override allows any transition to logical next states
        if is_admin:
            valid_admin_transitions = {
                'BOOKED': ['IN_CONSULTATION', 'CANCELLED', 'NO_SHOW'],
                'IN_CONSULTATION': ['COMPLETED', 'CANCELLED'],
                'CANCELLED': [],
                'COMPLETED': [],
                'NO_SHOW': []
            }
            if new_status in valid_admin_transitions.get(current_status, []):
                return True, ""
            return False, f"Cannot transition from {current_status} to {new_status} even as admin."

        # Doctor permissions
        if role == 'DOCTOR':
            if self.slot.doctor.user != user:
                return False, "You are not the assigned doctor for this booking."
            
            valid_doctor_transitions = {
                'BOOKED': ['IN_CONSULTATION', 'CANCELLED', 'NO_SHOW'],
                'IN_CONSULTATION': ['COMPLETED'],
                'CANCELLED': [],
                'COMPLETED': [],
                'NO_SHOW': []
            }
            if new_status in valid_doctor_transitions.get(current_status, []):
                return True, ""
            return False, f"Doctors cannot transition from {current_status} to {new_status}."

        # Patient permissions
        if role == 'PATIENT':
            if self.patient != user:
                return False, "You are not the patient for this booking."
            
            valid_patient_transitions = {
                'BOOKED': ['CANCELLED'],
                'IN_CONSULTATION': [],
                'CANCELLED': [],
                'COMPLETED': [],
                'NO_SHOW': []
            }
            if new_status in valid_patient_transitions.get(current_status, []):
                return True, ""
            return False, f"Patients cannot transition from {current_status} to {new_status}."

        return False, "Invalid role or permission."

