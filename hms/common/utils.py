from common.models import AuditLog

def get_client_ip(request):
    """
    Parses request metadata to extract the user's IP address.
    """
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_event(action, actor=None, ip_address=None, details=None):
    """
    Creates an AuditLog record in the database.
    """
    if details is None:
        details = {}
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        ip_address=ip_address,
        details=details
    )

def log_request_event(request, action, details=None):
    """
    Convenience wrapper to log an event from an HTTP request context.
    """
    actor = request.user if request and request.user and request.user.is_authenticated else None
    ip = get_client_ip(request) if request else None
    return log_event(action, actor=actor, ip_address=ip, details=details)
