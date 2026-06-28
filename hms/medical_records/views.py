from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from appointments.models import Booking
from medical_records.services import create_medical_record, upload_medical_report

@login_required
def create_medical_record_view(request, booking_id):
    """
    Doctor submits EMR for a completed consultation.
    """
    if request.user.role not in ['DOCTOR', 'ADMIN']:
        messages.error(request, "Only doctors or admins can create medical records.")
        return redirect('dashboard')

    booking = get_object_or_404(Booking, pk=booking_id)

    if request.method == 'POST':
        diagnosis = request.POST.get('diagnosis')
        symptoms = request.POST.get('symptoms')
        notes = request.POST.get('consultation_notes', '')
        follow_up = request.POST.get('follow_up_date') or None
        prescription = {} 

        try:
            create_medical_record(
                booking_id=booking_id,
                doctor_user=request.user,
                diagnosis=diagnosis,
                symptoms=symptoms,
                consultation_notes=notes,
                prescription_json=prescription,
                follow_up_date=follow_up,
                actor=request.user,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, f"Medical record successfully saved for patient {booking.patient.get_full_name()}.")
            return redirect('doctors:dashboard')
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, "An unexpected error occurred while saving the medical record.")

    return render(request, 'medical_records/create_record.html', {'booking': booking})


@login_required
def upload_report_view(request):
    """
    Patient uploads an independent medical report (scan, lab test, etc.).
    """
    if request.user.role != 'PATIENT':
        messages.error(request, "Only patients can upload reports.")
        return redirect('dashboard')

    if request.method == 'POST':
        title = request.POST.get('title', '')
        report_type = request.POST.get('report_type')
        uploaded_file = request.FILES.get('file')

        if not uploaded_file:
            messages.error(request, "Please select a file to upload.")
        else:
            try:
                upload_medical_report(
                    patient=request.user,
                    file=uploaded_file,
                    report_type=report_type,
                    title=title,
                    actor=request.user,
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                messages.success(request, "Medical report successfully uploaded.")
                return redirect('patients:dashboard')
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, "An unexpected error occurred during report upload.")

    return render(request, 'medical_records/upload_report.html')

