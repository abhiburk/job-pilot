
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.database import get_db
from backend.app.models import Candidate, CandidateSkill, Skill
from backend.app.schemas.candidate_skill import (
    CandidateSkillCreate,
    CandidateSkillRead,
    CandidateSkillUpdate,
)

router = APIRouter(
    prefix="/api/candidates/{candidate_id}/skills",
    tags=["Candidate Skills"],
)


async def get_candidate_or_404(
    db: AsyncSession,
    candidate_id: UUID,
) -> Candidate:
    candidate = await db.get(Candidate, candidate_id)

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    return candidate


def serialize_candidate_skill(
    association: CandidateSkill,
) -> CandidateSkillRead:
    return CandidateSkillRead(
        id=association.id,
        skill_id=association.skill_id,
        name=association.skill.name,
        category=association.skill.category,
        proficiency=association.proficiency,
        years_experience=association.years_experience,
        is_primary=association.is_primary,
    )


@router.post(
    "",
    response_model=CandidateSkillRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_candidate_skill(
    candidate_id: UUID,
    payload: CandidateSkillCreate,
    db: AsyncSession = Depends(get_db),
):
    await get_candidate_or_404(db, candidate_id)

    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=422,
            detail="Skill name cannot be blank",
        )

    try:
        skill_result = await db.execute(
            select(Skill).where(Skill.name.ilike(name))
        )
        skill = skill_result.scalar_one_or_none()

        if skill is None:
            skill = Skill(
                name=name,
                category=payload.category,
            )
            db.add(skill)
            await db.flush()
        elif payload.category and not skill.category:
            skill.category = payload.category

        existing_result = await db.execute(
            select(CandidateSkill).where(
                CandidateSkill.candidate_id == candidate_id,
                CandidateSkill.skill_id == skill.id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Candidate already has this skill",
            )

        association = CandidateSkill(
            candidate_id=candidate_id,
            skill_id=skill.id,
            proficiency=payload.proficiency,
            years_experience=payload.years_experience,
            is_primary=payload.is_primary,
        )
        db.add(association)
        await db.commit()

        result = await db.execute(
            select(CandidateSkill)
            .options(selectinload(CandidateSkill.skill))
            .where(CandidateSkill.id == association.id)
        )
        association = result.scalar_one()

        return serialize_candidate_skill(association)

    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This skill already exists or conflicts with another request",
        )


@router.get("", response_model=list[CandidateSkillRead])
async def list_candidate_skills(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await get_candidate_or_404(db, candidate_id)

    result = await db.execute(
        select(CandidateSkill)
        .options(selectinload(CandidateSkill.skill))
        .where(CandidateSkill.candidate_id == candidate_id)
        .order_by(CandidateSkill.is_primary.desc(), Skill.name)
        .join(CandidateSkill.skill)
    )

    return [
        serialize_candidate_skill(item)
        for item in result.scalars().all()
    ]


@router.patch(
    "/{skill_id}",
    response_model=CandidateSkillRead,
)
async def update_candidate_skill(
    candidate_id: UUID,
    skill_id: UUID,
    payload: CandidateSkillUpdate,
    db: AsyncSession = Depends(get_db),
):
    await get_candidate_or_404(db, candidate_id)

    result = await db.execute(
        select(CandidateSkill)
        .options(selectinload(CandidateSkill.skill))
        .where(
            CandidateSkill.candidate_id == candidate_id,
            CandidateSkill.id == skill_id,
        )
    )
    association = result.scalar_one_or_none()

    if association is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate skill not found",
        )

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(association, field, value)

    await db.commit()

    result = await db.execute(
        select(CandidateSkill)
        .options(selectinload(CandidateSkill.skill))
        .where(CandidateSkill.id == skill_id)
    )
    association = result.scalar_one()

    return serialize_candidate_skill(association)


@router.delete(
    "/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_candidate_skill(
    candidate_id: UUID,
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await get_candidate_or_404(db, candidate_id)

    result = await db.execute(
        select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate_id,
            CandidateSkill.id == skill_id,
        )
    )
    association = result.scalar_one_or_none()

    if association is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate skill not found",
        )

    await db.delete(association)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
