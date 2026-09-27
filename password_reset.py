"""Password reset email delivery using standard SMTP settings."""

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def send_password_reset_email(recipient: str, code: str) -> bool:
    """Send a one-time reset code. Returns False if SMTP is not configured."""
    host = os.getenv("SMTP_HOST")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM_EMAIL")
    if not all((host, username, password, sender)):
        logger.error("Password reset email not sent: SMTP settings are incomplete.")
        return False

    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
        message = EmailMessage()
        message["Subject"] = "Your FitBuddy password reset code"
        message["From"] = sender
        message["To"] = recipient
        message.set_content(
            "We received a request to reset your FitBuddy password.\n\n"
            f"Your one-time verification code is: {code}\n\n"
            "Enter this code on the FitBuddy password recovery page within 30 minutes.\n\n"
            "If you did not request this, you can ignore this email."
        )

        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=timeout) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(username, password)
            server.send_message(message)
        return True
    except (OSError, ValueError, smtplib.SMTPException):
        logger.exception("Unable to send FitBuddy password reset email.")
        return False
