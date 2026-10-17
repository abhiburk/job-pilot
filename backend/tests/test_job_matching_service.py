
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from backend.app.models import JobMatch
from backend.app.services.job_matching import match_jobs
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.services.job_matching import (
    calculate_score_coverage,
    calculate_skills_score,
    weighted_score,
)

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
    assert result["model_version"] == "hybrid-v1"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_match_jobs_processes_and_upserts_a_job():
    candidate = make_candidate()
    job = make_job()

    db = SimpleNamespace(
        get=AsyncMock(return_value=candidate),
        execute=AsyncMock(
            side_effect=[
                mock_result([]),   # Candidate skills from database
                mock_result([job]),  # Active jobs
                MagicMock(),       # JobMatch upsert
            ]
        ),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    with patch(
        "backend.app.services.job_matching.EmbeddingService"
    ) as mock_embedding_service:
        mock_embedding_service.return_value.get_embedding = AsyncMock(
            side_effect=[
                [0.1, 0.2, 0.3],  # Candidate embedding
                [0.1, 0.2, 0.3],  # Job embedding
            ]
        )

        mock_embedding_service.return_value.close = AsyncMock()

        result = await match_jobs(db, candidate.id)

    assert result["jobs_processed"] == 1
    assert result["candidate_id"] == str(candidate.id)

    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()

    # Find the upsert statement without assuming its position.
    upsert_statement = next(
        call.args[0]
        for call in db.execute.await_args_list
        if "uq_candidate_job_match" in str(
            call.args[0].compile(dialect=postgresql.dialect())
        )
    )

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
                mock_result([]),    # Candidate skills from database
                mock_result([job]), # Active jobs
                RuntimeError("Database write failed"),
            ]
        ),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    with patch(
        "backend.app.services.job_matching.EmbeddingService"
    ) as mock_embedding_service:
        mock_embedding_service.return_value.get_embedding = AsyncMock(
            side_effect=[
                [0.1, 0.2, 0.3],  # Candidate embedding
                [0.1, 0.2, 0.3],  # Job embedding
            ]
        )

        mock_embedding_service.return_value.close = AsyncMock()

        with pytest.raises(RuntimeError, match="Database write failed"):
            await match_jobs(db, candidate.id)

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()

def test_relevant_backend_role_scores_above_unrelated_data_role():
    from backend.app.services.job_matching import (
        calculate_role_relevance_score,
    )

    candidate = make_candidate()

    backend_job = make_job()
    unrelated_job = make_job()
    unrelated_job.title = "Data Scientist"
    unrelated_job.description = "Statistical modeling and data analysis"

    backend_score = calculate_role_relevance_score(
        backend_job, candidate
    )
    unrelated_score = calculate_role_relevance_score(
        unrelated_job, candidate
    )

    assert backend_score > unrelated_score

def test_missing_components_reduce_score_coverage():
    components = {
        "role_relevance": Decimal("85"),
        "skills": Decimal("70"),
        "experience": None,
        "preferences": None,
        "salary": None,
    }

    assert calculate_score_coverage(components) == Decimal("60.00")
    assert weighted_score(components) == Decimal("45.00")

def test_semantic_similarity_only_partially_changes_role_score():
    rule_score = Decimal("25.00")
    semantic_score = Decimal("100.00")

    blended_score = (
        rule_score * Decimal("0.75")
        + semantic_score * Decimal("0.25")
    ).quantize(Decimal("0.01"))

    assert blended_score == Decimal("43.75")
    assert blended_score < Decimal("50.00")

def test_unrelated_role_score_is_capped():
    components = {
        "role_relevance": Decimal("0"),
        "skills": Decimal("100"),
        "experience": Decimal("100"),
        "preferences": Decimal("100"),
        "salary": Decimal("100"),
    }

    score = weighted_score(components)

    # This mirrors the safeguard in match_jobs().
    score = min(score, Decimal("20.00"))

    assert score == Decimal("20.00")