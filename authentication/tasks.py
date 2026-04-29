from celery import shared_task
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from datetime import datetime


# =========================
# Activation Email
# =========================
@shared_task
def send_activation_email_async(first_name, email, activation_link):
    try:
        title = "Activate Your Law Firm Account"
        html_content = render_to_string(
            "emails/account_activation.html",
            {
                "title": title,
                "username": first_name,
                "message": "Welcome! Click the button below to activate your account and get started.",
                "action": "Activate Account",
                "activation_link": activation_link,
                "now": datetime.utcnow(),
            },
        )

        msg = EmailMultiAlternatives(
            subject=title,
            body=f"Click the link to activate your account: {activation_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print("Gmail SMTP ERROR [activation]:", str(e))
        return False


# =========================
# OTP / MFA Email
# =========================
@shared_task
def send_otp_email_async(first_name, email, otp):
    try:
        title = "Your Login OTP Code"
        html_content = render_to_string(
            "emails/otp_email.html",
            {
                "title": title,
                "username": first_name,
                "otp": otp,
                "message": "Use the OTP below to complete your login. It expires in 15 minutes.",
                "now": datetime.utcnow(),
            },
        )

        msg = EmailMultiAlternatives(
            subject=title,
            body=f"Your OTP is: {otp}. It expires in 15 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print("Gmail SMTP ERROR [otp]:", str(e))
        return False


# =========================
# Password Reset Email
# =========================
@shared_task
def send_reset_password_email_async(first_name, email, reset_link):
    try:
        title = "Reset Your Password"
        html_content = render_to_string(
            "emails/password_reset.html",
            {
                "title": title,
                "username": first_name,
                "message": "Click the button below to reset your password. This link expires in 1 hour.",
                "action": "Reset Password",
                "reset_link": reset_link,
                "now": datetime.utcnow(),
            },
        )

        msg = EmailMultiAlternatives(
            subject=title,
            body=f"Click the link to reset your password: {reset_link}. Ignore if you did not request this.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print("Gmail SMTP ERROR [reset-password]:", str(e))
        return False
    

# =========================
# Firm Owner Invite Email
# =========================
@shared_task
def send_firm_owner_invite_async(first_name, email, firm_name, role_name, invite_link):
    try:
        title = "You've been onboarded to WakiliAI"
        html_content = render_to_string(
            "emails/firm_owner_invite.html",
            {
                "title": title,
                "username": first_name,
                "firm_name": firm_name,
                "role_name": role_name,
                "message": f"You have been onboarded as {role_name} at {firm_name}. Click the button below to activate your account.",
                "action": "Activate Account",
                "invite_link": invite_link,
                "now": datetime.utcnow(),
            },
        )

        msg = EmailMultiAlternatives(
            subject=title,
            body=f"You have been onboarded as {role_name} at {firm_name}. Click the link to activate your account: {invite_link}. This link expires in 48 hours.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print("Gmail SMTP ERROR [firm-owner-invite]:", str(e))
        return False


# =========================
# Team Invite Email
# =========================
@shared_task
def send_team_invite_async(email, firm_name, role_name, invite_link):
    try:
        title = f"You've been invited to join {firm_name} on WakiliAI"
        html_content = render_to_string(
            "emails/team_invite.html",
            {
                "title": title,
                "firm_name": firm_name,
                "role_name": role_name,
                "message": f"You have been invited as {role_name} at {firm_name}. Click the button below to activate your account.",
                "action": "Accept Invitation",
                "invite_link": invite_link,
                "now": datetime.utcnow(),
            },
        )

        msg = EmailMultiAlternatives(
            subject=title,
            body=f"You have been invited as {role_name} at {firm_name}. Click the link to activate your account: {invite_link}. This link expires in 48 hours.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print("Gmail SMTP ERROR [team-invite]:", str(e))
        return False