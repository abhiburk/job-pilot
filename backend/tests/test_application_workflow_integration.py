
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from backend.app.api.routes.applications import (
    generate_cover_letter,
    update_application,
)
from backend.app.models import (
    Application,
    ApplicationDocument,
    Candidate,
    Job,
    JobMatch,
)
from backend.app.schemas.ai import CoverLetterRequest
from backend.app.schemas.application import ApplicationUpdate
from backend.app.services.job_matching import match_jobs
from backend.app.services.resume_tailoring import tailor_resume_for_job


@pytest.mark.asyncio
async def test_complete_application_preparation_workflow(test_db, test_user):
    # Arrange: create a candidate and an eligible job in PostgreSQL.
    candidate = Candidate(
        full_name="Integration Test Candidate",
        email=f"{uuid4()}@example.com",
        headline="Senior Backend Developer",
        summary="Backend engineer experienced in Laravel and PostgreSQL.",
        resume_text=(
            "PHP, Laravel, PostgreSQL, REST APIs. "
            "Built billing systems and asynchronous background jobs."
        ),
        years_experience=8,
        salary_currency="INR",
        user_id=test_user.id,
    )

    job = Job(
        title="Senior Laravel Developer",
        description=(
            "Requires PHP, Laravel, PostgreSQL, REST APIs, "
            "and experience with background processing."
        ),
        experience_level="Senior",
        job_url=f"https://example.com/jobs/{uuid4()}",
        source="integration-test",
        source_job_id=str(uuid4()),
        is_active=True,
    )

    test_db.add_all([candidate, job])
    await test_db.commit()
    await test_db.refresh(candidate)
    await test_db.refresh(job)

    # 1. Match the candidate to the job using the real matching service.
    matching_result = await match_jobs(test_db, candidate.id)

    assert matching_result["jobs_processed"] >= 1

    match = await test_db.scalar(
        select(JobMatch).where(
            JobMatch.candidate_id == candidate.id,
            JobMatch.job_id == job.id,
        )
    )
    assert match is not None

    # 2. Mock only the external AI generation calls.
    cover_letter_text = (
        "Dear Hiring Team,\n\n"
        "My experience building billing systems and background jobs "
        "with PHP and Laravel aligns with this backend role.\n\n"
        "Regards,\nIntegration Test Candidate"
    )

    tailored_resume_text = (
        "Senior Backend Developer\n\n"
        "Skills\n"
        "PHP, Laravel, PostgreSQL, REST APIs\n\n"
        "Experience Highlights\n"
        "- Built billing systems and asynchronous background jobs."
    )

    tailoring_response = json.dumps(
        {
            "tailored_resume": tailored_resume_text,
            "changes_summary": [
                "Highlighted relevant backend experience."
            ],
            "warnings": [],
        }
    )

    with (
        patch(
            "backend.app.api.routes.applications.generate_text",
            new=AsyncMock(return_value=cover_letter_text),
        ) as mock_cover_letter,
        patch(
            "backend.app.services.resume_tailoring.generate_text",
            new=AsyncMock(return_value=tailoring_response),
        ) as mock_resume,
    ):
        # 3. Generate and persist the cover letter.
        cover_letter_result = await generate_cover_letter(
            payload=CoverLetterRequest(
                candidate_id=candidate.id,
                job_id=job.id,
            ),
            current_user=test_user,
            db=test_db,
        )

        assert cover_letter_result.cover_letter == cover_letter_text
        mock_cover_letter.assert_awaited_once()

        # 4. Generate and persist the tailored resume.
        resume_result = await tailor_resume_for_job(
            db=test_db,
            candidate_id=candidate.id,
            job_id=job.id,
        )

        assert resume_result is not None
        mock_resume.assert_awaited_once()

    # 5. Verify both documents are stored and require approval.
    application = await test_db.scalar(
        select(Application).where(
            Application.candidate_id == candidate.id,
            Application.job_id == job.id,
        )
    )
    assert application is not None
    assert application.status == "saved"

    documents = (
        await test_db.scalars(
            select(ApplicationDocument).where(
                ApplicationDocument.application_id == application.id
            )
        )
    ).all()

    documents_by_type = {doc.document_type: doc for doc in documents}

    assert "cover_letter" in documents_by_type
    assert "tailored_resume" in documents_by_type

    cover_letter_doc = documents_by_type["cover_letter"]
    resume_doc = documents_by_type["tailored_resume"]

    assert cover_letter_doc.content_text == cover_letter_text
    assert resume_doc.content_text == tailored_resume_text
    assert cover_letter_doc.is_approved is False
    assert resume_doc.is_approved is False

    # 6. Update the application status and schedule a follow-up.
    follow_up_at = datetime.now(timezone.utc) + timedelta(days=3)

    updated_application = await update_application(
        application_id=application.id,
        payload=ApplicationUpdate(
            status="applied",
            follow_up_at=follow_up_at,
        ),
        candidate_id=candidate.id,
        current_user=test_user,
        db=test_db,
    )

    assert updated_application.status == "applied"
    assert updated_application.applied_at is not None
    assert updated_application.follow_up_at is not None

    # 7. Reload persisted records and verify the final state.
    await test_db.refresh(application)
    await test_db.refresh(cover_letter_doc)
    await test_db.refresh(resume_doc)

    assert application.status == "applied"
    assert application.applied_at is not None
    assert application.follow_up_at == follow_up_at

    assert cover_letter_doc.is_approved is False
    assert resume_doc.is_approved is False
