
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Company, Job
from backend.app.services.jobicy import fetch_jobs
from backend.app.services.freehire import fetch_jobs as fetch_freehire_jobs
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit

def parse_datetime(value):
    """Parse ISO timestamps safely and normalize them to UTC."""
    if not value:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(
                str(value).strip().replace("Z", "+00:00")
            )
        except (TypeError, ValueError):
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def parse_decimal(value):
    """Convert a numeric value to Decimal without raising on bad input."""
    if value is None or value == "":
        return None

    try:
        cleaned = str(value).replace(",", "").strip()
        result = Decimal(cleaned)
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def normalize_job(raw):
    """Normalize a Jobicy listing to the Job model's field names."""
    if not isinstance(raw, dict):
        return None

    source_id = raw.get("id")
    title = (raw.get("jobTitle") or "").strip()
    job_url = (raw.get("url") or "").strip()

    # A listing without a title or URL is not useful to the application.
    if not title or not job_url:
        return None

    job_types = raw.get("jobType") or []
    industries = raw.get("jobIndustry") or []

    if isinstance(job_types, str):
        job_types = [job_types]

    if isinstance(industries, str):
        industries = [industries]

    location = (raw.get("jobGeo") or "").strip() or None
    remote_text = " ".join(
        [
            str(raw.get("jobGeo") or ""),
            str(raw.get("jobTitle") or ""),
            str(raw.get("jobExcerpt") or ""),
        ]
    ).lower()

    # Do not label every listing remote just because it came from a remote-job API.
    if "hybrid" in remote_text:
        remote_type = "hybrid"
    elif any(
        term in remote_text
        for term in ("on-site", "onsite", "on site", "office-based")
    ):
        remote_type = "onsite"
    elif any(
        term in remote_text
        for term in ("remote", "work from home", "anywhere")
    ):
        remote_type = "remote"
    else:
        remote_type = None

    return {
        "title": title,
        "description": raw.get("jobDescription") or raw.get("jobExcerpt"),
        "location": location,
        "remote_type": remote_type,
        "employment_type": ", ".join(
            str(item) for item in job_types if item
        )[:50] or None,
        "experience_level": raw.get("jobLevel"),
        "salary_min": parse_decimal(raw.get("annualSalaryMin")),
        "salary_max": parse_decimal(raw.get("annualSalaryMax")),
        "salary_currency": (
            str(raw.get("salaryCurrency") or "").upper()[:3] or None
        ),
        "job_url": job_url,
        "source": "jobicy",
        "source_job_id": str(source_id) if source_id is not None else None,
        "posted_at": parse_datetime(raw.get("pubDate")),
        "source_metadata": {
            "company_name": raw.get("companyName"),
            "company_logo": raw.get("companyLogo"),
            "job_industry": industries,
            "salary_period": raw.get("salaryPeriod"),
            "job_slug": raw.get("jobSlug"),
        },
    }

def normalize_freehire_job(raw: dict) -> dict | None:
    source_id = raw.get("public_slug") or raw.get("external_id")
    title = raw.get("title")
    job_url = raw.get("url")

    if not source_id or not title or not job_url:
        return None

    # Don't import jobs explicitly marked as closed.
    if raw.get("closed_at"):
        return None

    company_name = raw.get("company")
    location = raw.get("location")
    enrichment = raw.get("enrichment") or {}

    countries = raw.get("countries") or []
    skills = raw.get("skills") or []
    reality = raw.get("reality") or {}

    if isinstance(countries, str):
        countries = [countries]

    if isinstance(skills, str):
        skills = [skills]

    return {
        "source_job_id": str(source_id),
        "title": str(title).strip()[:255],
        "description": raw.get("description") or enrichment.get("summary"),
        "location": str(location).strip()[:255] if location else None,
        # Don't guess work mode when the source doesn't provide it.
        "remote_type": raw.get("work_mode"),
        "employment_type": raw.get("employment_type"),
        "experience_level": raw.get("experience_level"),
        "salary_min": parse_decimal(raw.get("salary_min")),
        "salary_max": parse_decimal(raw.get("salary_max")),
        "salary_currency": (
            str(raw["salary_currency"])[:3].upper()
            if raw.get("salary_currency")
            else None
        ),
        "job_url": str(job_url),
        "source": "freehire",
        "posted_at": parse_datetime(raw.get("posted_at")),
        "source_metadata": {
            "company_name": company_name,
            "provider_source": raw.get("source"),
            "company_slug": raw.get("company_slug"),
            "countries": countries,
            "skills": skills,
            "posting_language": enrichment.get("posting_language"),
            "reality": reality,
        },
    }

