
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend.app.api.routes.candidate_skills import (
    add_candidate_skill,
    list_candidate_skills,
    remove_candidate_skill,
    update_candidate_skill,
)
from backend.app.models import Candidate, Skill
from backend.app.schemas.candidate_skill import (
    CandidateSkillCreate,
    CandidateSkillUpdate,
)


@pytest.mark.asyncio
async def test_candidate_skill_full_lifecycle(test_db):
    candidate = Candidate(
        full_name="Skills Integration Test",
        email="skills-integration@example.com",
        headline="Python Developer",
        years_experience=4,
        salary_currency="INR",
    )
    test_db.add(candidate)
    await test_db.commit()
    await test_db.refresh(candidate)

    # Add a skill.
    created = await add_candidate_skill(
        candidate.id,
        CandidateSkillCreate(
            name="Python",
            category="Backend",
            proficiency="Advanced",
            years_experience=3,
            is_primary=True,
        ),
        test_db,
    )

    assert created.name == "Python"
    assert created.proficiency == "Advanced"
    assert created.is_primary is True

    # List the candidate's skills.
    skills = await list_candidate_skills(candidate.id, test_db)

    assert len(skills) == 1
    assert skills[0].skill_id == created.skill_id

    # Update proficiency and years of experience.
    updated = await update_candidate_skill(
        candidate.id,
        created.id,
        CandidateSkillUpdate(
            proficiency="Expert",
            years_experience=4,
        ),
        test_db,
    )

    assert updated.proficiency == "Expert"
    assert updated.years_experience == 4

    # Remove the association from the candidate.
    response = await remove_candidate_skill(
        candidate.id,
        created.id,
        test_db,
    )

    assert response.status_code == 204

    skills_after_delete = await list_candidate_skills(
        candidate.id,
        test_db,
    )
    assert skills_after_delete == []

    # The shared Skill record should still exist.
    result = await test_db.execute(
        select(Skill).where(Skill.name == "Python")
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_duplicate_candidate_skill_returns_conflict(test_db):
    candidate = Candidate(
        full_name="Duplicate Skill Test",
        email="duplicate-skill@example.com",
        salary_currency="INR",
    )
    test_db.add(candidate)
    await test_db.commit()
    await test_db.refresh(candidate)

    payload = CandidateSkillCreate(name="Laravel")

    await add_candidate_skill(candidate.id, payload, test_db)

    with pytest.raises(HTTPException) as exc_info:
        await add_candidate_skill(candidate.id, payload, test_db)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_missing_candidate_returns_404(test_db):
    from uuid import uuid4

    with pytest.raises(HTTPException) as exc_info:
        await list_candidate_skills(uuid4(), test_db)

    assert exc_info.value.status_code == 404
