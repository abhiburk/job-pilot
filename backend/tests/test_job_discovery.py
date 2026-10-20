from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from backend.app.core.config import settings
from backend.app.models import AgentRun, Job
from backend.app.services import job_sources
from backend.app.services.job_discovery import (
    UnknownSourceError,
    run_discovery,
    select_sources,
)
from backend.app.services.job_sources import DiscoveryQuery
from backend.app.services.job_sources.providers import normalize_remotive_job
from backend.tests.auth_helpers import api_client, csrf, register


def jobicy_raw(job_id="j1"):
    return {
        "id": job_id,
        "jobTitle": "Python Developer",
        "url": f"https://jobicy.com/jobs/{job_id}",
        "companyName": "Acme",
        "jobGeo": "Anywhere",
        "jobDescription": "Build APIs",
    }


def freehire_raw(slug="f1"):
    return {
        "public_slug": slug,
        "title": "Backend Engineer",
        "url": f"https://freehire.me/jobs/{slug}",
        "company": "Globex",
        "work_mode": "hybrid",
        "countries": ["IN"],
    }


def remotive_raw(job_id=101):
    return {
        "id": job_id,
        "url": f"https://remotive.com/remote-jobs/software-development/x-{job_id}",
        "title": "Senior Django Engineer &amp; Lead",
        "company_name": "Initech",
        "category": "Software Development",
        "tags": ["python", "django"],
        "job_type": "full_time",
        "publication_date": "2026-10-17T16:04:29",
        "candidate_required_location": "Worldwide",
        "salary": "$90k - $120k",
        "description": "<p>Work on Django</p>",
    }


@pytest.fixture
def stub_fetch(monkeypatch):
    """Replace every registered source's network call."""
    mocks = {
        "jobicy": AsyncMock(return_value=[jobicy_raw()]),
        "freehire": AsyncMock(return_value=[freehire_raw()]),
        "remotive": AsyncMock(return_value=[remotive_raw()]),
    }
    for key, mock in mocks.items():
        monkeypatch.setattr(job_sources.get_source(key), "fetch", mock)
    return mocks


def test_registry_lists_three_sources_with_unique_keys():
    keys = [source.key for source in job_sources.all_sources()]
    assert keys == ["jobicy", "freehire", "remotive"]


def test_disabled_sources_are_excluded(monkeypatch):
    monkeypatch.setattr(settings, "job_sources_disabled", "remotive, JOBICY")
    assert [s.key for s in job_sources.enabled_sources()] == ["freehire"]
    with pytest.raises(UnknownSourceError):
        select_sources(["remotive"])


def test_unknown_source_is_rejected():
    with pytest.raises(UnknownSourceError):
        select_sources(["linkedin"])


def test_remotive_normalization():
    job = normalize_remotive_job(remotive_raw())

    assert job["title"] == "Senior Django Engineer & Lead"
    assert job["source"] == "remotive"
    assert job["source_job_id"] == "101"
    assert job["remote_type"] == "remote"
    assert job["employment_type"] == "Full-Time"
    assert job["salary_min"] is None
    assert job["source_metadata"]["salary_text"] == "$90k - $120k"
    assert job["source_metadata"]["company_name"] == "Initech"
    assert job["posted_at"].tzinfo is not None
    assert normalize_remotive_job({"id": 1, "title": "", "url": "x"}) is None


def test_ignored_filters_and_remote_only_rules():
    remotive = job_sources.get_source("remotive")
    freehire = job_sources.get_source("freehire")
    query = DiscoveryQuery(keywords="python", country="IN", work_mode="remote")

    assert remotive.ignored_filters(query) == ["country"]
    assert freehire.ignored_filters(query) == []
    assert remotive.skip_reason(query) is None
    assert "remote jobs only" in remotive.skip_reason(DiscoveryQuery(work_mode="onsite"))


@pytest.mark.asyncio
async def test_discovery_saves_jobs_from_every_source(test_db, stub_fetch):
    query = DiscoveryQuery(keywords="python", country="IN", limit=10)
    result = await run_discovery(test_db, query)

    statuses = {item["source"]: item["status"] for item in result["results"]}
    assert statuses == {"jobicy": "succeeded", "freehire": "succeeded", "remotive": "succeeded"}
    assert result["totals"]["created"] == 3

    sources = set((await test_db.scalars(select(Job.source))).all())
    assert sources == {"jobicy", "freehire", "remotive"}

    # Each source got the same generic query.
    for mock in stub_fetch.values():
        assert mock.await_args.args[0] == query

    by_source = {item["source"]: item for item in result["results"]}
    assert by_source["remotive"]["ignored_filters"] == ["country"]
    assert by_source["freehire"]["ignored_filters"] == []

    runs = (await test_db.scalars(select(AgentRun))).all()
    assert {run.run_type for run in runs} == {
        "job_discovery:jobicy", "job_discovery:freehire", "job_discovery:remotive",
    }
    assert {run.status for run in runs} == {"succeeded"}


