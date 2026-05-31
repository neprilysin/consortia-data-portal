import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
DEFAULT_FROM = SMTP_USER or "noreply@localhost"


def send_admin_notification(user, admin_email: str):
    message = EmailMessage()
    message["Subject"] = f"New portal registration: {user.first_name} {user.last_name}"
    message["From"] = DEFAULT_FROM
    message["To"] = admin_email
    message.set_content(
        f"A new user has registered for the Consortia Data Portal:\n\n"
        f"Name: {user.first_name} {user.last_name}\n"
        f"Title: {user.title or '-'}\n"
        f"Department: {user.department or '-'}\n"
        f"Organization: {user.organization or '-'}\n"
        f"Email: {user.email}\n"
        f"Policy accepted: {user.policy_accepted}\n\n"
        "Please review and approve or reject the registration in the dashboard."
    )

    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        print("[email_utils] SMTP is not configured. Registration notification not sent.")
        print(message)
        return

    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
                smtp.starttls()
                smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(message)
    except Exception as exc:
        print(f"[email_utils] Failed to send registration email: {exc}")
