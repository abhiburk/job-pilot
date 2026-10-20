from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_owned_candidate
from backend.app.core.database import get_db
from backend.app.models import Candidate, User
from backend.app.schemas.candidate import (
    CandidateCreate,
    CandidateRead,
    CandidateUpdate,
)

router = APIRouter(
    prefix="/api/candidates",
    tags=["Candidates"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/me",
    response_model=CandidateRead,
)
async def get_my_candidate(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    candidate = await db.scalar(
        select(Candidate).where(Candidate.user_id == current_user.id)
    )

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not created yet",
        )

    return candidate


@router.get(
    "/{candidate_id}",
    response_model=CandidateRead,
)
async def get_candidate(
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_owned_candidate(db, candidate_id, current_user)


@router.patch(
    "/{candidate_id}",
    response_model=CandidateRead,
)
async def update_candidate(
    candidate_id: UUID,
    payload: CandidateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    candidate = await get_owned_candidate(db, candidate_id, current_user)

    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(candidate, field, value)

    if not changes:
        return candidate

    try:
        await db.commit()
        await db.refresh(candidate)
        return candidate

    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The update conflicts with existing data, such as a duplicate email.",
        ) from exc

    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update candidate profile.",
        ) from exc

@router.post(
    "",
    response_model=CandidateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_candidate(
    payload: CandidateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(Candidate.id).where(Candidate.user_id == current_user.id)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account already has a candidate profile.",
        )

    candidate = Candidate(**payload.model_dump(), user_id=current_user.id)
    db.add(candidate)

    try:
        await db.commit()
        await db.refresh(candidate)
        return candidate

    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A candidate with this email may already exist.",
        ) from exc

    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create candidate profile.",
        ) from exc