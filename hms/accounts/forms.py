from django import forms
from django.db import transaction
from django.contrib.auth import get_user_model
from doctors.models import DoctorProfile

User = get_user_model()

class UserSignupForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-300 text-slate-900 placeholder:text-slate-400',
        'placeholder': '••••••••'
    }))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-300 text-slate-900 placeholder:text-slate-400',
        'placeholder': '••••••••'
    }))
    
    full_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-300 text-slate-900 placeholder:text-slate-400',
        'placeholder': 'John Doe'
    }))

    # Doctor specific fields
    specialization = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-300 text-slate-900 placeholder:text-slate-400',
        'placeholder': 'Cardiology'
    }))
    experience_years = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-300 text-slate-900 placeholder:text-slate-400',
        'placeholder': '5'
    }))
    bio = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-300 text-slate-900 placeholder:text-slate-400 rows-3',
        'placeholder': 'Short bio about yourself...',
        'rows': 3
    }))
    languages = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-300 text-slate-900 placeholder:text-slate-400',
        'placeholder': 'English, Spanish'
    }))
    
    gov_id_file = forms.FileField(required=False, widget=forms.FileInput(attrs={
        'class': 'w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-emerald-600 file:text-white hover:file:bg-emerald-700 cursor-pointer'
    }))
    medical_license_file = forms.FileField(required=False, widget=forms.FileInput(attrs={
        'class': 'w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-emerald-600 file:text-white hover:file:bg-emerald-700 cursor-pointer'
    }))
    degree_certificate_file = forms.FileField(required=False, widget=forms.FileInput(attrs={
        'class': 'w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-emerald-600 file:text-white hover:file:bg-emerald-700 cursor-pointer'
    }))

    class Meta:
        model = User
        fields = ['email', 'role']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-300 text-slate-900 placeholder:text-slate-400',
                'placeholder': 'john@example.com'
            }),
            'role': forms.Select(attrs={
                # bg-slate-900 border-white/20 is used for high-contrast accessibility of the select options
                'class': 'w-full px-4 py-2 bg-white border border-zinc-300 text-slate-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition cursor-pointer',
                'id': 'role-select'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict the role field to PATIENT and DOCTOR only (never expose ADMIN)
        self.fields['role'].choices = [
            (User.Roles.PATIENT, 'Patient'),
            (User.Roles.DOCTOR, 'Doctor')
        ]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        role = cleaned_data.get('role')

        if password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")

        # Require doctor specific fields if role is DOCTOR
        if role == User.Roles.DOCTOR:
            required_doctor_fields = ['specialization', 'experience_years', 'gov_id_file', 'medical_license_file', 'degree_certificate_file']
            for field in required_doctor_fields:
                if not cleaned_data.get(field):
                    self.add_error(field, f"This field is required for Doctor registration.")

        return cleaned_data

    def save(self, commit=True):
        from common.models import HospitalConfig
        with transaction.atomic():
            user = super().save(commit=False)
            user.username = self.cleaned_data['email']
            user.set_password(self.cleaned_data['password'])
            
            # Split full_name
            full_name = self.cleaned_data.get('full_name', '')
            parts = full_name.split(maxsplit=1)
            if len(parts) == 2:
                user.first_name, user.last_name = parts
            elif len(parts) == 1:
                user.first_name = parts[0]
                user.last_name = ''
            
            if commit:
                user.save()
                
                # If doctor, build profile
                if user.role == User.Roles.DOCTOR:
                    hospital_config = HospitalConfig.get_solo()
                    DoctorProfile.objects.create(
                        user=user,
                        specialization=self.cleaned_data['specialization'],
                        experience_years=self.cleaned_data['experience_years'],
                        hospital_name=hospital_config.name,
                        bio=self.cleaned_data.get('bio', ''),
                        languages=self.cleaned_data.get('languages', ''),
                        gov_id_file=self.cleaned_data.get('gov_id_file'),
                        medical_license_file=self.cleaned_data.get('medical_license_file'),
                        degree_certificate_file=self.cleaned_data.get('degree_certificate_file')
                    )
            return user

from django.contrib.auth.forms import AuthenticationForm

class UserLoginForm(AuthenticationForm):
    username = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'w-full px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-300 text-slate-900 placeholder:text-slate-400',
        'placeholder': 'name@example.com'
    }), label="Email Address")
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-300 text-slate-900 placeholder:text-slate-400',
        'placeholder': '••••••••'
    }), label="Password")
