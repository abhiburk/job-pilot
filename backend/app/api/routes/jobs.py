
import httpx
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.services.job_ingestion import (
    discover_and_save_freehire_jobs,
    discover_and_save_jobs,
)

from sqlalchemy import select
from backend.app.models import Job, JobMatch, Candidate
from backend.app.services.job_matching import match_jobs
from backend.app.services.match_confidence import calculate_match_confidence
from backend.app.models import Candidate, Company, Job, JobMatch

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("/match/{candidate_id}")
async def run_job_matching(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await match_jobs(db, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/matches/{candidate_id}")
async def get_job_matches(
    candidate_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    candidate = await db.get(Candidate, candidate_id)

    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    query = (
        select(JobMatch, Job, Company.name.label("company_name"))
        .join(Job, JobMatch.job_id == Job.id)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(JobMatch.candidate_id == candidate_id)
        .order_by(JobMatch.score.desc())
        .limit(limit)
    )

    result = await db.execute(query)

    candidate = await db.get(Candidate, candidate_id)

    return [
        {
            "job_id": str(job.id),
            "title": job.title,
            "company_id": str(job.company_id) if job.company_id else None,
            "location": job.location,
            "remote_type": job.remote_type,
            "job_url": job.job_url,
            "score": float(match.score),
            "confidence_score": calculate_match_confidence(
                job_title=job.title,
                job_description=job.description,
                job_location=job.location,
                job_experience_level=job.experience_level,
                job_salary_min=job.salary_min,
                job_salary_max=job.salary_max,
                candidate_resume_text=(
                    candidate.resume_text if candidate else None
                ),
            ),
            "skills_score": (
                float(match.skills_score)
                if match.skills_score is not None else None
            ),
            "experience_score": (
                float(match.experience_score)
                if match.experience_score is not None else None
            ),
            "preference_score": (
                float(match.preference_score)
                if match.preference_score is not None else None
            ),
            "strengths": match.strengths or [],
            "gaps": match.gaps or [],
            "explanation": match.explanation,
            "company_name": company_name,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "employment_type": job.employment_type,
            "matched_skills": [
                item.removeprefix("Matching skill: ")
                for item in (match.strengths or [])
                if item.startswith("Matching skill: ")
            ],
            "match_breakdown": {
                "role_relevance": (
                    float(match.role_relevance_score)
                    if getattr(match, "role_relevance_score", None) is not None
                    else None
                ),
                "skills": (
                    float(match.skills_score)
                    if match.skills_score is not None
                    else None
                ),
                "experience": (
                    float(match.experience_score)
                    if match.experience_score is not None
                    else None
                ),
                "preferences": (
                    float(match.preference_score)
                    if match.preference_score is not None
                    else None
                ),
                "salary": (
                    float(match.salary_score)
                    if getattr(match, "salary_score", None) is not None
                    else None
                ),
            },
        }
        for match, job, company_name in result.all()
    ]

@router.post("/discover")
async def discover_jobs(
    count: int = Query(default=20, ge=1, le=50),
    tag: str | None = Query(default=None, min_length=3, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await discover_and_save_jobs(
            db=db,
            count=count,
            tag=tag,
        )

    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="The external job source could not provide valid results.",
        ) from exc

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to save discovered jobs.",
        ) from exc

@router.post("/discover/freehire")
async def discover_freehire_jobs(
    query: str = Query(
        default="Laravel PHP Python",
        min_length=2,
        max_length=100,
    ),
    count: int = Query(default=20, ge=1, le=100),
    country: str | None = Query(
        default="IN",
        min_length=2,
        max_length=2,
    ),
    work_mode: str | None = Query(
        default=None,
        pattern="^(remote|hybrid|onsite)$",
    ),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await discover_and_save_freehire_jobs(
            db=db,
            query=query,
            count=count,
            country=country,
            work_mode=work_mode,
        )

    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="The Freehire job source could not provide valid results.",
        ) from exc

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to save discovered Freehire jobs.",
        ) from exc
