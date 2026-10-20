
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_owned_candidate
from backend.app.core.database import get_db
from backend.app.models import User
from backend.app.services.resume_parser import (
    MAX_RESUME_SIZE,
    extract_resume_text,
)
from backend.app.services.candidate_skill_extractor import (
    extract_and_save_candidate_skills,
)
from backend.app.services.job_matching import match_jobs

router = APIRouter(
    prefix="/api/candidates/{candidate_id}/resume",
    tags=["Resumes"],
    dependencies=[Depends(get_current_user)],
)

CHUNK_SIZE = 64 * 1024


@router.post("/upload")
async def upload_resume(
    candidate_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    candidate = await get_owned_candidate(db, candidate_id, current_user)

    filename = file.filename or ""

    # Check the extension before reading the file.
    if "." not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and DOCX resumes are supported",
        )

    extension = "." + filename.rsplit(".", 1)[-1].lower()

    if extension not in {".pdf", ".docx"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and DOCX resumes are supported",
        )

    # Read in bounded chunks to avoid an unbounded upload in memory.
    content = bytearray()

    while True:
        chunk = await file.read(CHUNK_SIZE)

        if not chunk:
            break

        content.extend(chunk)

        if len(content) > MAX_RESUME_SIZE:
            await file.close()
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Resume must not exceed 5 MB",
            )

    await file.close()

    try:
        resume_text = extract_resume_text(filename, bytes(content))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to read this resume file",
        ) from exc

    
    candidate.resume_text = resume_text

    try:
        await db.commit()

        extraction_result = await extract_and_save_candidate_skills(
            db=db,
            candidate_id=candidate.id,
            resume_text=resume_text,
        )

        matching_result = await match_jobs(
            db=db,
            candidate_id=candidate.id,
        )

    except Exception:
        await db.rollback()
        raise

    return {
        "message": "Resume uploaded, skills extracted, and jobs matched successfully",
        "candidate_id": str(candidate.id),
        "characters_extracted": len(resume_text),
        "skills_found": extraction_result["skills_found"],
        "skills_added": extraction_result["skills_added"],
        "skills": extraction_result["skills"],
        "jobs_processed": matching_result["jobs_processed"],
        "model_version": matching_result["model_version"],
    }

