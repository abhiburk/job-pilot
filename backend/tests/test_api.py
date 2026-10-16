
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib import response
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.api.routes import jobs as jobs_routes
from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import Candidate


@pytest.fixture
def db():
    session = MagicMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()

    def add_candidate(candidate):
        if candidate.id is None:
            candidate.id = uuid4()

        now = datetime.now(timezone.utc)
        if candidate.created_at is None:
            candidate.created_at = now
        if candidate.updated_at is None:
            candidate.updated_at = now

    session.add.side_effect = add_candidate
    return session


@pytest.fixture
def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def make_candidate(**overrides):
    now = datetime.now(timezone.utc)

    values = {
        "id": uuid4(),
        "full_name": "Test Candidate",
        "email": "candidate@example.com",
        "phone": None,
        "headline": "Backend Developer",
        "summary": "Experienced backend engineer",
        "location": "India",
        "preferred_locations": ["India"],
        "preferred_job_titles": ["Backend Developer"],
        "preferred_employment_types": ["Full-time"],
        "preferred_work_modes": ["Remote"],
        "years_experience": Decimal("8"),
        "minimum_salary": Decimal("100000"),
        "salary_currency": "INR",
        "remote_only": False,
        "is_active": True,
        "resume_text": "Laravel and Python",
        "linkedin_url": None,
        "github_url": None,
        "portfolio_url": None,
        "created_at": now,
        "updated_at": now,
    }

    values.update(overrides)
    return SimpleNamespace(**values)


# --------------------------------------------------
# Health
# --------------------------------------------------

def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --------------------------------------------------
# Candidate API
# --------------------------------------------------

def test_create_candidate(client, db):
    response = client.post(
        "/api/candidates",
        json={
            "full_name": "Test Candidate",
            "email": "candidate@example.com",
            "headline": "Backend Developer",
            "years_experience": 8,
        },
    )

    assert response.status_code == 201
    assert response.json()["full_name"] == "Test Candidate"
    assert response.json()["email"] == "candidate@example.com"
    assert response.json()["salary_currency"] == "INR"
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()


def test_create_candidate_rejects_invalid_email(client, db):
    response = client.post(
        "/api/candidates",
        json={
            "full_name": "Test Candidate",
            "email": "not-an-email",
        },
    )

    assert response.status_code == 422
    db.add.assert_not_called()


def test_get_candidate(client, db):
    candidate = make_candidate()
    db.get.return_value = candidate

    response = client.get(f"/api/candidates/{candidate.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(candidate.id)
    assert response.json()["full_name"] == "Test Candidate"


def test_get_missing_candidate_returns_404(client, db):
    db.get.return_value = None
    candidate_id = uuid4()

    response = client.get(f"/api/candidates/{candidate_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


def test_patch_candidate(client, db):
    candidate = make_candidate()
    db.get.return_value = candidate

    response = client.patch(
        f"/api/candidates/{candidate.id}",
        json={"headline": "Senior Backend Engineer"},
    )

    assert response.status_code == 200
    assert response.json()["headline"] == "Senior Backend Engineer"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()


def test_patch_candidate_rejects_null_full_name(client, db):
    candidate_id = uuid4()

    response = client.patch(
        f"/api/candidates/{candidate_id}",
        json={"full_name": None},
    )

    assert response.status_code == 422
    db.get.assert_not_awaited()


# --------------------------------------------------
# Job matching API
# --------------------------------------------------

def test_run_matching_returns_result(client, db, monkeypatch):
    candidate_id = uuid4()

    async def fake_match_jobs(session, requested_candidate_id):
        assert session is db
        assert requested_candidate_id == candidate_id
        return {
            "candidate_id": str(candidate_id),
            "jobs_processed": 3,
            "model_version": "rules-v1",
        }

    monkeypatch.setattr(jobs_routes, "match_jobs", fake_match_jobs)

    response = client.post(f"/api/jobs/match/{candidate_id}")

    assert response.status_code == 200
    assert response.json()["jobs_processed"] == 3


def test_run_matching_returns_404_for_missing_candidate(
    client, db, monkeypatch
):
    async def fake_match_jobs(session, candidate_id):
        raise ValueError("Candidate not found")

    monkeypatch.setattr(jobs_routes, "match_jobs", fake_match_jobs)

    response = client.post(f"/api/jobs/match/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


def test_get_matches_returns_404_for_missing_candidate(client, db):
    db.get.return_value = None

    response = client.get(f"/api/jobs/matches/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


def test_get_matches_returns_ranked_results(client, db):
    candidate = make_candidate()
    job_id = uuid4()

    job = SimpleNamespace(
        id=job_id,
        title="Laravel Developer",
        company_id=None,
        location="Remote",
        remote_type="Remote",
        job_url="https://example.com/jobs/1",
        description="Detailed backend developer job description " * 10,
        experience_level="Senior",
        salary_min=100000,
        salary_max=150000,
        salary_currency="INR",
        employment_type="Full-time",
    )

    match = SimpleNamespace(
        job_id=job_id,
        score=Decimal("85.50"),
        skills_score=Decimal("90.00"),
        experience_score=Decimal("80.00"),
        preference_score=None,
        strengths=["Matching skill: Laravel"],
        gaps=["Docker"],
        explanation="Good match",
    )

    db.get.return_value = candidate
    result = MagicMock()
    result.all.return_value = [
        (match, job, "Example Company"),
    ]
    db.execute.return_value = result

    response = client.get(f"/api/jobs/matches/{candidate.id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["job_id"] == str(job_id)
    assert data[0]["score"] == 85.5
    assert data[0]["gaps"] == ["Docker"]
    assert response.json()[0]["matched_skills"] == ["Laravel"]
    assert "match_breakdown" in response.json()[0]
    assert response.json()[0]["match_breakdown"]["skills"] == 90.0


def test_get_matches_rejects_invalid_limit(client, db):
    response = client.get(f"/api/jobs/matches/{uuid4()}?limit=101")

    assert response.status_code == 422
    db.get.assert_not_awaited()
