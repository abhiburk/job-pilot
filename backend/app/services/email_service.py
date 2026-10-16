from email.message import EmailMessage
from html import escape

import aiosmtplib

from backend.app.core.config import settings
from aiosmtplib.errors import (
    SMTPAuthenticationError,
    SMTPConnectError,
    SMTPRecipientRefused,
    SMTPRecipientsRefused,
    SMTPSenderRefused,
    SMTPTimeoutError,
    SMTPException,
)

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

    except SMTPConnectError as e:
        # Triggered if connection fails, e.g., bad host, wrong port, or SSL verification issues
        print(f"Connection Failed: Cannot reach {settings.smtp_host}:{settings.smtp_port}. Details: {e}")

    except SMTPAuthenticationError as e:
        # Triggered if credentials (username/password) are incorrect or rejected
        print(f"Authentication Failed (Code {e.code}): {e.message}")

    except SMTPSenderRefused as e:
        # Triggered if the server rejects the 'From' address
        print(f"Sender Refused (Code {e.code}): {e.message}. Rejected Sender: {e.sender}")

    except SMTPRecipientRefused as e:
        # Triggered if a specific recipient is rejected by the server
        print(f"Recipient Refused (Code {e.code}): {e.message}. Rejected Recipient: {e.recipient}")

    except SMTPRecipientsRefused as e:
        # Triggered if multiple recipients are blocked
        print(f"Multiple Recipients Refused: {e.recipients}")

    except SMTPTimeoutError as e:
        # Triggered if the server does not respond within the 30-second timeout window
        print(f"Network Timeout: The operation took too long. {e}")

    except SMTPException as e:
        # Catch-all for any other library-specific SMTP errors
        print(f"General SMTP Error occurred: {e}")

    except Exception as e:
        # Catch-all for non-SMTP related issues (e.g., local configuration errors, missing message data)
        print(f"Unexpected system error: {e}")


def escape_html(value: object | None) -> str:
    return escape(str(value or ""))