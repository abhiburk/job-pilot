
from backend.app.services.job_ingestion import normalize_freehire_job


def test_normalize_freehire_job():
    raw = {
        "public_slug": "laravel-developer-example",
        "source": "example_board",
        "url": "https://example.com/jobs/123",
        "title": "Laravel Developer",
        "company": "Example Co",
        "location": "Pune, India",
        "description": "Build Laravel applications.",
        "countries": ["in"],
        "skills": ["laravel", "php"],
        "posted_at": "2026-10-16T05:27:11Z",
        "closed_at": None,
        "reality": {"class": "fresh", "age_days": 0},
        "enrichment": {"posting_language": "en"},
    }

    job = normalize_freehire_job(raw)

    assert job is not None
    assert job["source"] == "freehire"
    assert job["source_job_id"] == "laravel-developer-example"
    assert job["title"] == "Laravel Developer"
    assert job["location"] == "Pune, India"
    assert job["remote_type"] is None
    assert job["source_metadata"]["provider_source"] == "example_board"
    assert job["source_metadata"]["skills"] == ["laravel", "php"]
    assert job["posted_at"].tzinfo is not None


def test_normalize_freehire_job_uses_external_id_fallback():
    raw = {
        "external_id": "12345",
        "title": "Backend Engineer",
        "url": "https://example.com/jobs/12345",
    }

    job = normalize_freehire_job(raw)

    assert job is not None
    assert job["source_job_id"] == "12345"


def test_normalize_freehire_job_skips_missing_required_fields():
    assert normalize_freehire_job({"title": "Developer"}) is None


def test_normalize_freehire_job_skips_closed_jobs():
    raw = {
        "public_slug": "closed-job",
        "title": "Developer",
        "url": "https://example.com/jobs/closed",
        "closed_at": "2026-10-15T10:00:00Z",
    }

    assert normalize_freehire_job(raw) is None
