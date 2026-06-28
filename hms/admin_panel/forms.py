from django import forms
from doctors.models import DoctorProfile, WorkingHours, DoctorLeave
from common.models import HospitalConfig
from django.contrib.auth import get_user_model

User = get_user_model()

class AdminDoctorEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
    }))
    last_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
    }))
    
    class Meta:
        model = DoctorProfile
        fields = ['specialization', 'experience_years', 'bio', 'languages', 'qualification']
        widgets = {
            'specialization': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
            'experience_years': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400',
                'rows': 3
            }),
            'languages': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
            'qualification': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()
        if commit:
            profile.save()
        return profile


class HospitalConfigForm(forms.ModelForm):
    class Meta:
        model = HospitalConfig
        fields = ['name', 'logo', 'address', 'phone', 'email', 'website', 'working_hours', 'emergency_contact']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
            'logo': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
            'address': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
            'website': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
            'working_hours': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
            'emergency_contact': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white border-zinc-200 text-slate-800 placeholder-zinc-400'
            }),
        }
