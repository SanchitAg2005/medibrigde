from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserSignupForm, UserLoginForm
from .models import CustomUser
from common.models import AsyncTask

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserSignupForm(request.POST, request.FILES)
        if form.is_valid():
            # Security check: verify that roles are not hijacked
            role = form.cleaned_data.get('role')
            if role == CustomUser.Roles.ADMIN:
                messages.error(request, "Administrator registration is disabled.")
                return render(request, 'accounts/signup.html', {'form': form})
                
            user = form.save()
            
            # Enqueue SIGNUP_WELCOME email task
            AsyncTask.objects.create(
                task_type=AsyncTask.TaskTypes.SEND_EMAIL,
                payload={
                    "type": "SIGNUP_WELCOME",
                    "user_id": str(user.id),
                    "recipient_email": user.email
                }
            )

            if user.role == CustomUser.Roles.DOCTOR:
                messages.info(request, "Registration successful! Admin verification is required before you can log in.")
                return redirect('verification_pending')
            else:
                login(request, user)
                messages.success(request, "Welcome! Registration successful.")
                return redirect('dashboard')
    else:
        form = UserSignupForm()
    return render(request, 'accounts/signup.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                # Check Doctor Approval status
                if user.role == CustomUser.Roles.DOCTOR:
                    if user.approval_status == CustomUser.ApprovalStatus.PENDING:
                        messages.error(request, "Your account is pending admin verification. Please wait for approval.")
                        return redirect('verification_pending')
                    elif user.approval_status == CustomUser.ApprovalStatus.REJECTED:
                        messages.error(request, "Your registration request has been rejected by the administrator.")
                        return render(request, 'accounts/login.html', {'form': form})
                    elif user.approval_status == CustomUser.ApprovalStatus.REMOVED:
                        messages.error(request, "This doctor account has been deactivated/removed from the medical center.")
                        return render(request, 'accounts/login.html', {'form': form})
                
                login(request, user)
                messages.success(request, f"Welcome back, {user.first_name or user.email}!")
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid email or password.")
    else:
        form = UserLoginForm()
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('landing')

def verification_pending_view(request):
    return render(request, 'accounts/verification_pending.html')

@login_required
def dashboard_redirect_view(request):
    user = request.user
    if user.role == CustomUser.Roles.ADMIN or user.is_superuser:
        return redirect('admin_panel:dashboard')
    elif user.role == CustomUser.Roles.DOCTOR:
        return redirect('doctors:dashboard')
    else:
        return redirect('patients:dashboard')

