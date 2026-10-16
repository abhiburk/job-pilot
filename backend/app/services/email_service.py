from email.message import EmailMessage
from html import escape
import aiosmtplib
from backend.app.core.config import settings

async def send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    if not settings.smtp_from_email:
        raise RuntimeError("SMTP_FROM_EMAIL is not configured")

    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")

    message = EmailMessage()
    message["From"] = (
        f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    )
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)

    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
            start_tls=settings.smtp_start_tls,
            validate_certs=False,
            timeout=30,
        )
        print("Email sent successfully!")
    except Exception:
        print("Failed to send email to %s", to_email)
        raise


def escape_html(value: object | None) -> str:
    return escape(str(value or ""))