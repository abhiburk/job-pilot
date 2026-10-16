from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.services import email_service, job_digest


def test_build_digest_email_includes_job_details():
    match = SimpleNamespace(score=88.5)
    job = SimpleNamespace(
        title="Senior Laravel Developer",
        location="Remote",
        job_url="https://example.com/jobs/123",
    )

    subject, text_body, html_body = job_digest.build_digest_email([
        (match, job, "Example Inc"),
    ])

    assert "1 new jobs" in subject
    assert "Senior Laravel Developer" in text_body
    assert "Example Inc" in text_body
    assert "88/100" in text_body
    assert "https://example.com/jobs/123" in text_body
    assert "Senior Laravel Developer" in html_body
    assert "https://example.com/jobs/123" in html_body


@pytest.mark.asyncio
async def test_send_email_uses_smtp(monkeypatch):
    smtp_send = AsyncMock()
    monkeypatch.setattr(email_service.aiosmtplib, "send", smtp_send)
    monkeypatch.setattr(
        email_service.settings, "smtp_from_email", "jobs@example.com"
    )
    monkeypatch.setattr(
        email_service.settings, "smtp_from_name", "JobPilot"
    )
    monkeypatch.setattr(
        email_service.settings, "smtp_host", "smtp.example.com"
    )
    monkeypatch.setattr(email_service.settings, "smtp_port", 587)
    monkeypatch.setattr(
        email_service.settings, "smtp_username", "jobs@example.com"
    )
    monkeypatch.setattr(
        email_service.settings, "smtp_password", "test-password"
    )
    monkeypatch.setattr(
        email_service.settings, "smtp_use_tls", False
    )
    monkeypatch.setattr(
        email_service.settings, "smtp_start_tls", True
    )

    await email_service.send_email(
        to_email="candidate@example.com",
        subject="JobPilot digest",
        text_body="Your new jobs are ready.",
        html_body="<p>Your new jobs are ready.</p>",
    )

    smtp_send.assert_awaited_once()
    args = smtp_send.await_args
    message = args.args[0]

    assert message["To"] == "candidate@example.com"
    assert message["Subject"] == "JobPilot digest"
    assert args.kwargs["hostname"] == "smtp.example.com"
    assert args.kwargs["start_tls"] is True


@pytest.mark.asyncio
async def test_send_email_propagates_smtp_failure(monkeypatch):
    async def fail_smtp(*args, **kwargs):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(
        email_service.aiosmtplib,
        "send",
        fail_smtp,
    )
    monkeypatch.setattr(
        email_service.settings,
        "smtp_from_email",
        "jobs@example.com",
    )
    monkeypatch.setattr(
        email_service.settings,
        "smtp_host",
        "smtp.example.com",
    )

    with pytest.raises(OSError, match="SMTP unavailable"):
        await email_service.send_email(
            to_email="candidate@example.com",
            subject="Test",
            text_body="Test message",
        )