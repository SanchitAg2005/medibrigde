from django.db import models
from django.conf import settings
from django.db.models import Avg

class DoctorProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='doctor_profile'
    )
    specialization = models.CharField(max_length=100)
    experience_years = models.PositiveIntegerField(default=0)
    hospital_name = models.CharField(max_length=150)
    bio = models.TextField(blank=True)
    languages = models.CharField(max_length=150, blank=True)
    qualification = models.CharField(max_length=200, blank=True)
    
    # Upload paths for verification documents
    gov_id_file = models.FileField(upload_to='doctor_documents/', blank=True, null=True)
    medical_license_file = models.FileField(upload_to='doctor_documents/', blank=True, null=True)
    degree_certificate_file = models.FileField(upload_to='doctor_documents/', blank=True, null=True)
    
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username} - {self.specialization}"


class WorkingHours(models.Model):
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='working_hours'
    )
    day_of_week = models.IntegerField(help_text="0=Monday, 6=Sunday")
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.PositiveIntegerField(default=30)
    buffer_time_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "Working Hours"
        unique_together = ('doctor', 'day_of_week')

    def __str__(self):
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_str = days[self.day_of_week] if 0 <= self.day_of_week < 7 else f"Day {self.day_of_week}"
        return f"{self.doctor} - {day_str}: {self.start_time} to {self.end_time}"


class DoctorLeave(models.Model):
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='leaves'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)

    def __str__(self):
        return f"{self.doctor} Leave: {self.start_date} to {self.end_date}"


class Review(models.Model):
    booking = models.OneToOneField(
        'appointments.Booking',
        on_delete=models.CASCADE,
        related_name='review'
    )
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_reviews'
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_doctor_rating()

    def delete(self, *args, **kwargs):
        doctor = self.doctor
        super().delete(*args, **kwargs)
        self.update_doctor_rating_for_doctor(doctor)

    def update_doctor_rating(self):
        self.update_doctor_rating_for_doctor(self.doctor)

    @staticmethod
    def update_doctor_rating_for_doctor(doctor):
        stats = doctor.reviews.aggregate(
            avg_rating=Avg('rating'),
            count=models.Count('id')
        )
        doctor.average_rating = stats['avg_rating'] or 0.00
        doctor.total_reviews = stats['count'] or 0
        doctor.save(update_fields=['average_rating', 'total_reviews'])

    def __str__(self):
        return f"Review by {self.patient} for {self.doctor} - {self.rating} stars"


