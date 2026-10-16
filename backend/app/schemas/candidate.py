from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class CandidateUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    location: str | None = Field(default=None, max_length=255)

    preferred_locations: list[str] | None = None
    preferred_job_titles: list[str] | None = None
    preferred_employment_types: list[str] | None = None
    preferred_work_modes: list[str] | None = None

    years_experience: Decimal | None = Field(default=None, ge=0, le=999.9)
    minimum_salary: Decimal | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)

    remote_only: bool | None = None
    is_active: bool | None = None

    resume_text: str | None = None
    linkedin_url: str | None = Field(default=None, max_length=500)
    github_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_non_nullable_fields(self):
        non_nullable = {"full_name", "email", "salary_currency"}

        for field in non_nullable:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")

        if self.salary_currency is not None and not self.salary_currency.isalpha():
            raise ValueError("salary_currency must contain letters only")

        return self


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    headline: str | None
    summary: str | None
    location: str | None

    preferred_locations: list[str] | None
    preferred_job_titles: list[str] | None
    preferred_employment_types: list[str] | None
    preferred_work_modes: list[str] | None

    years_experience: Decimal | None
    minimum_salary: Decimal | None
    salary_currency: str
    remote_only: bool
    is_active: bool

    resume_text: str | None
    linkedin_url: str | None
    github_url: str | None
    portfolio_url: str | None

    created_at: datetime
    updated_at: datetime

class CandidateCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    location: str | None = Field(default=None, max_length=255)

    preferred_locations: list[str] | None = None
    preferred_job_titles: list[str] | None = None
    preferred_employment_types: list[str] | None = None
    preferred_work_modes: list[str] | None = None

    years_experience: Decimal | None = Field(default=None, ge=0, le=999.9)
    minimum_salary: Decimal | None = Field(default=None, ge=0)
    salary_currency: str = Field(default="INR", min_length=3, max_length=3)

    remote_only: bool = False
    is_active: bool = True

    resume_text: str | None = None
    linkedin_url: str | None = Field(default=None, max_length=500)
    github_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)