@pytest.mark.asyncio
async def test_one_failing_source_does_not_stop_others(test_db, stub_fetch):
    stub_fetch["jobicy"].side_effect = RuntimeError("upstream 500")

    result = await run_discovery(test_db, DiscoveryQuery(keywords="python"))
    by_source = {item["source"]: item for item in result["results"]}

    assert by_source["jobicy"]["status"] == "failed"
    assert by_source["jobicy"]["message"] == "Jobicy could not provide valid results."
    assert "upstream" not in by_source["jobicy"]["message"]
    assert by_source["freehire"]["status"] == "succeeded"
    assert by_source["remotive"]["status"] == "succeeded"
    assert result["totals"] == {"fetched": 2, "created": 2, "skipped": 0, "succeeded": 2, "failed": 1}

    failed_run = await test_db.scalar(
        select(AgentRun).where(AgentRun.run_type == "job_discovery:jobicy")
    )
    assert failed_run.status == "failed"
    assert "upstream 500" in failed_run.error_message


@pytest.mark.asyncio
async def test_provider_request_limits_are_enforced(test_db, stub_fetch):
    await run_discovery(test_db, DiscoveryQuery(keywords="python"))
    second = await run_discovery(test_db, DiscoveryQuery(keywords="django"))
    by_source = {item["source"]: item for item in second["results"]}

    # Jobicy (1 h) and Remotive (6 h) are not contacted again; FreeHire has no limit.
    assert stub_fetch["jobicy"].await_count == 1
    assert stub_fetch["remotive"].await_count == 1
    assert stub_fetch["freehire"].await_count == 2
    assert by_source["jobicy"]["status"] == "skipped"
    assert by_source["jobicy"]["message"] == "Jobicy allows one request every 1 hour."
    assert by_source["remotive"]["message"] == "Remotive allows one request every 6 hours."
    assert by_source["remotive"]["next_available_at"] > datetime.now(timezone.utc) + timedelta(hours=5)

    # Once the interval has passed the source runs again.
    runs = (await test_db.scalars(select(AgentRun).where(AgentRun.run_type == "job_discovery:jobicy"))).all()
    for run in runs:
        run.started_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await test_db.commit()

    third = await run_discovery(test_db, DiscoveryQuery(), ["jobicy"])
    assert third["results"][0]["status"] == "succeeded"
    assert stub_fetch["jobicy"].await_count == 2


@pytest.mark.asyncio
async def test_remote_only_sources_are_skipped_for_onsite(test_db, stub_fetch):
    result = await run_discovery(test_db, DiscoveryQuery(work_mode="onsite"))
    by_source = {item["source"]: item for item in result["results"]}

    assert by_source["jobicy"]["status"] == "skipped"
    assert by_source["remotive"]["message"] == "Remotive lists remote jobs only."
    assert by_source["freehire"]["status"] == "succeeded"
    stub_fetch["jobicy"].assert_not_awaited()
    stub_fetch["remotive"].assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_listings_are_not_duplicated(test_db, stub_fetch):
    await run_discovery(test_db, DiscoveryQuery(), ["freehire"])
    second = await run_discovery(test_db, DiscoveryQuery(), ["freehire"])

    assert second["results"][0]["created"] == 0
    assert second["results"][0]["skipped"] == 1
    assert await test_db.scalar(select(func.count(Job.id))) == 1


@pytest.mark.asyncio
async def test_discovery_api(test_db, stub_fetch, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        session = await register(client, "discover@example.com")

        sources = await client.get("/api/jobs/sources")
        assert sources.status_code == 200
        listed = {item["key"]: item for item in sources.json()}
        assert set(listed) == {"jobicy", "freehire", "remotive"}
        assert listed["remotive"]["min_interval_minutes"] == 360
        assert listed["remotive"]["last_run"] is None

        invalid = await client.post(
            "/api/jobs/discovery",
            json={"keywords": "x", "country": "IND"},
            headers=csrf(session),
        )
        assert invalid.status_code == 422

        unknown = await client.post(
            "/api/jobs/discovery",
            json={"sources": ["linkedin"]},
            headers=csrf(session),
        )
        assert unknown.status_code == 422

        response = await client.post(
            "/api/jobs/discovery",
            json={"keywords": "  python  ", "country": "in", "sources": ["freehire", "remotive"]},
            headers=csrf(session),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["query"]["keywords"] == "python"
        assert body["query"]["country"] == "IN"
        assert [item["source"] for item in body["results"]] == ["freehire", "remotive"]
        stub_fetch["jobicy"].assert_not_awaited()

        after = {item["key"]: item for item in (await client.get("/api/jobs/sources")).json()}
        assert after["remotive"]["last_run"]["status"] == "succeeded"
        assert after["remotive"]["last_run"]["created"] == 1
        assert after["remotive"]["next_available_at"] is not None
        assert after["freehire"]["next_available_at"] is None

        filtered = await client.get("/api/jobs", params={"source": "remotive"})
        assert [item["source"] for item in filtered.json()["items"]] == ["remotive"]


@pytest.mark.asyncio
async def test_limit_is_applied_even_if_provider_ignores_it(test_db, stub_fetch):
    stub_fetch["remotive"].return_value = [remotive_raw(i) for i in range(5)]

    result = await run_discovery(test_db, DiscoveryQuery(limit=2), ["remotive"])

    assert result["results"][0]["fetched"] == 2
    assert result["results"][0]["created"] == 2
