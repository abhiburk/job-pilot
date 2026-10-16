
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ApplicationStatus = Literal[
    "saved",
    "preparing",
    "applied",
    "interviewing",
    "rejected",
    "offer",
    "withdrawn",
]


class ApplicationCreate(BaseModel):
    candidate_id: UUID
    job_id: UUID
    application_url: str | None = None
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    application_url: str | None = None
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    notes: str | None = None


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    job_id: UUID
    status: str
    application_url: str | None
    applied_at: datetime | None
    follow_up_at: datetime | None
    notes: str | None
    submission_metadata: dict | None
    created_at: datetime
    updated_at: datetime


class ApplicationListItem(ApplicationRead):
    job_title: str
    company_name: str | None
    job_location: str | None
    job_url: str
    job_source: str
