from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.models import (
    Application,
    ApplicationDocument,
    Candidate,
    Job,
)
from backend.app.services import resume_tailoring as service


async def create_resume_test_data(db):
    candidate = Candidate(
        full_name="Test Candidate",
        email=f"{uuid4()}@example.com",
        headline="Backend Developer",
        summary="Experienced backend developer.",
        resume_text=(
            "PHP, Laravel, PostgreSQL, REST APIs. "
            "Built billing systems and asynchronous background jobs."
        ),
        years_experience=8,
    )

    job = Job(
        title="Senior Backend Developer",
        description=(
            "Requires PHP, Laravel, PostgreSQL, REST APIs, "
            "and experience with background processing."
        ),
        job_url="https://example.com/jobs/resume-test",
        source="resume-test",
        source_job_id=str(uuid4()),
        is_active=True,
    )

    db.add_all([candidate, job])
    await db.commit()
    await db.refresh(candidate)
    await db.refresh(job)

    return candidate, job


@pytest.mark.asyncio
async def test_tailor_resume_creates_unapproved_document(
    test_db, monkeypatch
):
    candidate, job = await create_resume_test_data(test_db)

    monkeypatch.setattr(
        service,
        "generate_text",
        AsyncMock(
            return_value=(
                "Test Candidate\n"
                "PROFESSIONAL SUMMARY\n"
                "Backend developer experienced with Laravel and PostgreSQL."
            )
        ),
    )

    result = await service.tailor_resume_for_job(
        test_db, candidate.id, job.id
    )

    document = result["document"]

    assert document["document_type"] == "tailored_resume"
    assert document["version"] == 1
    assert document["is_approved"] is False
    assert document["content_text"]
    assert result["application_id"] is not None

    # The candidate's original resume must remain unchanged.
    await test_db.refresh(candidate)
    assert "billing systems" in candidate.resume_text


@pytest.mark.asyncio
async def test_tailor_resume_increments_version(test_db, monkeypatch):
    candidate, job = await create_resume_test_data(test_db)

    monkeypatch.setattr(
        service,
        "generate_text",
        AsyncMock(return_value="Tailored resume draft."),
    )

    first = await service.tailor_resume_for_job(
        test_db, candidate.id, job.id
    )
    second = await service.tailor_resume_for_job(
        test_db, candidate.id, job.id
    )

    assert first["application_id"] == second["application_id"]
    assert first["document"]["version"] == 1
    assert second["document"]["version"] == 2

    result = await test_db.execute(
        select(ApplicationDocument).where(
            ApplicationDocument.application_id
            == first["application_id"],
            ApplicationDocument.document_type == "tailored_resume",
        )
    )
    documents = result.scalars().all()

    assert len(documents) == 2
    assert all(not doc.is_approved for doc in documents)


@pytest.mark.asyncio
async def test_tailor_resume_requires_original_resume(
    test_db, monkeypatch
):
    candidate, job = await create_resume_test_data(test_db)
    candidate.resume_text = None
    await test_db.commit()

    generate_mock = AsyncMock(return_value="Should not be called.")
    monkeypatch.setattr(service, "generate_text", generate_mock)

    with pytest.raises(ValueError, match="Candidate resume is required"):
        await service.tailor_resume_for_job(
            test_db, candidate.id, job.id
        )

    generate_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_tailor_resume_requires_job_description(
    test_db, monkeypatch
):
    candidate, job = await create_resume_test_data(test_db)
    job.description = None
    await test_db.commit()

    generate_mock = AsyncMock(return_value="Should not be called.")
    monkeypatch.setattr(service, "generate_text", generate_mock)

    with pytest.raises(ValueError, match="job description is missing"):
        await service.tailor_resume_for_job(
            test_db, candidate.id, job.id
        )

    generate_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_tailor_resume_handles_ai_provider_failure(
    test_db, monkeypatch
):
    candidate, job = await create_resume_test_data(test_db)

    monkeypatch.setattr(
        service,
        "generate_text",
        AsyncMock(side_effect=service.AIProviderError("Provider error")),
    )

    with pytest.raises(service.ResumeTailoringError):
        await service.tailor_resume_for_job(
            test_db, candidate.id, job.id
        )

    result = await test_db.execute(select(ApplicationDocument))
    assert result.scalars().all() == []