from django.db import models
from django.conf import settings

class AsyncTask(models.Model):
    class TaskTypes(models.TextChoices):
        SEND_EMAIL = 'SEND_EMAIL', 'Send Email'
        CREATE_CALENDAR = 'CREATE_CALENDAR', 'Create Calendar Event'
        UPDATE_CALENDAR = 'UPDATE_CALENDAR', 'Update Calendar Event'
        DELETE_CALENDAR = 'DELETE_CALENDAR', 'Delete Calendar Event'

    class Statuses(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        RUNNING = 'RUNNING', 'Running'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'

    task_type = models.CharField(max_length=50, choices=TaskTypes.choices)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Statuses.choices, default=Statuses.PENDING)
    retry_count = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.status} ({self.created_at})"

class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        actor_name = self.actor.username if self.actor else "System"
        return f"{actor_name} - {self.action} ({self.timestamp})"


class HospitalConfig(models.Model):
    name = models.CharField(max_length=150, default="MediBridge Medical Center")
    logo = models.FileField(upload_to='hospital_logo/', blank=True, null=True)
    address = models.CharField(max_length=255, default="100 Medical Center Parkway, Suite 400, Aura City")
    phone = models.CharField(max_length=50, default="+1 (555) 019-2831")
    email = models.EmailField(default="contact@medibridge.hospital.local")
    website = models.CharField(max_length=200, default="www.medibridge-clinic.local")
    working_hours = models.CharField(max_length=255, default="Mon - Fri: 8:00 AM - 6:00 PM, Sat: 9:00 AM - 2:00 PM")
    emergency_contact = models.CharField(max_length=100, default="+1 (555) 019-9111")

    class Meta:
        verbose_name = "Hospital Configuration"
        verbose_name_plural = "Hospital Configuration"

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return self.name


