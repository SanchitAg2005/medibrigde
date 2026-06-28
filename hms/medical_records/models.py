import uuid
from django.db import models
from django.conf import settings

class MedicalRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(
        'appointments.Booking',
        on_delete=models.CASCADE,
        related_name='medical_record'
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='medical_records'
    )
    doctor = models.ForeignKey(
        'doctors.DoctorProfile',
        on_delete=models.CASCADE,
        related_name='medical_records'
    )
    diagnosis = models.TextField()
    symptoms = models.TextField()
    consultation_notes = models.TextField(blank=True)
    prescription_json = models.JSONField(default=dict, blank=True)
    follow_up_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"EMR for {self.patient} by Dr. {self.doctor.user.last_name} on {self.created_at.strftime('%Y-%m-%d')}"


class MedicalReport(models.Model):
    REPORT_TYPES = [
        ('BLOOD_TEST', 'Blood Test'),
        ('MRI', 'MRI'),
        ('CT_SCAN', 'CT Scan'),
        ('X_RAY', 'X-Ray'),
        ('PRESCRIPTION', 'Prescription'),
        ('OTHER', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='medical_reports'
    )
    # Optional link to support both independent patient uploads and doctor attachments
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports'
    )
    title = models.CharField(max_length=150, blank=True)
    file = models.FileField(upload_to='medical_reports/')
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        title_str = self.title or f"Report ({self.get_report_type_display()})"
        return f"{self.patient} - {title_str}"

