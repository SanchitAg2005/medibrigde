from django.core.exceptions import ValidationError
from django.db import transaction
from appointments.models import Booking
from medical_records.models import MedicalRecord, MedicalReport
from common.utils import log_event

def create_medical_record(booking_id, doctor_user, diagnosis, symptoms, consultation_notes="", prescription_json=None, follow_up_date=None, actor=None, ip_address=None):
    """
    Creates a new Medical Record (EMR) for a booking and transitions its status to COMPLETED.
    """
    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)
        except Booking.DoesNotExist:
            raise ValidationError("Booking does not exist.")

        # 1. Verify doctor ownership
        if booking.slot.doctor.user != doctor_user:
            raise ValidationError("You are not the assigned doctor for this appointment.")

        # 2. Check transition permission to COMPLETED
        is_allowed, error_msg = booking.can_transition_to('COMPLETED', doctor_user)
        if not is_allowed:
            raise ValidationError(f"Cannot complete this consultation: {error_msg}")

        # 3. Create MedicalRecord
        record = MedicalRecord.objects.create(
            booking=booking,
            patient=booking.patient,
            doctor=booking.slot.doctor,
            diagnosis=diagnosis,
            symptoms=symptoms,
            consultation_notes=consultation_notes,
            prescription_json=prescription_json or {},
            follow_up_date=follow_up_date
        )

        # 4. Mark slot as completed
        slot = booking.slot
        slot.status = 'COMPLETED'
        slot.save()

        log_event(
            action="MEDICAL_RECORD_CREATED",
            actor=actor or doctor_user,
            ip_address=ip_address,
            details={
                "record_id": str(record.id),
                "booking_id": str(booking.id),
                "patient_id": str(booking.patient.id),
                "doctor_id": str(booking.slot.doctor.id)
            }
        )

        return record


def upload_medical_report(patient, file, report_type, title="", medical_record_id=None, actor=None, ip_address=None):
    """
    Uploads a patient medical report (MRI, scan, blood test, etc.).
    Can optionally be linked to a specific consultation's EMR.
    """
    medical_record = None
    if medical_record_id:
        try:
            medical_record = MedicalRecord.objects.get(pk=medical_record_id)
            if medical_record.patient != patient:
                raise ValidationError("Medical record does not belong to this patient.")
        except MedicalRecord.DoesNotExist:
            raise ValidationError("Medical record does not exist.")

    report = MedicalReport.objects.create(
        patient=patient,
        medical_record=medical_record,
        title=title,
        file=file,
        report_type=report_type
    )

    log_event(
        action="MEDICAL_REPORT_UPLOADED",
        actor=actor or patient,
        ip_address=ip_address,
        details={
            "report_id": str(report.id),
            "patient_id": str(patient.id),
            "report_type": report_type,
            "linked_to_record": medical_record_id is not None
        }
    )

    return report
