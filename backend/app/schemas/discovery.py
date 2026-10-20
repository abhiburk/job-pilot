from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DiscoveryRequest(BaseModel):
    keywords: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    work_mode: Literal["remote", "hybrid", "onsite"] | None = None
    limit: int = Field(default=20, ge=1, le=50)
    # Source keys to search; all enabled sources when omitted.
    sources: list[str] | None = Field(default=None, max_length=20)

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())
        if value and len(value) < 2:
            raise ValueError("keywords must be at least 2 characters")
        return value or None

    @field_validator("country")
    @classmethod
    def clean_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.isalpha():
            raise ValueError("country must be a 2-letter ISO code")
        return value.upper()
