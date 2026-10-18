from types import SimpleNamespace

import pytest

from backend.app.services import email_service, job_digest
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.services import job_digest

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


@pytest.mark.asyncio
async def test_send_candidate_digest_no_jobs_sends_nothing(monkeypatch):
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=SimpleNamespace(all=lambda: [])
    )
    db.commit = AsyncMock()
    db.add_all = MagicMock()

    send_email = AsyncMock()
    monkeypatch.setattr(job_digest, "send_email", send_email)

    candidate = SimpleNamespace(
        id="candidate-1",
        email="candidate@example.com",
    )

    result = await job_digest.send_candidate_digest(db, candidate)

    assert result == 0
    send_email.assert_not_awaited()
    db.add_all.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_candidate_digest_records_delivery_after_success(
    monkeypatch,
):
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add_all = MagicMock()

    match = SimpleNamespace(
        score=90,
        score_coverage=95,
        strengths=["Matching skill: Laravel"],
        gaps=[],
        explanation="Strong skills match",
    )
    job = SimpleNamespace(
        id="job-1",
        title="Senior Laravel Developer",
        location="Remote",
        job_url="https://example.com/jobs/1",
        is_active=True,
        posted_at=None,
    )
    db.execute.return_value = SimpleNamespace(
        all=lambda: [(match, job, "Example Inc")]
    )

    send_email = AsyncMock()
    monkeypatch.setattr(job_digest, "send_email", send_email)

    candidate = SimpleNamespace(
        id="candidate-1",
        email="candidate@example.com",
    )

    result = await job_digest.send_candidate_digest(db, candidate)

    assert result == 1
    send_email.assert_awaited_once()
    db.add_all.assert_called_once()
    db.commit.assert_awaited_once()

    deliveries = db.add_all.call_args.args[0]
    assert len(deliveries) == 1
    assert deliveries[0].candidate_id == candidate.id
    assert deliveries[0].job_id == job.id


@pytest.mark.asyncio
async def test_send_candidate_digest_smtp_failure_records_nothing(
    monkeypatch,
):
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add_all = MagicMock()

    match = SimpleNamespace(
        score=90,
        score_coverage=95,
        strengths=[],
        gaps=[],
        explanation="",
    )
    job = SimpleNamespace(
        id="job-1",
        title="Laravel Developer",
        location="Remote",
        job_url="https://example.com/jobs/1",
        posted_at=None,
    )
    db.execute.return_value = SimpleNamespace(
        all=lambda: [(match, job, "Example Inc")]
    )

    async def fail_email(**kwargs):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(job_digest, "send_email", fail_email)

    candidate = SimpleNamespace(
        id="candidate-1",
        email="candidate@example.com",
    )

    with pytest.raises(OSError, match="SMTP unavailable"):
        await job_digest.send_candidate_digest(db, candidate)

    db.add_all.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_daily_digest_continues_after_candidate_failure(monkeypatch):
    first = SimpleNamespace(id="candidate-1")
    second = SimpleNamespace(id="candidate-2")

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [first, second])
        )
    )
    db.rollback = AsyncMock()

    processed = []

    async def fake_send_candidate_digest(db, candidate):
        processed.append(candidate.id)

        if candidate.id == first.id:
            raise OSError("SMTP unavailable")

        return 2

    monkeypatch.setattr(
        job_digest,
        "send_candidate_digest",
        fake_send_candidate_digest,
    )

    result = await job_digest.send_daily_job_digests(db)

    assert processed == ["candidate-1", "candidate-2"]
    assert result == {
        "candidates_checked": 2,
        "candidates_emailed": 1,
        "jobs_emailed": 2,
        "failed_candidates": 1,
    }
    db.rollback.assert_awaited_once()
