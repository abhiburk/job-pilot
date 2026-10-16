
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import CandidateSkill, Skill
from backend.app.services.job_matching import extract_skills


async def extract_and_save_candidate_skills(
    db: AsyncSession,
    candidate_id,
    resume_text: str,
) -> dict:
    """Extract recognized skills and associate them with a candidate."""

    skill_names = sorted(extract_skills(resume_text))

    if not skill_names:
        return {
            "skills_found": 0,
            "skills_added": 0,
            "skills": [],
        }

    try:
        # Insert missing global skills without failing on duplicate names.
        skill_insert = insert(Skill).values(
            [{"name": name} for name in skill_names]
        )
        skill_insert = skill_insert.on_conflict_do_nothing(
            index_elements=[Skill.name]
        )
        await db.execute(skill_insert)

        # Fetch the canonical Skill records.
        result = await db.execute(
            select(Skill).where(Skill.name.in_(skill_names))
        )
        skills = result.scalars().all()

        # Add candidate associations, skipping existing associations.
        association_insert = insert(CandidateSkill).values(
            [
                {
                    "candidate_id": candidate_id,
                    "skill_id": skill.id,
                    "is_primary": False,
                }
                for skill in skills
            ]
        )
        association_insert = association_insert.on_conflict_do_nothing(
            constraint="uq_candidate_skill"
        )

        insert_result = await db.execute(association_insert)
        await db.commit()

        return {
            "skills_found": len(skill_names),
            "skills_added": insert_result.rowcount or 0,
            "skills": sorted(skill.name for skill in skills),
        }

    except Exception:
        await db.rollback()
        raise
