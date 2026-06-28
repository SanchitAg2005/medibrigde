from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

class CustomUserManager(BaseUserManager):
    def create_user(self, username=None, email=None, password=None, **extra_fields):
        # Resolve email/username if only email-like values are passed
        if email is None and username is not None and '@' in username:
            email = username
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        
        if not username:
            username = email
            
        extra_fields.setdefault('username', username)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username=None, email=None, password=None, **extra_fields):
        if email is None and username is not None and '@' in username:
            email = username
        if not email:
            raise ValueError('Superuser must have an email.')
            
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'ADMIN')
        extra_fields.setdefault('approval_status', 'APPROVED')

        if username is None:
            username = email
        return self.create_user(username=username, email=email, password=password, **extra_fields)

class CustomUser(AbstractUser):
    class Roles(models.TextChoices):
        DOCTOR = 'DOCTOR', 'Doctor'
        PATIENT = 'PATIENT', 'Patient'
        ADMIN = 'ADMIN', 'Admin'

    class ApprovalStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        SUSPENDED = 'SUSPENDED', 'Suspended'
        REMOVED = 'REMOVED', 'Removed'

    # Override email to be required and unique
    email = models.EmailField(unique=True)
    
    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.PATIENT
    )
    
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.APPROVED  # Patients and Admins are approved by default
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        # Doctors default to PENDING status upon creation
        if self.role == self.Roles.DOCTOR and not self.pk:
            self.approval_status = self.ApprovalStatus.PENDING
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

