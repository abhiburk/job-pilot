
import pytest
from sqlalchemy import select

from backend.app.models import Candidate, CandidateSkill, Skill
from backend.app.services.candidate_skill_extractor import (
    extract_and_save_candidate_skills,
)


@pytest.mark.asyncio
async def test_extracts_and_saves_candidate_skills(test_db):
    candidate = Candidate(
        full_name="Skill Extraction Test",
        email="skill-extraction@example.com",
        salary_currency="INR",
    )
    test_db.add(candidate)
    await test_db.commit()
    await test_db.refresh(candidate)

    resume_text = (
        "Experienced Laravel and PHP developer "
        "with PostgreSQL, Docker, and Kubernetes."
    )

    result = await extract_and_save_candidate_skills(
        test_db,
        candidate.id,
        resume_text,
    )

    assert result["skills_found"] >= 5
    assert result["skills_added"] >= 5
    assert "Laravel" in result["skills"]
    assert "Kubernetes" in result["skills"]

    associations = await test_db.execute(
        select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate.id
        )
    )
    assert len(associations.scalars().all()) >= 5


@pytest.mark.asyncio
async def test_repeated_extraction_does_not_duplicate_skills(test_db):
    candidate = Candidate(
        full_name="Duplicate Extraction Test",
        email="duplicate-extraction@example.com",
        salary_currency="INR",
    )
    test_db.add(candidate)
    await test_db.commit()
    await test_db.refresh(candidate)

    text = "Laravel PHP Docker"

    first = await extract_and_save_candidate_skills(
        test_db, candidate.id, text
    )
    second = await extract_and_save_candidate_skills(
        test_db, candidate.id, text
    )

    assert first["skills_added"] >= 1
    assert second["skills_added"] == 0

    associations = await test_db.execute(
        select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate.id
        )
    )
    assert len(associations.scalars().all()) == first["skills_added"]
