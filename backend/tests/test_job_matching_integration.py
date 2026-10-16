import pytest
from sqlalchemy import func, select

from backend.app.models import Candidate, Job, JobMatch
from backend.app.services.job_matching import match_jobs

@pytest.mark.asyncio
async def test_matching_updates_existing_match_in_postgres(test_db):
    # Arrange: create a candidate and a job in the test database.
    candidate = Candidate(
        full_name="Integration Test Candidate",
        email="integration-test@example.com",
        headline="Laravel PHP Developer",
        years_experience=8,
        salary_currency="INR",
    )
    job = Job(
        title="Senior Laravel Developer",
        description="Laravel, PHP, Docker",
        experience_level="Senior",
        job_url="https://example.com/jobs/integration-test",
        source="integration-test",
        source_job_id="job-001",
        is_active=True,
    )

    test_db.add_all([candidate, job])
    await test_db.commit()
    await test_db.refresh(candidate)
    await test_db.refresh(job)

    # Act: run matching for the first time.
    first_result = await match_jobs(test_db, candidate.id)

    assert first_result["jobs_processed"] == 1

    first_match = await test_db.scalar(
        select(JobMatch).where(
            JobMatch.candidate_id == candidate.id,
            JobMatch.job_id == job.id,
        )
    )

    assert first_match is not None
    original_match_id = first_match.id
    original_score = first_match.score

    # Change the job so the match should be recalculated.
    job.description = "Laravel, PHP, Docker, Kubernetes"
    await test_db.commit()

    # Act: run matching again for the same candidate and job.
    second_result = await match_jobs(test_db, candidate.id)

    assert second_result["jobs_processed"] == 1

    updated_match = await test_db.scalar(
        select(JobMatch)
        .where(
            JobMatch.candidate_id == candidate.id,
            JobMatch.job_id == job.id,
        )
        .execution_options(populate_existing=True)
    )

    match_count = await test_db.scalar(
        select(func.count())
        .select_from(JobMatch)
        .where(
            JobMatch.candidate_id == candidate.id,
            JobMatch.job_id == job.id,
        )
    )

    # Assert: PostgreSQL updated the existing record.
    assert updated_match is not None
    assert updated_match.id == original_match_id
    assert match_count == 1

    # Kubernetes is now an additional recognized skill gap.
    print("Updated gaps:", updated_match.gaps)
    print("Updated score:", updated_match.score)
    assert "Kubernetes" in updated_match.gaps
    assert updated_match.score < original_score

@pytest.mark.asyncio
async def test_matching_missing_candidate_in_postgres(test_db):
    from uuid import uuid4

    import pytest

    with pytest.raises(ValueError, match="Candidate not found"):
        await match_jobs(test_db, uuid4())
