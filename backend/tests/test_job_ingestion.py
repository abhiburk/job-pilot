
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from backend.app.models import Company, Job
from backend.app.services.job_ingestion import (
    normalize_company_name,
    normalize_freehire_job,
    normalize_job,
    normalize_job_url,
    parse_datetime,
    parse_decimal,
    save_normalized_jobs,
)


def make_job(
    *,
    source_job_id="job-1",
    title="Laravel Backend Developer",
    url="https://example.com/jobs/1",
    company_name="Example Inc",
):
    return {
        "source_job_id": source_job_id,
        "title": title,
        "description": "Build backend APIs",
        "job_url": url,
        "source": "jobicy",
        "source_metadata": {"company_name": company_name},
    }


@pytest.mark.asyncio
async def test_ingestion_creates_job_and_company(test_db):
    result = await save_normalized_jobs(
        db=test_db,
        normalized_jobs=[make_job()],
        source="jobicy",
        fetched_count=1,
    )

    assert result == {
        "source": "jobicy",
        "fetched": 1,
        "created": 1,
        "skipped": 0,
    }

    jobs = (await test_db.execute(select(Job))).scalars().all()
    companies = (await test_db.execute(select(Company))).scalars().all()

    assert len(jobs) == 1
    assert jobs[0].title == "Laravel Backend Developer"
    assert jobs[0].source_job_id == "job-1"
    assert len(companies) == 1
    assert companies[0].name == "Example Inc"
    assert jobs[0].company_id == companies[0].id


@pytest.mark.asyncio
async def test_repeated_ingestion_does_not_create_duplicate(test_db):
    job = make_job()

    first = await save_normalized_jobs(
        test_db, [job], source="jobicy", fetched_count=1
    )
    second = await save_normalized_jobs(
        test_db, [job], source="jobicy", fetched_count=1
    )

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["skipped"] == 1

    count = await test_db.scalar(select(func.count()).select_from(Job))
    assert count == 1


@pytest.mark.asyncio
async def test_duplicate_urls_in_same_batch_are_skipped(test_db):
    jobs = [
        make_job(
            source_job_id="job-1",
            url="https://example.com/jobs/1?utm_source=feed",
        ),
        make_job(
            source_job_id="job-2",
            url="https://EXAMPLE.com/jobs/1/",
        ),
    ]

    result = await save_normalized_jobs(
        test_db, jobs, source="jobicy", fetched_count=2
    )

    assert result["created"] == 1
    assert result["skipped"] == 1

    count = await test_db.scalar(select(func.count()).select_from(Job))
    assert count == 1


@pytest.mark.asyncio
async def test_invalid_records_are_skipped(test_db):
    jobs = [
        None,
        {"title": "", "job_url": "https://example.com/jobs/2"},
        {"title": "Missing URL", "job_url": ""},
        make_job(source_job_id="valid-job"),
    ]

    result = await save_normalized_jobs(
        test_db, jobs, source="jobicy", fetched_count=4
    )

    assert result["created"] == 1
    assert result["skipped"] == 3

    count = await test_db.scalar(select(func.count()).select_from(Job))
    assert count == 1


@pytest.mark.asyncio
async def test_same_source_id_can_exist_in_different_sources(test_db):
    jobs = [
        make_job(source_job_id="shared-id", url="https://jobicy.example/1"),
        make_job(source_job_id="shared-id", url="https://freehire.example/1"),
    ]

    first = await save_normalized_jobs(
        test_db, [jobs[0]], source="jobicy", fetched_count=1
    )
    second = await save_normalized_jobs(
        test_db, [jobs[1]], source="freehire", fetched_count=1
    )

    assert first["created"] == 1
    assert second["created"] == 1

    count = await test_db.scalar(select(func.count()).select_from(Job))
    assert count == 2


@pytest.mark.asyncio
async def test_database_error_rolls_back_ingestion(test_db, monkeypatch):
    async def fail_commit():
        raise RuntimeError("Simulated commit failure")

    monkeypatch.setattr(test_db, "commit", fail_commit)

    with pytest.raises(RuntimeError, match="Simulated commit failure"):
        await save_normalized_jobs(
            test_db,
            [make_job()],
            source="jobicy",
            fetched_count=1,
        )

    # save_normalized_jobs should have called rollback after the failure.
    monkeypatch.undo()

    count = await test_db.scalar(select(func.count()).select_from(Job))
    assert count == 0


def test_normalize_jobicy_record():
    normalized = normalize_job(
        {
            "id": 123,
            "jobTitle": "  Laravel Developer  ",
            "url": "https://example.com/jobs/123",
            "jobGeo": "Remote",
            "jobType": "Full-time",
            "annualSalaryMin": "80,000",
            "annualSalaryMax": "120000",
            "salaryCurrency": "usd",
            "pubDate": "2026-10-01T10:00:00Z",
            "companyName": "Example Inc",
        }
    )

    assert normalized is not None
    assert normalized["title"] == "Laravel Developer"
    assert normalized["source_job_id"] == "123"
    assert normalized["remote_type"] == "remote"
    assert normalized["employment_type"] == "Full-time"
    assert normalized["salary_min"] == Decimal("80000")
    assert normalized["salary_max"] == Decimal("120000")
    assert normalized["salary_currency"] == "USD"
    assert normalized["posted_at"].tzinfo is not None


def test_normalize_jobicy_rejects_missing_title_or_url():
    assert normalize_job({"id": 1, "jobTitle": "", "url": "https://example.com"}) is None
    assert normalize_job({"id": 1, "jobTitle": "Developer", "url": ""}) is None
    assert normalize_job("not a record") is None


def test_normalize_freehire_closed_job_is_skipped():
    assert normalize_freehire_job(
        {
            "public_slug": "closed-job",
            "title": "Developer",
            "url": "https://example.com/jobs/closed",
            "closed_at": "2026-10-01T00:00:00Z",
        }
    ) is None


def test_parse_datetime_normalizes_to_utc():
    parsed = parse_datetime("2026-10-01T15:00:00+05:30")

    assert parsed == datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)
    assert parse_datetime("not-a-date") is None
    assert parse_datetime(None) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("80,000.50", Decimal("80000.50")),
        (120000, Decimal("120000")),
        ("invalid", None),
        ("NaN", None),
        ("Infinity", None),
        (None, None),
        ("", None),
    ],
)
def test_parse_decimal(value, expected):
    assert parse_decimal(value) == expected


def test_normalize_job_url_removes_query_and_fragment():
    assert normalize_job_url(
        "HTTPS://EXAMPLE.COM/jobs/1/?utm_source=feed#details"
    ) == "https://example.com/jobs/1"


def test_normalize_company_name_collapses_whitespace():
    assert normalize_company_name("  Example   INC  ") == "example inc"
