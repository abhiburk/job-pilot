
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from backend.app.models import JobMatch
from backend.app.services.job_matching import match_jobs


def mock_result(items):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def make_candidate():
    return SimpleNamespace(
        id=uuid4(),
        headline="Laravel PHP Developer",
        summary="Backend developer",
        resume_text="",
        years_experience=Decimal("8"),
        minimum_salary=None,
        salary_currency="INR",
        preferred_job_titles=[],
        preferred_work_modes=[],
        preferred_locations=[],
    )


def make_job():
    return SimpleNamespace(
        id=uuid4(),
        title="Senior Laravel Developer",
        description="PHP, Laravel and Docker",
        experience_level="Senior",
        remote_type="Remote",
        location="India",
        salary_min=None,
        salary_max=None,
        salary_currency="INR",
    )


@pytest.mark.asyncio
async def test_match_jobs_raises_when_candidate_does_not_exist():
    db = SimpleNamespace(
        get=AsyncMock(return_value=None),
        execute=AsyncMock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    with pytest.raises(ValueError, match="Candidate not found"):
        await match_jobs(db, uuid4())

    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_match_jobs_handles_no_active_jobs():
    candidate = make_candidate()

    db = SimpleNamespace(
        get=AsyncMock(return_value=candidate),
        execute=AsyncMock(
            side_effect=[
                mock_result([]),  # Candidate skills
                mock_result([]),  # Active jobs
            ]
        ),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    result = await match_jobs(db, candidate.id)

    assert result["candidate_id"] == str(candidate.id)
    assert result["jobs_processed"] == 0
    assert result["model_version"] == "rules-v2"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_match_jobs_processes_and_upserts_a_job():
    candidate = make_candidate()
    job = make_job()

    db = SimpleNamespace(
        get=AsyncMock(return_value=candidate),
        execute=AsyncMock(
            side_effect=[
                mock_result([]),  # Candidate skills from database
                mock_result([job]),  # Active jobs
                MagicMock(),  # JobMatch upsert
            ]
        ),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    result = await match_jobs(db, candidate.id)

    assert result["jobs_processed"] == 1
    assert result["candidate_id"] == str(candidate.id)

    # First query loads skills, second loads jobs, third writes the match.
    assert db.execute.await_count == 3
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()

    upsert_statement = db.execute.await_args_list[2].args[0]
    compiled = str(
        upsert_statement.compile(dialect=postgresql.dialect())
    )

    assert "ON CONFLICT ON CONSTRAINT uq_candidate_job_match" in compiled
    assert "DO UPDATE SET" in compiled


@pytest.mark.asyncio
async def test_match_jobs_rolls_back_when_upsert_fails():
    candidate = make_candidate()
    job = make_job()

    db = SimpleNamespace(
        get=AsyncMock(return_value=candidate),
        execute=AsyncMock(
            side_effect=[
                mock_result([]),
                mock_result([job]),
                RuntimeError("Database write failed"),
            ]
        ),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="Database write failed"):
        await match_jobs(db, candidate.id)

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
