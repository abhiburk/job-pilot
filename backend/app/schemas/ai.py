
from uuid import UUID

from pydantic import BaseModel, Field


class CoverLetterRequest(BaseModel):
    candidate_id: UUID
    job_id: UUID


class CoverLetterResponse(BaseModel):
    candidate_id: UUID
    job_id: UUID
    model: str
    cover_letter: str
