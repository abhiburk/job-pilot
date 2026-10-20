"""Cross-user isolation and authentication coverage for every private route."""

import re
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.main import app
from backend.app.models import (
    Application,
    ApplicationDocument,
    Candidate,
    CandidateSkill,
    Job,
    JobAIAnalysis,
    JobMatch,
    Skill,
)
from backend.tests.auth_helpers import api_client, register


PUBLIC_ROUTES = {
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/password-reset/request"),
    ("POST", "/api/auth/password-reset/confirm"),
}


def private_api_routes():
    # Read from the OpenAPI schema: it lists every mounted operation,
    # including those on included routers.
    for path, operations in app.openapi()["paths"].items():
        if not path.startswith("/api/"):
            continue
        for method in operations:
            method = method.upper()
            if (method, path) not in PUBLIC_ROUTES:
                yield method, path


def test_every_api_route_is_classified():
    routes = list(private_api_routes())
    # Guard against the sweep below silently testing nothing.
    assert len(routes) >= 25


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", sorted(private_api_routes()))
async def test_private_routes_require_authentication(test_db, monkeypatch, method, path):
    url = re.sub(r"\{[^}]+\}", str(uuid4()), path)

    async with api_client(test_db, monkeypatch) as client:
        response = await client.request(
            method,
            url,
            params={"candidate_id": str(uuid4())},
            json={},
        )

    assert response.status_code == 401, (method, path, response.text)


class Account:
    def __init__(self, session_body, cookie):
        self.csrf = session_body["csrf_token"]
        self.cookie = cookie
        self.candidate_id = None

    def use(self, client):
        client.cookies.clear()
        client.cookies.set(settings.session_cookie_name, self.cookie)
        return {"X-CSRF-Token": self.csrf}


async def make_account(client, email):
    client.cookies.clear()
    body = await register(client, email)
    account = Account(body, client.cookies.get(settings.session_cookie_name))

    response = await client.post(
        "/api/candidates",
        json={
            "full_name": email.split("@")[0],
            "email": f"candidate-{email}",
            "resume_text": "Python, FastAPI, PostgreSQL",
        },
        headers={"X-CSRF-Token": account.csrf},
    )
    assert response.status_code == 201, response.text
    account.candidate_id = response.json()["id"]
    return account


