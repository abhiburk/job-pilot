"""Adapters for the supported job providers."""

import html
from datetime import timedelta

import httpx

from backend.app.services import freehire, jobicy
from backend.app.services.job_ingestion import (
    normalize_freehire_job,
    normalize_job,
    parse_datetime,
)
from backend.app.services.job_sources.base import DiscoveryQuery, JobSource


class JobicySource(JobSource):
    key = "jobicy"
    label = "Jobicy"
    description = "Remote jobs from the Jobicy public API."
    homepage = "https://jobicy.com"
    supported_filters = frozenset({"keywords"})
    remote_only = True
    max_limit = 50
    # Jobicy API terms: polling "must not exceed once per hour".
    min_interval = timedelta(hours=1)

    async def fetch(self, query: DiscoveryQuery) -> list:
        return await jobicy.fetch_jobs(
            count=min(query.limit, self.max_limit),
            tag=query.keywords,
        )

    def normalize(self, raw) -> dict | None:
        return normalize_job(raw)


class FreeHireSource(JobSource):
    key = "freehire"
    label = "FreeHire"
    description = "Jobs aggregated by FreeHire, searchable by country and work mode."
    homepage = "https://freehire.me"
    supported_filters = frozenset({"keywords", "country", "work_mode"})
    max_limit = 100

    async def fetch(self, query: DiscoveryQuery) -> list:
        return await freehire.fetch_jobs(
            query=query.keywords or "",
            count=min(query.limit, self.max_limit),
            country=query.country,
            work_mode=query.work_mode,
        )

    def normalize(self, raw) -> dict | None:
        return normalize_freehire_job(raw)


REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"

_REMOTIVE_JOB_TYPES = {
    "full_time": "Full-Time",
    "part_time": "Part-Time",
    "contract": "Contract",
    "freelance": "Freelance",
    "internship": "Internship",
}


def normalize_remotive_job(raw) -> dict | None:
    """Map a Remotive listing to Job fields."""
    if not isinstance(raw, dict):
        return None

    source_id = raw.get("id")
    title = (raw.get("title") or "").strip()
    job_url = (raw.get("url") or "").strip()

    if not title or not job_url:
        return None

    location = (raw.get("candidate_required_location") or "").strip() or None
    job_type = (raw.get("job_type") or "").strip()
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]

    return {
        "title": html.unescape(title)[:255],
        "description": raw.get("description"),
        "location": location[:255] if location else None,
        # Remotive only lists remote positions.
        "remote_type": "remote",
        "employment_type": (
            _REMOTIVE_JOB_TYPES.get(job_type, job_type.replace("_", " ").title())[:50]
            or None
        ),
        "experience_level": None,
        # Salary is free text ("$1000 per task", "€60k - €80k"), so it is
        # kept in metadata instead of being guessed into numbers.
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "job_url": job_url,
        "source": "remotive",
        "source_job_id": str(source_id) if source_id is not None else None,
        "posted_at": parse_datetime(raw.get("publication_date")),
        "source_metadata": {
            "company_name": raw.get("company_name"),
            "company_logo": raw.get("company_logo"),
            "category": raw.get("category"),
            "tags": [str(tag) for tag in tags][:30],
            "salary_text": raw.get("salary") or None,
        },
    }


class RemotiveSource(JobSource):
    key = "remotive"
    label = "Remotive"
    description = (
        "Remote tech jobs from Remotive. Listings are delayed 24 hours by "
        "Remotive; each job links back to its Remotive page."
    )
    homepage = "https://remotive.com"
    supported_filters = frozenset({"keywords"})
    remote_only = True
    max_limit = 50
    # Remotive API terms: "max. 4 times a day"; excessive requests are blocked.
    min_interval = timedelta(hours=6)

    async def fetch(self, query: DiscoveryQuery) -> list:
        params: dict[str, str | int] = {"limit": min(query.limit, self.max_limit)}
        if query.keywords:
            params["search"] = query.keywords

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                REMOTIVE_API_URL,
                params=params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()

        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise RuntimeError("Remotive returned an invalid jobs response")

        return jobs

    def normalize(self, raw) -> dict | None:
        return normalize_remotive_job(raw)

