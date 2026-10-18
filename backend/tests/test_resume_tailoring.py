
import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.models import (
    ApplicationDocument,
    Candidate,
    Job,
)
from backend.app.services import resume_tailoring as service


def make_tailoring_response(
    tailored_resume="Test Candidate\nPROFESSIONAL SUMMARY\nBackend developer experienced with Laravel and PostgreSQL.",
):
    return json.dumps(
        {
            "tailored_resume": tailored_resume,
            "changes_summary": [
                "Emphasized existing Laravel backend experience."
            ],
            "warnings": [
                "The supplied resume does not establish Kubernetes experience."
            ],
        }
    )


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
        AsyncMock(return_value=make_tailoring_response()),
    )

    result = await service.tailor_resume_for_job(
        test_db, candidate.id, job.id
    )

    document = result["document"]
    metadata = document["generation_metadata"]

    assert document["document_type"] == "tailored_resume"
    assert document["version"] == 1
    assert document["is_approved"] is False
    assert document["content_text"]
    assert result["application_id"] is not None

    assert metadata["changes_summary"] == [
        "Emphasized existing Laravel backend experience."
    ]
    assert metadata["warnings"] == [
        "The supplied resume does not establish Kubernetes experience."
    ]

    # The candidate's original resume must remain unchanged.
    await test_db.refresh(candidate)
    assert "billing systems" in candidate.resume_text


@pytest.mark.asyncio
async def test_tailor_resume_increments_version(
    test_db, monkeypatch
):
    candidate, job = await create_resume_test_data(test_db)

    monkeypatch.setattr(
        service,
        "generate_text",
        AsyncMock(return_value=make_tailoring_response()),
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

    generate_mock = AsyncMock(
        return_value=make_tailoring_response()
    )
    monkeypatch.setattr(service, "generate_text", generate_mock)

    with pytest.raises(
        ValueError, match="Candidate resume is required"
    ):
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

    generate_mock = AsyncMock(
        return_value=make_tailoring_response()
    )
    monkeypatch.setattr(service, "generate_text", generate_mock)

    with pytest.raises(
        ValueError, match="job description is missing"
    ):
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
        AsyncMock(
            side_effect=service.AIProviderError("Provider error")
        ),
    )

    with pytest.raises(service.ResumeTailoringError):
        await service.tailor_resume_for_job(
            test_db, candidate.id, job.id
        )

    result = await test_db.execute(select(ApplicationDocument))
    assert result.scalars().all() == []


def test_parse_tailoring_response_rejects_invalid_json():
    with pytest.raises(
        service.ResumeTailoringError,
        match="invalid preview response",
    ):
        service._parse_tailoring_response("not valid JSON")


def test_parse_tailoring_response_rejects_missing_fields():
    with pytest.raises(
        service.ResumeTailoringError,
        match="incomplete preview response",
    ):
        service._parse_tailoring_response(
            json.dumps({"tailored_resume": "Resume content"})
        )


def test_parse_tailoring_response_rejects_invalid_field_types():
    with pytest.raises(
        service.ResumeTailoringError,
        match="incomplete preview response",
    ):
        service._parse_tailoring_response(
            json.dumps(
                {
                    "tailored_resume": "Resume content",
                    "changes_summary": "This should be a list",
                    "warnings": [],
                }
            )
        )


def test_parse_tailoring_response_accepts_empty_summary_and_warnings():
    parsed = service._parse_tailoring_response(
        json.dumps(
            {
                "tailored_resume": "Resume content",
                "changes_summary": [],
                "warnings": [],
            }
        )
    )

    assert parsed["tailored_resume"] == "Resume content"
    assert parsed["changes_summary"] == []
    assert parsed["warnings"] == []

@pytest.mark.parametrize(
    "resume, expected_warning",
    [
        (
            "Backend engineer andcloud developer",
            "Possible missing space: 'andcloud'.",
        ),
        (
            "CRMplatform developer",
            "Possible missing space: 'CRMplatform'.",
        ),
        (
            "Other:REST APIs",
            "Possible missing space: 'Other:REST'.",
        ),
    ],
)
def test_parse_tailoring_response_warns_about_formatting(
    resume, expected_warning
):
    parsed = service._parse_tailoring_response(
        make_tailoring_response(tailored_resume=resume)
    )

    assert expected_warning in parsed["warnings"]


def test_parse_tailoring_response_preserves_original_content():
    resume = "Backend engineer andcloud developer"

    parsed = service._parse_tailoring_response(
        make_tailoring_response(tailored_resume=resume)
    )

    # Flag the issue without silently rewriting the model output.
    assert parsed["tailored_resume"] == resume
    assert any("missing space" in warning for warning in parsed["warnings"])


@pytest.mark.parametrize(
    "resume",
    [
        "LinkedIn: string",
        "GitHub: undefined",
        "Email: null",
        "-Developed a billing system",
        "DevelopedeCommerce website",
    ],
)
def test_parse_tailoring_response_flags_formatting_issues(resume):
    parsed = service._parse_tailoring_response(
        make_tailoring_response(tailored_resume=resume)
    )

    assert parsed["warnings"]


@pytest.mark.parametrize(
    "value",
    [None, "", "  ", "string", "undefined", "null", "N/A"],
)
def test_clean_profile_value_returns_none_for_placeholders(value):
    assert service._clean_profile_value(value) is None


def test_clean_profile_value_preserves_real_values():
    assert (
        service._clean_profile_value(" https://github.com/example ")
        == "https://github.com/example"
    )
