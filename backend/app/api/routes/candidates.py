from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.models import Candidate
from backend.app.schemas.candidate import (
    CandidateCreate,
    CandidateRead,
    CandidateUpdate,
)

router = APIRouter(prefix="/api/candidates", tags=["Candidates"])


@router.get(
    "/{candidate_id}",
    response_model=CandidateRead,
)
async def get_candidate(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    candidate = await db.get(Candidate, candidate_id)

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    return candidate


@router.patch(
    "/{candidate_id}",
    response_model=CandidateRead,
)
async def update_candidate(
    candidate_id: UUID,
    payload: CandidateUpdate,
    db: AsyncSession = Depends(get_db),
):
    candidate = await db.get(Candidate, candidate_id)

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

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
    db: AsyncSession = Depends(get_db),
):
    candidate = Candidate(**payload.model_dump())
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