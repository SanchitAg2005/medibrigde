from django.core.exceptions import ValidationError
from appointments.models import Booking
from doctors.models import Review
from common.utils import log_event

def create_review(booking_id, patient, rating, comment="", actor=None, ip_address=None):
    """
    Submits a review for a completed appointment.
    """
    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        raise ValidationError("Booking does not exist.")

    # 1. Booking must belong to the patient
    if booking.patient != patient:
        raise ValidationError("You cannot review a booking that does not belong to you.")

    # 2. Only completed appointments can be reviewed
    if booking.slot.status != 'COMPLETED':
        raise ValidationError("You can only review completed appointments.")

    # 3. Booking must not have a review already
    if hasattr(booking, 'review'):
        raise ValidationError("A review has already been submitted for this appointment.")

    # 4. Rating must be 1-5
    if rating < 1 or rating > 5:
        raise ValidationError("Rating must be between 1 and 5.")

    review = Review.objects.create(
        booking=booking,
        doctor=booking.slot.doctor,
        patient=patient,
        rating=rating,
        comment=comment
    )

    log_event(
        action="REVIEW_SUBMITTED",
        actor=actor or patient,
        ip_address=ip_address,
        details={
            "review_id": review.id,
            "booking_id": str(booking.id),
            "doctor_id": str(booking.slot.doctor.id),
            "rating": rating
        }
    )

    return review
