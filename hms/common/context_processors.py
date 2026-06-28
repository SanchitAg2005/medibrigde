from .models import HospitalConfig

def hospital_settings(request):
    """
    Exposes the global HospitalConfig singleton to all template contexts.
    """
    return {
        'hospital_config': HospitalConfig.get_solo()
    }
