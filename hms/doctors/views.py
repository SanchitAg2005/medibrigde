import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction

from doctors.models import DoctorProfile, WorkingHours, DoctorLeave, Review
from doctors.services import create_review
from appointments.models import Booking
from calendar_sync.models import GoogleOAuthToken
from appointments.services import generate_slots

@login_required
def dashboard_view(request):
    doctor_profile = DoctorProfile.objects.filter(user=request.user).first()
    if not doctor_profile:
        messages.error(request, "Doctor profile not configured. Please contact administrator.")
        return redirect('dashboard')

    today = timezone.now().date()
    
    # Scheduled appointments for today (in chronological order)
    today_bookings = Booking.objects.filter(
        slot__doctor=doctor_profile,
        slot__start_datetime__date=today
    ).order_by('slot__start_datetime')

    # All upcoming/past appointments
    all_bookings = Booking.objects.filter(
        slot__doctor=doctor_profile
    ).order_by('-slot__start_datetime')

    # Doctor schedule configuration
    working_hours = WorkingHours.objects.filter(doctor=doctor_profile).order_by('day_of_week')
    leaves = DoctorLeave.objects.filter(doctor=doctor_profile).order_by('-start_date')
    
    # Patient Reviews
    reviews = Review.objects.filter(doctor=doctor_profile).order_by('-created_at')
    
    # Calendar status
    has_calendar_connected = GoogleOAuthToken.objects.filter(user=request.user).exists()

    context = {
        'doctor_profile': doctor_profile,
        'today_bookings': today_bookings,
        'all_bookings': all_bookings,
        'working_hours': working_hours,
        'leaves': leaves,
        'reviews': reviews,
        'has_calendar_connected': has_calendar_connected,
    }
    return render(request, 'doctors/dashboard.html', context)

@login_required
def submit_review_view(request, booking_id):
    if request.method == 'POST':
        rating_raw = request.POST.get('rating')
        comment = request.POST.get('comment', '')
        
        try:
            rating = int(rating_raw)
            create_review(
                booking_id=booking_id,
                patient=request.user,
                rating=rating,
                comment=comment,
                actor=request.user,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, "Thank you! Your review has been successfully submitted.")
        except ValidationError as e:
            messages.error(request, str(e))
        except ValueError:
            messages.error(request, "Invalid rating value provided.")
        except Exception as e:
            messages.error(request, "An unexpected error occurred while submitting your review.")
            
    return redirect('patients:dashboard')

@login_required
def configure_working_hours_view(request):
    doctor_profile = DoctorProfile.objects.filter(user=request.user).first()
    if not doctor_profile:
        messages.error(request, "Doctor profile not configured. Please contact administrator.")
        return redirect('dashboard')

    days_list = [
        {"day": 0, "name": "Monday"},
        {"day": 1, "name": "Tuesday"},
        {"day": 2, "name": "Wednesday"},
        {"day": 3, "name": "Thursday"},
        {"day": 4, "name": "Friday"},
        {"day": 5, "name": "Saturday"},
        {"day": 6, "name": "Sunday"},
    ]

    if request.method == 'POST':
        try:
            with transaction.atomic():
                for day_item in days_list:
                    day_num = day_item["day"]
                    is_active = request.POST.get(f'active_{day_num}') == 'on'
                    
                    if is_active:
                        start_str = request.POST.get(f'start_{day_num}')
                        end_str = request.POST.get(f'end_{day_num}')
                        duration_str = request.POST.get(f'duration_{day_num}', '30')
                        buffer_str = request.POST.get(f'buffer_{day_num}', '0')
                        
                        if not start_str or not end_str:
                            raise ValidationError(f"Please provide start and end times for {day_item['name']}.")
                            
                        # Convert to time objects
                        start_time = datetime.datetime.strptime(start_str, "%H:%M").time()
                        end_time = datetime.datetime.strptime(end_str, "%H:%M").time()
                        
                        if end_time <= start_time:
                            raise ValidationError(f"End time must be after start time for {day_item['name']}.")
                            
                        WorkingHours.objects.update_or_create(
                            doctor=doctor_profile,
                            day_of_week=day_num,
                            defaults={
                                'start_time': start_time,
                                'end_time': end_time,
                                'slot_duration_minutes': int(duration_str),
                                'buffer_time_minutes': int(buffer_str)
                            }
                        )
                    else:
                        # Inactive, delete existing
                        WorkingHours.objects.filter(doctor=doctor_profile, day_of_week=day_num).delete()
                
                # Auto generate slots for the next 14 days
                today = timezone.now().date()
                end_date = today + datetime.timedelta(days=14)
                slots_created = generate_slots(doctor_profile, today, end_date, actor=request.user)
                
                messages.success(request, f"Working hours saved successfully! {slots_created} new appointment slots generated for the next 14 days.")
                return redirect('doctors:dashboard')
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")

    # Pre-populate existing working hours
    existing_wh = {wh.day_of_week: wh for wh in WorkingHours.objects.filter(doctor=doctor_profile)}
    
    prepopulated_days = []
    for day_item in days_list:
        wh_record = existing_wh.get(day_item["day"])
        prepopulated_days.append({
            "day": day_item["day"],
            "name": day_item["name"],
            "is_active": wh_record is not None,
            "start_time": wh_record.start_time.strftime("%H:%M") if wh_record else "09:00",
            "end_time": wh_record.end_time.strftime("%H:%M") if wh_record else "17:00",
            "slot_duration": wh_record.slot_duration_minutes if wh_record else 30,
            "buffer_time": wh_record.buffer_time_minutes if wh_record else 0
        })

    return render(request, 'doctors/configure_working_hours.html', {
        'days': prepopulated_days,
        'doctor_profile': doctor_profile
    })
