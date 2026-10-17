
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

from backend.app.models import Job, JobMatch, Candidate
from backend.app.services.job_matching import match_jobs
from backend.app.services.match_confidence import calculate_match_confidence
from backend.app.models import Candidate, Company, Job, JobMatch
from sqlalchemy import and_, func, or_, select
from uuid import UUID

from fastapi import HTTPException
from backend.app.services.job_ai_analysis import (
    JobAIAnalysisError,
    analyze_job_for_candidate,
)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.get("")
async def list_jobs(
    q: str | None = Query(default=None, min_length=2, max_length=150),
    candidate_id: UUID | None = Query(default=None),
    location: str | None = Query(default=None, max_length=150),
    remote_type: str | None = Query(
        default=None,
        pattern="^(remote|hybrid|onsite)$",
    ),
    experience_level: str | None = Query(default=None, max_length=100),
    employment_type: str | None = Query(default=None, max_length=50),
    min_score: float | None = Query(default=None, ge=0, le=100),
    sort_by: str = Query(
        default="newest",
        pattern="^(newest|match_score|salary_high|salary_low)$",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List active jobs with optional search, filters, and candidate ranking."""

    if min_score is not None and candidate_id is None:
        raise HTTPException(
            status_code=422,
            detail="candidate_id is required when filtering by min_score.",
        )

    if candidate_id is not None:
        candidate = await db.get(Candidate, candidate_id)
        if candidate is None:
            raise HTTPException(
                status_code=404,
                detail="Candidate not found",
            )

    match_join = and_(
        JobMatch.job_id == Job.id,
        JobMatch.candidate_id == candidate_id,
    )

    filters = [Job.is_active.is_(True)]

    if q:
        search_term = f"%{q.strip()}%"
        filters.append(
            or_(
                Job.title.ilike(search_term),
                Job.description.ilike(search_term),
                Company.name.ilike(search_term),
            )
        )

    if location:
        filters.append(Job.location.ilike(f"%{location.strip()}%"))

    if remote_type:
        filters.append(func.lower(Job.remote_type) == remote_type.lower())

    if experience_level:
        filters.append(
            Job.experience_level.ilike(f"%{experience_level.strip()}%")
        )

    if employment_type:
        filters.append(
            Job.employment_type.ilike(f"%{employment_type.strip()}%")
        )

    if min_score is not None:
        filters.append(JobMatch.score >= min_score)

    # Count all matching jobs before pagination.
    count_query = (
        select(func.count(Job.id))
        .select_from(Job)
        .outerjoin(Company, Job.company_id == Company.id)
        .outerjoin(JobMatch, match_join)
        .where(*filters)
    )
    total = await db.scalar(count_query)

    # Fetch the requested page.
    query = (
        select(
            Job,
            Company.name.label("company_name"),
            JobMatch.score.label("match_score"),
            JobMatch.skills_score,
            JobMatch.experience_score,
            JobMatch.preference_score,
            JobMatch.role_relevance_score,
            JobMatch.salary_score,
            JobMatch.strengths,
            JobMatch.gaps,
            JobMatch.explanation,
        )
        .outerjoin(Company, Job.company_id == Company.id)
        .outerjoin(JobMatch, match_join)
        .where(*filters)
    )

    if sort_by == "match_score":
        query = query.order_by(
            JobMatch.score.desc().nulls_last(),
            Job.posted_at.desc().nulls_last(),
        )
    elif sort_by == "salary_high":
        query = query.order_by(
            Job.salary_max.desc().nulls_last(),
            Job.posted_at.desc().nulls_last(),
        )
    elif sort_by == "salary_low":
        query = query.order_by(
            Job.salary_min.asc().nulls_last(),
            Job.posted_at.desc().nulls_last(),
        )
    else:
        query = query.order_by(
            Job.posted_at.desc().nulls_last(),
            Job.discovered_at.desc(),
        )

    result = await db.execute(query.limit(limit).offset(offset))

    items = []
    for row in result.all():
        job = row[0]

        items.append(
            {
                "id": str(job.id),
                "title": job.title,
                "company_id": str(job.company_id) if job.company_id else None,
                "company_name": row.company_name,
                "description": job.description,
                "location": job.location,
                "remote_type": job.remote_type,
                "employment_type": job.employment_type,
                "experience_level": job.experience_level,
                "salary_min": (
                    float(job.salary_min)
                    if job.salary_min is not None
                    else None
                ),
                "salary_max": (
                    float(job.salary_max)
                    if job.salary_max is not None
                    else None
                ),
                "salary_currency": job.salary_currency,
                "job_url": job.job_url,
                "source": job.source,
                "posted_at": job.posted_at,
                "discovered_at": job.discovered_at,
                "match_score": (
                    float(row.match_score)
                    if row.match_score is not None
                    else None
                ),
                "match_breakdown": {
                    "skills": (
                        float(row.skills_score)
                        if row.skills_score is not None else None
                    ),
                    "experience": (
                        float(row.experience_score)
                        if row.experience_score is not None else None
                    ),
                    "preferences": (
                        float(row.preference_score)
                        if row.preference_score is not None else None
                    ),
                    "role_relevance": (
                        float(row.role_relevance_score)
                        if row.role_relevance_score is not None else None
                    ),
                    "salary": (
                        float(row.salary_score)
                        if row.salary_score is not None else None
                    ),
                },
                "strengths": row.strengths or [],
                "gaps": row.gaps or [],
                "explanation": row.explanation,
            }
        )

    return {
        "items": items,
        "pagination": {
            "total": total or 0,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < (total or 0),
        },
        "filters": {
            "q": q,
            "candidate_id": str(candidate_id) if candidate_id else None,
            "location": location,
            "remote_type": remote_type,
            "experience_level": experience_level,
            "employment_type": employment_type,
            "min_score": min_score,
            "sort_by": sort_by,
        },
    }

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
            "score_coverage": (
                float(match.score_coverage)
                if match.score_coverage is not None
                else 0.0
            ),
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
                "coverage": (
                    float(match.score_coverage)
                    if match.score_coverage is not None
                    else 0.0
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


@router.post("/{job_id}/analyze/{candidate_id}")
async def analyze_job(
    job_id: UUID,
    candidate_id: UUID,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await analyze_job_for_candidate(
            db=db,
            candidate_id=candidate_id,
            job_id=job_id,
            force=force,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message in {
            "Candidate not found.",
            "Job not found.",
        } else 400

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc
    except JobAIAnalysisError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