async def save_normalized_jobs(
    db,
    normalized_jobs,
    source: str,
    fetched_count: int,
):
    from sqlalchemy import func, select

    from backend.app.models import Company, Job

    # Ignore invalid entries and enforce a consistent source identifier.
    prepared = []
    skipped = max(0, fetched_count - len(normalized_jobs))

    for item in normalized_jobs:
        if not item:
            skipped += 1
            continue

        job_data = dict(item)
        job_data["source"] = source

        job_url = job_data.get("job_url")
        title = (job_data.get("title") or "").strip()

        if not title or not job_url:
            skipped += 1
            continue

        source_id = job_data.get("source_job_id")
        if source_id is not None:
            job_data["source_job_id"] = str(source_id)

        prepared.append(job_data)

    # Existing source IDs: authoritative duplicate check.
    source_ids = {
        item["source_job_id"]
        for item in prepared
        if item.get("source_job_id")
    }

    existing_ids = set()

    if source_ids:
        result = await db.execute(
            select(Job.source_job_id).where(
                Job.source == source,
                Job.source_job_id.in_(source_ids),
            )
        )
        existing_ids = {
            value for value in result.scalars().all() if value
        }

    # Existing URLs are checked only within the same source. We deliberately
    # do not merge across sources because syndicated listings can differ.
    result = await db.execute(
        select(Job.job_url).where(Job.source == source)
    )
    existing_urls = {
        normalized
        for url in result.scalars().all()
        if (normalized := normalize_job_url(url))
    }

    company_cache = {}
    created = 0

    try:
        for job_data in prepared:
            source_id = job_data.get("source_job_id")
            normalized_url = normalize_job_url(job_data.get("job_url"))

            if source_id and source_id in existing_ids:
                skipped += 1
                continue

            if normalized_url and normalized_url in existing_urls:
                skipped += 1
                continue

            metadata = job_data.get("source_metadata") or {}
            company_name = (
                metadata.get("company_name")
                or job_data.get("company_name")
                or ""
            ).strip()

            company_id = None

            if company_name:
                company_key = normalize_company_name(company_name)

                if company_key in company_cache:
                    company_id = company_cache[company_key]
                else:
                    company_result = await db.execute(
                        select(Company)
                        .where(func.lower(Company.name) == company_key)
                        .limit(1)
                    )
                    company = company_result.scalar_one_or_none()

                    if company is None:
                        company = Company(name=company_name)
                        db.add(company)
                        await db.flush()

                    company_id = company.id
                    company_cache[company_key] = company_id

            # Strip ingestion-only keys before constructing the ORM object.
            payload = {
                key: value
                for key, value in job_data.items()
                if key != "company_name"
            }
            payload["source"] = source
            payload["company_id"] = company_id

            db.add(Job(**payload))
            created += 1

            if source_id:
                existing_ids.add(source_id)

            if normalized_url:
                existing_urls.add(normalized_url)

        await db.commit()

    except Exception:
        await db.rollback()
        raise

    return {
        "source": source,
        "fetched": fetched_count,
        "created": created,
        "skipped": skipped,
    }

async def discover_and_save_jobs(
    db: AsyncSession,
    count: int = 20,
    tag: str | None = None,
) -> dict:
    raw_jobs = await fetch_jobs(count=count, tag=tag)

    normalized_jobs = [
        job
        for raw in raw_jobs
        if (job := normalize_job(raw)) is not None
    ]

    return await save_normalized_jobs(
        db=db,
        normalized_jobs=normalized_jobs,
        source="jobicy",
        fetched_count=len(raw_jobs),
    )

async def discover_and_save_freehire_jobs(
    db: AsyncSession,
    query: str = "Laravel PHP Python",
    count: int = 20,
    country: str | None = "IN",
    work_mode: str | None = None,
) -> dict:
    raw_jobs = await fetch_freehire_jobs(
        query=query,
        count=count,
        country=country,
        work_mode=work_mode,
    )

    normalized_jobs = [
        job
        for raw in raw_jobs
        if (job := normalize_freehire_job(raw)) is not None
    ]

    return await save_normalized_jobs(
        db=db,
        normalized_jobs=normalized_jobs,
        source="freehire",
        fetched_count=len(raw_jobs),
    )

def normalize_job_url(value: str | None) -> str | None:
    """
    Normalize a URL for conservative duplicate comparison.
    Remove common tracking parameters but retain the actual path.
    """
    if not value:
        return None

    try:
        parsed = urlsplit(value.strip())

        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return value.strip().rstrip("/")

        host = parsed.netloc.lower()
        path = parsed.path.rstrip("/")

        # Tracking query parameters are intentionally omitted.
        return urlunsplit(
            (
                parsed.scheme.lower(),
                host,
                path,
                "",
                "",
            )
        )
    except (TypeError, ValueError):
        return value.strip().rstrip("/")


def normalize_company_name(value: str | None) -> str:
    """Create a conservative company-name lookup key."""
    return " ".join((value or "").strip().lower().split())