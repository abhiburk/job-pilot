
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CandidateSkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    proficiency: str | None = Field(default=None, max_length=50)
    years_experience: Decimal | None = Field(
        default=None,
        ge=0,
        le=60,
    )
    is_primary: bool = False


class CandidateSkillUpdate(BaseModel):
    proficiency: str | None = Field(default=None, max_length=50)
    years_experience: Decimal | None = Field(
        default=None,
        ge=0,
        le=60,
    )
    is_primary: bool | None = None


class CandidateSkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    skill_id: UUID
    name: str
    category: str | None
    proficiency: str | None
    years_experience: Decimal | None
    is_primary: bool
