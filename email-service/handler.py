import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def get_html_template(trigger_type, context):
    """
    Returns a clean, Vercel/Linear style HTML template based on the trigger type.
    """
    primary_color = "#4f46e5"  # indigo-600
    bg_color = "#0f172a"       # slate-900
    card_bg = "#1e293b"        # slate-800
    text_color = "#f1f5f9"     # slate-100
    muted_color = "#94a3b8"    # slate-400

    base_style = f"""
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background-color: {bg_color};
        color: {text_color};
        text-align: center;
        padding: 40px 20px;
    """

    card_style = f"""
        max-width: 500px;
        margin: 0 auto;
        background-color: {card_bg};
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 32px;
        text-align: left;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    """

    button_style = f"""
        display: inline-block;
        background-color: {primary_color};
        color: #ffffff;
        text-decoration: none;
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 600;
        margin-top: 16px;
        text-align: center;
    """

    if trigger_type == "SIGNUP_WELCOME":
        title = "Welcome to AuraHealth"
        body = f"""
            <h2 style="font-size: 24px; font-weight: 700; margin-bottom: 16px; color: #ffffff;">Welcome to AuraHealth!</h2>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 20px;">Hi {context.get('name', 'User')},</p>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 20px;">Thank you for registering with AuraHealth. Your account has been successfully configured.</p>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 24px;">You can now log in to schedule and manage consultations, view clinical records, and track your health timeline.</p>
            <div style="text-align: center;">
                <a href="{context.get('login_url', 'http://localhost:8000/auth/login/')}" style="{button_style}">Access Your Dashboard</a>
            </div>
        """
    elif trigger_type == "BOOKING_CONFIRMATION":
        title = "Appointment Confirmed"
        body = f"""
            <h2 style="font-size: 24px; font-weight: 700; margin-bottom: 16px; color: #ffffff;">Appointment Confirmed</h2>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 20px;">Hi {context.get('patient_name', 'Patient')},</p>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 20px;">Your appointment request has been approved and confirmed. Here are your booking details:</p>
            <div style="background-color: rgba(255, 255, 255, 0.03); border-radius: 8px; padding: 16px; margin-bottom: 24px; border: 1px solid rgba(255, 255, 255, 0.05);">
                <div style="margin-bottom: 8px;"><strong style="color: #ffffff;">Reference ID:</strong> <span style="font-family: monospace; color: {muted_color};">{context.get('reference_id', 'N/A')}</span></div>
                <div style="margin-bottom: 8px;"><strong style="color: #ffffff;">Doctor:</strong> <span style="color: {muted_color};">Dr. {context.get('doctor_name', 'N/A')}</span></div>
                <div><strong style="color: #ffffff;">Date & Time:</strong> <span style="color: {muted_color};">{context.get('appointment_time', 'N/A')}</span></div>
            </div>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 24px;">A calendar event has been added to your synced Google Calendar account.</p>
            <div style="text-align: center;">
                <a href="{context.get('dashboard_url', 'http://localhost:8000/dashboard/')}" style="{button_style}">View Appointments</a>
            </div>
        """
    elif trigger_type == "DOCTOR_APPROVED":
        title = "Doctor Account Approved"
        body = f"""
            <h2 style="font-size: 24px; font-weight: 700; margin-bottom: 16px; color: #ffffff;">Registration Approved</h2>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 20px;">Hi Dr. {context.get('name', 'Doctor')},</p>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 20px;">We are pleased to inform you that your registration request as a Doctor on AuraHealth has been approved by the administrators.</p>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 24px;">You can now log in to configure your working hours, start generating slots, and consult patients.</p>
            <div style="text-align: center;">
                <a href="{context.get('login_url', 'http://localhost:8000/auth/login/')}" style="{button_style}">Go to Doctor Dashboard</a>
            </div>
        """
    elif trigger_type == "DOCTOR_REJECTED":
        title = "Registration Request Rejected"
        body = f"""
            <h2 style="font-size: 24px; font-weight: 700; margin-bottom: 16px; color: #f43f5e;">Registration Rejected</h2>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 20px;">Hi Dr. {context.get('name', 'Doctor')},</p>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 20px;">We regret to inform you that your registration request to join AuraHealth as a Doctor has been rejected by the administrator review panel.</p>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 24px;"><strong style="color: #ffffff;">Reason for rejection:</strong> {context.get('reason', 'Provided credentials or documentation did not pass our verification standards.')}</p>
        """
    else:
        # Fallback template
        title = "AuraHealth Notification"
        body = f"""
            <h2 style="font-size: 24px; font-weight: 700; margin-bottom: 16px; color: #ffffff;">System Update</h2>
            <p style="color: {muted_color}; line-height: 1.6; margin-bottom: 20px;">{context.get('message', 'You have a new message.')}</p>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
    </head>
    <body style="{base_style}">
        <div style="{card_style}">
            <div style="display: flex; align-items: center; margin-bottom: 24px;">
                <div style="width: 32px; height: 32px; border-radius: 8px; background-color: {primary_color}; color: #ffffff; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 18px; margin-right: 12px; font-family: sans-serif;">H</div>
                <span style="font-weight: 700; font-size: 18px; color: #ffffff;">AuraHealth</span>
            </div>
            {body}
            <div style="margin-top: 32px; border-t: 1px solid rgba(255,255,255,0.05); padding-top: 16px; font-size: 11px; color: {muted_color}; text-align: center;">
                AuraHealth Appointment Management System &bull; Local Lab Execution
            </div>
        </div>
    </body>
    </html>
    """
    return html

# Connect to SMTP server
def send_email(event, context):
    try:
        body_str = event.get('body', '{}')
        if isinstance(body_str, str):
            payload = json.loads(body_str)
        else:
            payload = body_str
    except Exception as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Invalid request payload: {str(e)}'})
        }

    recipient = payload.get('recipient_email')
    trigger_type = payload.get('trigger_type')
    email_context = payload.get('context', {})

    if not recipient or not trigger_type:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Fields recipient_email and trigger_type are required.'})
        }

    smtp_host = os.environ.get('SMTP_HOST', 'mailpit')
    smtp_port = int(os.environ.get('SMTP_PORT', '1025'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASSWORD', '')
    sender = os.environ.get('EMAIL_FROM', 'noreply@hospital.local')

    # Subject line map
    subject_map = {
        'SIGNUP_WELCOME': 'Welcome to AuraHealth!',
        'BOOKING_CONFIRMATION': 'Appointment Booking Confirmed',
        'DOCTOR_APPROVED': 'AuraHealth Doctor Account Approved',
        'DOCTOR_REJECTED': 'AuraHealth Doctor Account Rejected',
    }
    subject = subject_map.get(trigger_type, 'AuraHealth Notification')

    # Build MIME message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    # Set HTML body
    html_content = get_html_template(trigger_type, email_context)
    msg.attach(MIMEText(html_content, 'html'))

    try:
        # Connect to SMTP server
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        
        server.sendmail(sender, [recipient], msg.as_string())
        server.quit()
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'Email successfully dispatched to {recipient}'})
        }
    except Exception as e:
        return {
            'statusCode': 502,
            'body': json.dumps({'error': f'Failed to dispatch email over SMTP: {str(e)}'})
        }

def health_check(event, context):
    """
    AWS Lambda Handler for health checks.
    """
    return {
        'statusCode': 200,
        'body': json.dumps({'status': 'healthy'})
    }