@pytest.mark.asyncio
async def test_user_cannot_read_or_modify_another_users_data(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        alice = await make_account(client, "alice@example.com")
        bob = await make_account(client, "bob@example.com")

        # Seed Alice's private records directly.
        job = Job(
            title="Backend Engineer",
            description="Python and FastAPI",
            job_url=f"https://example.com/{uuid4()}",
            source="test",
            source_job_id=str(uuid4()),
        )
        skill = Skill(name="Python")
        test_db.add_all([job, skill])
        await test_db.flush()

        alice_id = alice.candidate_id
        application = Application(candidate_id=alice_id, job_id=job.id, status="saved")
        test_db.add(application)
        await test_db.flush()

        document = ApplicationDocument(
            application_id=application.id,
            document_type="cover_letter",
            content_text="Alice's private letter",
        )
        candidate_skill = CandidateSkill(candidate_id=alice_id, skill_id=skill.id)
        match = JobMatch(candidate_id=alice_id, job_id=job.id, score=80)
        analysis = JobAIAnalysis(
            candidate_id=alice_id,
            job_id=job.id,
            status="completed",
            summary="Alice's private analysis",
        )
        test_db.add_all([document, candidate_skill, match, analysis])
        await test_db.commit()

        app_id, doc_id, job_id = application.id, document.id, job.id
        skill_link_id = candidate_skill.id
        bob_id = bob.candidate_id

        headers = bob.use(client)

        attempts = [
            ("GET", f"/api/candidates/{alice_id}", {}, None),
            ("PATCH", f"/api/candidates/{alice_id}", {}, {"full_name": "Hacked"}),
            ("GET", f"/api/candidates/{alice_id}/skills", {}, None),
            ("POST", f"/api/candidates/{alice_id}/skills", {}, {"name": "Go"}),
            ("PATCH", f"/api/candidates/{alice_id}/skills/{skill_link_id}", {}, {"is_primary": True}),
            ("DELETE", f"/api/candidates/{alice_id}/skills/{skill_link_id}", {}, None),
            ("GET", "/api/jobs", {"candidate_id": alice_id}, None),
            ("GET", f"/api/jobs/{job_id}", {"candidate_id": alice_id}, None),
            ("POST", f"/api/jobs/match/{alice_id}", {}, None),
            ("GET", f"/api/jobs/matches/{alice_id}", {}, None),
            ("POST", f"/api/jobs/{job_id}/analyze/{alice_id}", {}, None),
            ("GET", f"/api/jobs/{job_id}/analysis/{alice_id}", {}, None),
            ("POST", "/api/applications", {}, {"candidate_id": alice_id, "job_id": str(job_id)}),
            ("GET", f"/api/applications/candidate/{alice_id}", {}, None),
            ("GET", f"/api/applications/candidate/{alice_id}/summary", {}, None),
            ("POST", "/api/applications/generate-cover-letter", {}, {"candidate_id": alice_id, "job_id": str(job_id)}),
            ("POST", "/api/applications/tailor-resume", {}, {"candidate_id": alice_id, "job_id": str(job_id)}),
        ]

        # Application-scoped routes: with Alice's candidate ID (not owned) and
        # with Bob's own candidate ID (owned, but the application is not his).
        for candidate_id in (alice_id, bob_id):
            params = {"candidate_id": candidate_id}
            attempts += [
                ("GET", f"/api/applications/{app_id}", params, None),
                ("PATCH", f"/api/applications/{app_id}", params, {"status": "withdrawn"}),
                ("GET", f"/api/applications/{app_id}/documents", params, None),
                ("GET", f"/api/applications/{app_id}/documents/{doc_id}", params, None),
                ("PATCH", f"/api/applications/{app_id}/documents/{doc_id}/approve", params, None),
                ("DELETE", f"/api/applications/{app_id}", params, None),
            ]

        for method, url, params, body in attempts:
            response = await client.request(
                method, url, params=params, json=body, headers=headers
            )
            assert response.status_code == 404, (method, url, params, response.text)
            assert "Alice" not in response.text

        upload = await client.post(
            f"/api/candidates/{alice_id}/resume/upload",
            files={"file": ("resume.pdf", b"%PDF-1.4", "application/pdf")},
            headers=headers,
        )
        assert upload.status_code == 404

        # Bob's own listing does not include Alice's application.
        own = await client.get(f"/api/applications/candidate/{bob_id}")
        assert own.status_code == 200
        assert own.json() == []

        mine = await client.get("/api/candidates/me")
        assert mine.json()["id"] == bob_id

    # Alice's data is untouched.
    test_db.expire_all()
    candidate = await test_db.get(Candidate, alice.candidate_id)
    assert candidate.full_name == "alice"
    assert await test_db.get(Application, app_id) is not None
    stored = await test_db.get(ApplicationDocument, doc_id)
    assert stored.is_approved is False
    assert (await test_db.get(Application, app_id)).status == "saved"
    assert await test_db.get(CandidateSkill, skill_link_id) is not None


@pytest.mark.asyncio
async def test_owner_can_access_own_application_and_documents(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        alice = await make_account(client, "owner-alice@example.com")
        job = Job(
            title="Engineer",
            job_url=f"https://example.com/{uuid4()}",
            source="test",
            source_job_id=str(uuid4()),
        )
        test_db.add(job)
        await test_db.commit()

        headers = alice.use(client)
        created = await client.post(
            "/api/applications",
            json={"candidate_id": alice.candidate_id, "job_id": str(job.id)},
            headers=headers,
        )
        assert created.status_code == 201
        app_id = created.json()["id"]

        params = {"candidate_id": alice.candidate_id}
        detail = await client.get(f"/api/applications/{app_id}", params=params)
        assert detail.status_code == 200
        assert detail.json()["job_title"] == "Engineer"

        by_job = await client.get(
            f"/api/applications/candidate/{alice.candidate_id}",
            params={"job_id": str(job.id)},
        )
        assert [item["id"] for item in by_job.json()] == [app_id]

        docs = await client.get(f"/api/applications/{app_id}/documents", params=params)
        assert docs.status_code == 200
        assert docs.json() == []

        job_detail = await client.get(f"/api/jobs/{job.id}", params=params)
        assert job_detail.status_code == 200
        assert job_detail.json()["match_score"] is None

        analysis = await client.get(f"/api/jobs/{job.id}/analysis/{alice.candidate_id}")
        assert analysis.json() == {"analysis": None}


@pytest.mark.asyncio
async def test_account_owns_at_most_one_candidate(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        alice = await make_account(client, "single@example.com")
        headers = alice.use(client)

        second = await client.post(
            "/api/candidates",
            json={"full_name": "Second", "email": "second-profile@example.com"},
            headers=headers,
        )
        assert second.status_code == 409


@pytest.mark.asyncio
async def test_unowned_legacy_candidate_is_not_reachable(test_db, monkeypatch):
    legacy = Candidate(full_name="Legacy", email="legacy@example.com")
    test_db.add(legacy)
    await test_db.commit()

    async with api_client(test_db, monkeypatch) as client:
        await make_account(client, "newcomer@example.com")
        response = await client.get(f"/api/candidates/{legacy.id}")
        assert response.status_code == 404

    owners = await test_db.scalar(
        select(Candidate.user_id).where(Candidate.id == legacy.id)
    )
    assert owners is None
