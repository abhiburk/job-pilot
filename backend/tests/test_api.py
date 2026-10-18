
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

from backend.app.api.routes import applications as applications_routes
from backend.app.models import Application, ApplicationDocument
from backend.app.models import Company, Job

@pytest.fixture
def db():
    session = MagicMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()

    
    def add_candidate(instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid4()

        now = datetime.now(timezone.utc)

        if hasattr(instance, "created_at") and instance.created_at is None:
            instance.created_at = now

        if hasattr(instance, "updated_at") and instance.updated_at is None:
            instance.updated_at = now


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
        score_coverage=Decimal("80.00"),
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


# --------------------------------------------------
# Job Dashboard API
# --------------------------------------------------

from collections import namedtuple


DashboardRow = namedtuple(
    "DashboardRow",
    [
        "job",
        "company_name",
        "match_score",
        "skills_score",
        "experience_score",
        "preference_score",
        "role_relevance_score",
        "salary_score",
        "strengths",
        "gaps",
        "explanation",
    ],
)


def make_dashboard_job(**overrides):
    """Build a lightweight job object for dashboard response tests."""
    data = {
        "id": uuid4(),
        "title": "Senior Laravel Developer",
        "company_id": uuid4(),
        "description": "Build APIs with Laravel and PostgreSQL",
        "location": "Remote, India",
        "remote_type": "remote",
        "employment_type": "full-time",
        "experience_level": "senior",
        "salary_min": Decimal("1500000"),
        "salary_max": Decimal("2500000"),
        "salary_currency": "INR",
        "job_url": "https://example.com/jobs/laravel",
        "source": "test",
        "posted_at": datetime.now(timezone.utc),
        "discovered_at": datetime.now(timezone.utc),
        "is_active": True,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_dashboard_row(job=None, **overrides):
    data = {
        "job": job or make_dashboard_job(),
        "company_name": "Example Technologies",
        "match_score": Decimal("85.50"),
        "skills_score": Decimal("90.00"),
        "experience_score": Decimal("80.00"),
        "preference_score": Decimal("75.00"),
        "role_relevance_score": Decimal("88.00"),
        "salary_score": Decimal("70.00"),
        "strengths": ["Matching skill: Laravel"],
        "gaps": ["Missing skill: Kubernetes"],
        "explanation": "Strong match for the role.",
    }
    data.update(overrides)
    return DashboardRow(**data)



def setup_dashboard_result(db, rows=None, total=1):
    """Configure the mocked count and paginated query results."""
    db.scalar = AsyncMock(return_value=total)

    result = MagicMock()
    result.all.return_value = rows or []
    db.execute = AsyncMock(return_value=result)



def test_list_jobs_returns_paginated_results(client, db):
    job = make_dashboard_job()
    setup_dashboard_result(
        db,
        rows=[make_dashboard_row(job)],
        total=1,
    )

    response = client.get("/api/jobs")

    assert response.status_code == 200
    body = response.json()

    assert body["pagination"]["total"] == 1
    assert body["pagination"]["limit"] == 20
    assert body["pagination"]["offset"] == 0
    assert body["pagination"]["has_more"] is False

    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(job.id)
    assert body["items"][0]["title"] == job.title
    assert body["items"][0]["company_name"] == "Example Technologies"
    assert body["items"][0]["match_score"] == 85.5
    assert body["items"][0]["match_breakdown"]["skills"] == 90.0


def test_list_jobs_returns_empty_results(client, db):
    setup_dashboard_result(db, rows=[], total=0)

    response = client.get("/api/jobs")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["pagination"]["total"] == 0
    assert response.json()["pagination"]["has_more"] is False


def test_list_jobs_supports_search_and_filters(client, db):
    setup_dashboard_result(db, rows=[], total=0)

    response = client.get(
        "/api/jobs",
        params={
            "q": "Laravel",
            "location": "India",
            "remote_type": "remote",
            "experience_level": "senior",
            "employment_type": "full-time",
        },
    )

    assert response.status_code == 200
    filters = response.json()["filters"]

    assert filters["q"] == "Laravel"
    assert filters["location"] == "India"
    assert filters["remote_type"] == "remote"
    assert filters["experience_level"] == "senior"
    assert filters["employment_type"] == "full-time"


def test_list_jobs_supports_pagination(client, db):
    first_job = make_dashboard_job()
    second_job = make_dashboard_job(title="Backend Engineer")

    setup_dashboard_result(
        db,
        rows=[
            make_dashboard_row(first_job),
            make_dashboard_row(second_job),
        ],
        total=5,
    )

    response = client.get(
        "/api/jobs",
        params={"limit": 2, "offset": 2},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["pagination"]["total"] == 5
    assert body["pagination"]["limit"] == 2
    assert body["pagination"]["offset"] == 2
    assert body["pagination"]["has_more"] is True
    assert len(body["items"]) == 2


def test_list_jobs_supports_sort_options(client, db):
    setup_dashboard_result(db, rows=[], total=0)

    for sort_by in ("newest", "match_score", "salary_high", "salary_low"):
        response = client.get(
            "/api/jobs",
            params={"sort_by": sort_by},
        )
        assert response.status_code == 200, sort_by


def test_list_jobs_rejects_invalid_sort(client, db):
    response = client.get(
        "/api/jobs",
        params={"sort_by": "random"},
    )

    assert response.status_code == 422


def test_list_jobs_rejects_invalid_remote_type(client, db):
    response = client.get(
        "/api/jobs",
        params={"remote_type": "anywhere"},
    )

    assert response.status_code == 422


def test_list_jobs_rejects_invalid_pagination(client, db):
    response = client.get(
        "/api/jobs",
        params={"limit": 101},
    )

    assert response.status_code == 422


def test_min_score_requires_candidate_id(client, db):
    response = client.get(
        "/api/jobs",
        params={"min_score": 70},
    )

    assert response.status_code == 422
    assert "candidate_id is required" in response.json()["detail"]


def test_list_jobs_returns_404_for_unknown_candidate(client, db):
    candidate_id = uuid4()
    db.get.return_value = None

    response = client.get(
        "/api/jobs",
        params={"candidate_id": str(candidate_id)},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


def test_list_jobs_rejects_min_score_out_of_range(client, db):
    response = client.get(
        "/api/jobs",
        params={
            "candidate_id": str(uuid4()),
            "min_score": 101,
        },
    )

    assert response.status_code == 422


# --------------------------------------------------
# Application Dashboard Summary API
# --------------------------------------------------

def test_application_summary_returns_status_and_follow_up_counts(client, db):
    candidate = make_candidate()
    db.get.return_value = candidate

    status_result = MagicMock()
    status_result.all.return_value = [
        ("saved", 3),
        ("preparing", 2),
        ("applied", 4),
        ("interviewing", 1),
        ("offer", 1),
    ]
    db.execute = AsyncMock(return_value=status_result)
    db.scalar = AsyncMock(side_effect=[2, 3, 4])

    response = client.get(
        f"/api/applications/candidate/{candidate.id}/summary"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["candidate_id"] == str(candidate.id)
    assert body["total"] == 11

    assert body["by_status"] == {
        "saved": 3,
        "preparing": 2,
        "applied": 4,
        "interviewing": 1,
        "rejected": 0,
        "offer": 1,
        "withdrawn": 0,
    }

    assert body["follow_ups"] == {
        "overdue": 2,
        "due_today": 3,
        "upcoming": 4,
    }


def test_application_summary_returns_zero_counts(client, db):
    candidate = make_candidate()
    db.get.return_value = candidate

    status_result = MagicMock()
    status_result.all.return_value = []
    db.execute = AsyncMock(return_value=status_result)
    db.scalar = AsyncMock(return_value=None)

    response = client.get(
        f"/api/applications/candidate/{candidate.id}/summary"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 0
    assert all(
        count == 0 for count in body["by_status"].values()
    )
    assert body["follow_ups"] == {
        "overdue": 0,
        "due_today": 0,
        "upcoming": 0,
    }


def test_application_summary_returns_404_for_missing_candidate(client, db):
    db.get.return_value = None

    response = client.get(
        f"/api/applications/candidate/{uuid4()}/summary"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"

    db.execute.assert_not_awaited()

def test_generate_cover_letter_saves_unapproved_document(
    client, db, monkeypatch
):
    candidate_id = uuid4()
    job_id = uuid4()
    application_id = uuid4()

    candidate = make_candidate(id=candidate_id)
    job = SimpleNamespace(
        id=job_id,
        company_id=None,
        title="Backend Developer",
        location="Remote",
        employment_type="Full-time",
        experience_level="Senior",
        description="Build backend APIs using Python and PostgreSQL.",
        is_active=True,
    )

    application = SimpleNamespace(
        id=application_id,
        candidate_id=candidate_id,
        job_id=job_id,
        status="saved",
    )

    db.get.side_effect = [candidate, job]

    # First query: find an existing application.
    # Second query: find the latest cover-letter version.
    application_result = MagicMock()
    application_result.scalar_one_or_none.return_value = application

    version_result = MagicMock()
    version_result.scalar_one_or_none.return_value = 0

    db.execute.side_effect = [application_result, version_result]

    generated_letter = (
        "Dear Hiring Team,\n\n"
        "My backend development experience aligns with this role."
    )

    async def fake_generate_text(**kwargs):
        return generated_letter

    monkeypatch.setattr(
        applications_routes,
        "generate_text",
        fake_generate_text,
    )

    response = client.post(
        "/api/applications/generate-cover-letter",
        json={
            "candidate_id": str(candidate_id),
            "job_id": str(job_id),
        },
    )

    assert response.status_code == 200
    assert response.json()["cover_letter"] == generated_letter
    assert response.json()["candidate_id"] == str(candidate_id)
    assert response.json()["job_id"] == str(job_id)

    saved_document = next(
        item
        for item in db.add.call_args_list
        if isinstance(item.args[0], ApplicationDocument)
    )
    document = saved_document.args[0]

    assert document.application_id == application_id
    assert document.document_type == "cover_letter"
    assert document.version == 1
    assert document.content_text == generated_letter
    assert document.is_approved is False

    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(document)


def test_generate_cover_letter_increments_document_version(
    client, db, monkeypatch
):
    candidate_id = uuid4()
    job_id = uuid4()
    application_id = uuid4()

    candidate = make_candidate(id=candidate_id)
    job = SimpleNamespace(
        id=job_id,
        company_id=None,
        title="Backend Developer",
        location="Remote",
        employment_type="Full-time",
        experience_level="Senior",
        description="Build backend APIs using Python and PostgreSQL.",
        is_active=True,
    )
    application = SimpleNamespace(
        id=application_id,
        candidate_id=candidate_id,
        job_id=job_id,
        status="saved",
    )

    # Simulate two requests: each loads the candidate and job.
    db.get.side_effect = [
        candidate, job,
        candidate, job,
    ]

    # Each request finds the existing application.
    application_result = MagicMock()
    application_result.scalar_one_or_none.return_value = application

    # First request sees no previous version; second sees version 1.
    version_1_result = MagicMock()
    version_1_result.scalar_one_or_none.return_value = 0

    version_2_result = MagicMock()
    version_2_result.scalar_one_or_none.return_value = 1

    db.execute.side_effect = [
        application_result,
        version_1_result,
        application_result,
        version_2_result,
    ]

    generated_letters = iter([
        "First version of the cover letter.",
        "Updated version of the cover letter.",
    ])

    async def fake_generate_text(**kwargs):
        return next(generated_letters)

    monkeypatch.setattr(
        applications_routes,
        "generate_text",
        fake_generate_text,
    )

    payload = {
        "candidate_id": str(candidate_id),
        "job_id": str(job_id),
    }

    first_response = client.post(
        "/api/applications/generate-cover-letter",
        json=payload,
    )
    second_response = client.post(
        "/api/applications/generate-cover-letter",
        json=payload,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    documents = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], ApplicationDocument)
    ]

    assert len(documents) == 2

    assert documents[0].version == 1
    assert documents[0].content_text == (
        "First version of the cover letter."
    )

    assert documents[1].version == 2
    assert documents[1].content_text == (
        "Updated version of the cover letter."
    )

    assert all(
        document.application_id == application_id
        for document in documents
    )
    assert all(
        document.is_approved is False
        for document in documents
    )

    assert db.commit.await_count == 2


def test_approve_document_does_not_mark_application_as_applied(
    client, db
):
    application_id = uuid4()
    document_id = uuid4()
    candidate_id = uuid4()

    application = SimpleNamespace(
        id=application_id,
        candidate_id=candidate_id,
        job_id=uuid4(),
        status="saved",
        applied_at=None,
    )

    document = SimpleNamespace(
        id=document_id,
        application_id=application_id,
        document_type="cover_letter",
        version=1,
        content_text="Dear Hiring Team...",
        generation_metadata={},
        is_approved=False,
        approved_at=None,
        created_at=datetime.now(timezone.utc),
    )

    # The endpoint calls db.scalar() first for the application,
    # then for the document.
    db.scalar = AsyncMock(side_effect=[application, document])

    response = client.patch(
        f"/api/applications/{application_id}/documents/"
        f"{document_id}/approve",
        params={"candidate_id": str(candidate_id)},
    )

    assert response.status_code == 200
    result = response.json()

    assert result["is_approved"] is True
    assert result["approved_at"] is not None
    assert result["document_type"] == "cover_letter"

    # Approval must not mean that the application was submitted.
    assert application.status == "saved"
    assert application.applied_at is None

    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(document)


def test_generate_cover_letter_handles_ai_provider_failure(
    client, db, monkeypatch
):
    candidate_id = uuid4()
    job_id = uuid4()

    candidate = make_candidate(id=candidate_id)
    job = SimpleNamespace(
        id=job_id,
        company_id=None,
        title="Backend Developer",
        location="Remote",
        employment_type="Full-time",
        experience_level="Senior",
        description="Build backend APIs using Python and PostgreSQL.",
        is_active=True,
    )

    db.get.side_effect = [candidate, job]

    async def failing_generate_text(**kwargs):
        from backend.app.services.ai_provider import AIProviderError

        raise AIProviderError("The AI provider is temporarily unavailable.")

    monkeypatch.setattr(
        applications_routes,
        "generate_text",
        failing_generate_text,
    )

    response = client.post(
        "/api/applications/generate-cover-letter",
        json={
            "candidate_id": str(candidate_id),
            "job_id": str(job_id),
        },
    )

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]

    # No application or document should be created after generation fails.
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


def test_update_application_to_applied_sets_applied_at(client, db):
    application_id = uuid4()
    candidate_id = uuid4()

    application = SimpleNamespace(
        id=application_id,
        candidate_id=candidate_id,
        job_id=uuid4(),
        status="saved",
        applied_at=None,
        follow_up_at=None,
        notes=None,
        application_url=None,
        submission_metadata=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.scalar = AsyncMock(return_value=application)

    response = client.patch(
        f"/api/applications/{application_id}",
        params={"candidate_id": str(candidate_id)},
        json={"status": "applied"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    assert application.applied_at is not None

    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(application)


def test_update_application_notes_preserves_status(client, db):
    application_id = uuid4()
    candidate_id = uuid4()

    application = SimpleNamespace(
        id=application_id,
        candidate_id=candidate_id,
        job_id=uuid4(),
        status="saved",
        applied_at=None,
        follow_up_at=None,
        notes=None,
        application_url=None,
        submission_metadata=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.scalar = AsyncMock(return_value=application)

    response = client.patch(
        f"/api/applications/{application_id}",
        params={"candidate_id": str(candidate_id)},
        json={"notes": "Follow up with the recruiter next week."},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    assert application.notes == "Follow up with the recruiter next week."
    assert application.applied_at is None

    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(application)
