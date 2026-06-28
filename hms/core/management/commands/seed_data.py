import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.base import ContentFile

from doctors.models import DoctorProfile, WorkingHours, DoctorLeave, Review
from appointments.models import AvailabilitySlot, Booking
from medical_records.models import MedicalRecord, MedicalReport
from common.models import AsyncTask, AuditLog
from appointments.services import generate_slots, book_appointment
from medical_records.services import create_medical_record, upload_medical_report
from doctors.services import create_review
from common.utils import log_event

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds realistic demo data into the AuraHealth HMS database."

    def handle(self, *args, **options):
        self.stdout.write("Clearing existing data...")
        Review.objects.all().delete()
        MedicalReport.objects.all().delete()
        MedicalRecord.objects.all().delete()
        Booking.objects.all().delete()
        AvailabilitySlot.objects.all().delete()
        WorkingHours.objects.all().delete()
        DoctorLeave.objects.all().delete()
        DoctorProfile.objects.all().delete()
        # Delete users except superusers
        User.objects.filter(is_superuser=False).delete()
        AsyncTask.objects.all().delete()
        AuditLog.objects.all().delete()

        self.stdout.write("Creating users...")
        # 1. Admin / Superusers
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            email='admin@hospital.local',
            is_superuser=True,
            is_staff=True
        )
        admin_user.set_password('adminpassword123')
        admin_user.role = User.Roles.ADMIN
        admin_user.approval_status = User.ApprovalStatus.APPROVED
        admin_user.save()

        demo_admin, _ = User.objects.get_or_create(
            username='demo_admin',
            email='demo_admin@hospital.local',
            is_superuser=True,
            is_staff=True
        )
        demo_admin.set_password('hms_admin123')
        demo_admin.role = User.Roles.ADMIN
        demo_admin.approval_status = User.ApprovalStatus.APPROVED
        demo_admin.save()

        # 2. Patients
        p_demo = User.objects.create_user(
            username='demo_patient',
            email='demo_patient@example.com',
            password='hms_patient123',
            role=User.Roles.PATIENT,
            first_name='David',
            last_name='Miller'
        )
        p_demo.approval_status = User.ApprovalStatus.APPROVED
        p_demo.save()

        # 2. Patients
        p1 = User.objects.create_user(
            username='alice_green',
            email='alice@example.com',
            password='password123',
            role=User.Roles.PATIENT,
            first_name='Alice',
            last_name='Green'
        )
        p1.approval_status = User.ApprovalStatus.APPROVED
        p1.save()

        p2 = User.objects.create_user(
            username='bob_blue',
            email='bob@example.com',
            password='password123',
            role=User.Roles.PATIENT,
            first_name='Bob',
            last_name='Blue'
        )
        p2.approval_status = User.ApprovalStatus.APPROVED
        p2.save()

        p3 = User.objects.create_user(
            username='charlie_orange',
            email='charlie@example.com',
            password='password123',
            role=User.Roles.PATIENT,
            first_name='Charlie',
            last_name='Orange'
        )
        p3.approval_status = User.ApprovalStatus.APPROVED
        p3.save()

        # 3. Doctors
        d1_user = User.objects.create_user(
            username='dr_smith',
            email='smith@hospital.local',
            password='password123',
            role=User.Roles.DOCTOR,
            first_name='John',
            last_name='Smith'
        )
        d1_user.approval_status = User.ApprovalStatus.APPROVED
        d1_user.save()
        dr_smith = DoctorProfile.objects.create(
            user=d1_user,
            specialization='Cardiology',
            experience_years=12,
            hospital_name='AuraHealth Cardiology Clinic',
            bio='Dr. John Smith is an experienced cardiologist focusing on preventative heart care.',
            languages='English, Spanish',
            qualification='MBBS, MD, DM (Cardiology)'
        )

        d2_user = User.objects.create_user(
            username='dr_jenkins',
            email='jenkins@hospital.local',
            password='password123',
            role=User.Roles.DOCTOR,
            first_name='Sarah',
            last_name='Jenkins'
        )
        d2_user.approval_status = User.ApprovalStatus.APPROVED
        d2_user.save()
        dr_jenkins = DoctorProfile.objects.create(
            user=d2_user,
            specialization='Pediatrics',
            experience_years=8,
            hospital_name='AuraHealth Childrens Clinic',
            bio='Dr. Sarah Jenkins has a passion for childhood development and wellness programs.',
            languages='English',
            qualification='MBBS, MD (Pediatrics)'
        )

        # Pending doctor (Emily Taylor)
        d3_user = User.objects.create_user(
            username='dr_taylor',
            email='taylor@hospital.local',
            password='password123',
            role=User.Roles.DOCTOR,
            first_name='Emily',
            last_name='Taylor'
        )
        d3_user.approval_status = User.ApprovalStatus.PENDING
        d3_user.save()
        dr_taylor = DoctorProfile.objects.create(
            user=d3_user,
            specialization='General Medicine',
            experience_years=5,
            hospital_name='AuraHealth City Clinic',
            bio='Dr. Emily Taylor provides comprehensive primary care services.',
            qualification='MBBS, MD'
        )

        # Approved demo doctor (Robert Chen)
        d_demo_user = User.objects.create_user(
            username='demo_doctor',
            email='demo_doctor@hospital.local',
            password='hms_doctor123',
            role=User.Roles.DOCTOR,
            first_name='Robert',
            last_name='Chen'
        )
        d_demo_user.approval_status = User.ApprovalStatus.APPROVED
        d_demo_user.save()
        dr_demo = DoctorProfile.objects.create(
            user=d_demo_user,
            specialization='Dermatology',
            experience_years=10,
            hospital_name='AuraHealth Skin Clinic',
            bio='Dr. Robert Chen specializes in medical and cosmetic dermatology with a focus on skin wellness.',
            languages='English, Mandarin',
            qualification='MBBS, MD (Dermatology)'
        )

        self.stdout.write("Configuring working hours and leaves...")
        # Working hours
        # Smith: Mon (0) 09:00-12:00, Wed (2) 13:00-16:00
        WorkingHours.objects.create(
            doctor=dr_smith,
            day_of_week=0,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(12, 0),
            slot_duration_minutes=30,
            buffer_time_minutes=0
        )
        WorkingHours.objects.create(
            doctor=dr_smith,
            day_of_week=2,
            start_time=datetime.time(13, 0),
            end_time=datetime.time(16, 0),
            slot_duration_minutes=30,
            buffer_time_minutes=10
        )

        # Jenkins: Tue (1) 10:00-13:00, Thu (3) 14:00-17:00
        WorkingHours.objects.create(
            doctor=dr_jenkins,
            day_of_week=1,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(13, 0),
            slot_duration_minutes=30,
            buffer_time_minutes=0
        )
        WorkingHours.objects.create(
            doctor=dr_jenkins,
            day_of_week=3,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(17, 0),
            slot_duration_minutes=30,
            buffer_time_minutes=5
        )

        # Chen (dr_demo): Wed (2) 09:00-12:00, Fri (4) 13:00-16:00
        WorkingHours.objects.create(
            doctor=dr_demo,
            day_of_week=2,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(12, 0),
            slot_duration_minutes=30,
            buffer_time_minutes=0
        )
        WorkingHours.objects.create(
            doctor=dr_demo,
            day_of_week=4,
            start_time=datetime.time(13, 0),
            end_time=datetime.time(16, 0),
            slot_duration_minutes=30,
            buffer_time_minutes=10
        )

        # Doctor Leave for Jenkins (next Friday)
        today = timezone.now().date()
        leave_date = today + datetime.timedelta(days=(4 - today.weekday() + 7) % 7)
        DoctorLeave.objects.create(
            doctor=dr_jenkins,
            start_date=leave_date,
            end_date=leave_date,
            reason="Medical Conference"
        )

        self.stdout.write("Generating availability slots...")
        # Generate slots for next 14 days
        end_date = today + datetime.timedelta(days=14)
        generate_slots(dr_smith, today, end_date, actor=admin_user)
        generate_slots(dr_jenkins, today, end_date, actor=admin_user)
        generate_slots(dr_demo, today, end_date, actor=admin_user)

        self.stdout.write("Booking appointments...")
        # Fetch some generated slots to create bookings
        smith_slots = AvailabilitySlot.objects.filter(doctor=dr_smith, status='AVAILABLE')
        jenkins_slots = AvailabilitySlot.objects.filter(doctor=dr_jenkins, status='AVAILABLE')

        if smith_slots.exists():
            # 1. Upcoming booking for Alice with Smith
            slot_alice = smith_slots[0]
            booking_alice = book_appointment(slot_alice.id, p1, actor=p1)
            self.stdout.write(f"Created upcoming booking for Alice Green: {booking_alice.reference_id}")

            # 2. Completed consultation for Charlie with Smith (in the past, we force it completed)
            if len(smith_slots) > 1:
                slot_charlie = smith_slots[1]
                booking_charlie = book_appointment(slot_charlie.id, p3, actor=p3)
                
                # Transition status to IN_CONSULTATION so the doctor can write the EMR
                slot_charlie.status = 'IN_CONSULTATION'
                slot_charlie.save()
                
                # Write EMR (transitions to COMPLETED)
                prescription = {
                    "medications": [
                        {"name": "Lisinopril", "dosage": "10mg", "frequency": "Once daily", "duration": "30 days"}
                    ]
                }
                create_medical_record(
                    booking_id=booking_charlie.id,
                    doctor_user=d1_user,
                    diagnosis="Essential Hypertension",
                    symptoms="Recurrent headaches, systolic reading of 152/94.",
                    consultation_notes="Patient advised to begin low-sodium diet and log daily BP.",
                    prescription_json=prescription,
                    follow_up_date=today + datetime.timedelta(days=30),
                    actor=d1_user
                )

                # Attach a report to consultation EMR
                mock_file = ContentFile(b"Mock blood panel analysis content", name="blood_panel.txt")
                upload_medical_report(
                    patient=p3,
                    file=mock_file,
                    report_type="BLOOD_TEST",
                    title="Charlie Orange Lipid Panel",
                    medical_record_id=booking_charlie.medical_record.id,
                    actor=d1_user
                )

                # Add a Review
                create_review(
                    booking_id=booking_charlie.id,
                    patient=p3,
                    rating=5,
                    comment="Dr. Smith was very attentive and explained my treatment plan clearly.",
                    actor=p3
                )
                self.stdout.write(f"Created completed consult + EMR + review for Charlie Orange: {booking_charlie.reference_id}")

        if jenkins_slots.exists():
            # 3. No Show appointment for Bob with Jenkins
            slot_bob = jenkins_slots[0]
            booking_bob = book_appointment(slot_bob.id, p2, actor=p2)
            slot_bob.status = 'NO_SHOW'
            slot_bob.save()
            self.stdout.write(f"Created No-Show booking for Bob Blue: {booking_bob.reference_id}")

        # 4. Independent report upload by Alice Green (Workflow A: exists before appointment)
        mock_scan = ContentFile(b"Mock MRI scan report content", name="mri_scan.pdf")
        upload_medical_report(
            patient=p1,
            file=mock_scan,
            report_type="MRI",
            title="Alice Green Knee MRI Scan",
            actor=p1
        )
        self.stdout.write("Created patient-uploaded independent medical report.")

        # Log some additional system audit logs
        log_event("DOCTOR_REGISTRATION_SUBMITTED", actor=d3_user, details={"doctor": d3_user.username})
        log_event("SYSTEM_INITIALIZATION", details={"description": "Successfully seeded demo data"})

        self.stdout.write(self.style.SUCCESS("Database seeded successfully with modern HMS demo data!"))
