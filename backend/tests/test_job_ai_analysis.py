from backend.app.services.job_ai_analysis import (
    JobAIAnalysisError,
    _parse_analysis,
)
import json

import pytest
from sqlalchemy import select

from backend.app import models  # noqa: F401
from backend.app.models import Candidate, CandidateSkill, Job, Skill
from backend.app.services import job_ai_analysis as analysis_service


def test_parse_valid_analysis():
    result = _parse_analysis(
        """
        {
          "fit_score": 86,
          "recommendation": "strong_fit",
          "summary": "Relevant backend experience.",
          "strengths": ["Laravel experience"],
          "missing_requirements": [],
          "evidence_gaps": ["Cloud deployment experience unclear"],
          "concerns": []
        }
        """
    )

    assert result["fit_score"] == 86
    assert result["recommendation"] == "strong_fit"
    assert result["strengths"] == ["Laravel experience"]


def test_reject_invalid_fit_score():
    with pytest.raises(JobAIAnalysisError):
        _parse_analysis(
            """
            {
              "fit_score": 150,
              "recommendation": "strong_fit",
              "summary": "Looks good",
              "strengths": [],
              "missing_requirements": [],
              "evidence_gaps": [],
              "concerns": []
            }
            """
        )


def test_reject_invalid_json():
    with pytest.raises(JobAIAnalysisError):
        _parse_analysis("This is not JSON")


def test_parse_analysis_with_markdown_code_fence():
    result = _parse_analysis(
        """```json
        {
          "fit_score": 75,
          "recommendation": "possible_fit",
          "summary": "Some relevant experience.",
          "strengths": ["Backend development"],
          "missing_requirements": [],
          "evidence_gaps": [],
          "concerns": []
        }
        ```"""
    )

    assert result["fit_score"] == 75
    assert result["recommendation"] == "possible_fit"


def test_reject_invalid_recommendation():
    with pytest.raises(JobAIAnalysisError):
        _parse_analysis(
            """
            {
              "fit_score": 75,
              "recommendation": "guaranteed_hire",
              "summary": "Looks good",
              "strengths": [],
              "missing_requirements": [],
              "evidence_gaps": [],
              "concerns": []
            }
            """
        )


def test_reject_missing_required_field():
    with pytest.raises(JobAIAnalysisError):
        _parse_analysis(
            """
            {
              "fit_score": 75,
              "recommendation": "possible_fit",
              "summary": "Some relevant experience.",
              "strengths": [],
              "missing_requirements": [],
              "evidence_gaps": []
            }
            """
        )

def make_ai_response(fit_score=82):
    return json.dumps({
        "fit_score": fit_score,
        "recommendation": "strong_fit",
        "summary": "Relevant backend development experience.",
        "strengths": ["Laravel experience"],
        "missing_requirements": [],
        "evidence_gaps": [],
        "concerns": [],
    })


async def create_analysis_test_data(db):
    candidate = Candidate(
        full_name="Test Candidate",
        email="jobpilot-analysis-test@example.com",
        headline="Backend Developer",
        summary="Experienced backend developer.",
        resume_text="PHP, Laravel, PostgreSQL, REST APIs",
        years_experience=8,
    )
    job = Job(
        title="Senior Backend Developer",
        description="Requires PHP, Laravel and PostgreSQL experience.",
        job_url="https://example.com/jobs/test-backend",
        source="analysis-test",
        source_job_id="analysis-test-job-1",
    )
    skill = Skill(
        name="Laravel",
        category="Backend",
    )

    db.add_all([candidate, job, skill])
    await db.flush()

    candidate_skill = CandidateSkill(
        candidate_id=candidate.id,
        skill_id=skill.id,
        proficiency="advanced",
        years_experience=6,
        is_primary=True,
    )
    db.add(candidate_skill)
    await db.commit()

    return candidate, job, candidate_skill


@pytest.mark.asyncio
async def test_analysis_returns_cached_result(test_db, monkeypatch):
    candidate, job, _ = await create_analysis_test_data(test_db)
    calls = []

    async def fake_generate_text(**kwargs):
        calls.append(kwargs)
        return make_ai_response()

    monkeypatch.setattr(
        analysis_service, "generate_text", fake_generate_text
    )

    first = await analysis_service.analyze_job_for_candidate(
        db=test_db,
        candidate_id=candidate.id,
        job_id=job.id,
    )
    second = await analysis_service.analyze_job_for_candidate(
        db=test_db,
        candidate_id=candidate.id,
        job_id=job.id,
    )

    assert first["cached"] is False
    assert second["cached"] is True
    assert first["analysis"]["fit_score"] == second["analysis"]["fit_score"]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_skill_change_invalidates_cached_analysis(
    test_db, monkeypatch
):
    candidate, job, candidate_skill = await create_analysis_test_data(
        test_db
    )
    calls = []

    async def fake_generate_text(**kwargs):
        calls.append(kwargs)
        return make_ai_response(fit_score=80 + len(calls))

    monkeypatch.setattr(
        analysis_service, "generate_text", fake_generate_text
    )

    first = await analysis_service.analyze_job_for_candidate(
        db=test_db,
        candidate_id=candidate.id,
        job_id=job.id,
    )

    candidate_skill.proficiency = "intermediate"
    await test_db.commit()

    second = await analysis_service.analyze_job_for_candidate(
        db=test_db,
        candidate_id=candidate.id,
        job_id=job.id,
    )

    assert first["cached"] is False
    assert second["cached"] is False
    assert len(calls) == 2
    assert second["analysis"]["fit_score"] != first["analysis"]["fit_score"]


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache(test_db, monkeypatch):
    candidate, job, _ = await create_analysis_test_data(test_db)
    calls = []

    async def fake_generate_text(**kwargs):
        calls.append(kwargs)
        return make_ai_response(fit_score=80 + len(calls))

    monkeypatch.setattr(
        analysis_service, "generate_text", fake_generate_text
    )

    first = await analysis_service.analyze_job_for_candidate(
        db=test_db,
        candidate_id=candidate.id,
        job_id=job.id,
    )
    second = await analysis_service.analyze_job_for_candidate(
        db=test_db,
        candidate_id=candidate.id,
        job_id=job.id,
        force=True,
    )

    assert first["cached"] is False
    assert second["cached"] is False
    assert len(calls) == 2
    assert second["analysis"]["fit_score"] != first["analysis"]["fit_score"]
