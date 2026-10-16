
from io import BytesIO
from uuid import uuid4

import pytest
from docx import Document
from httpx import ASGITransport, AsyncClient

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import Candidate


def make_docx(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)

    output = BytesIO()
    document.save(output)
    return output.getvalue()


@pytest.mark.asyncio
async def test_resume_upload_success(test_db):
    candidate = Candidate(
        full_name="Resume Upload Test",
        email="resume-upload@example.com",
        salary_currency="INR",
    )
    test_db.add(candidate)
    await test_db.commit()
    await test_db.refresh(candidate)

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/candidates/{candidate.id}/resume/upload",
                files={
                    "file": (
                        "resume.docx",
                        make_docx("Python developer with FastAPI experience"),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )

        assert response.status_code == 200
        assert response.json()["characters_extracted"] > 0

        await test_db.refresh(candidate)
        assert "Python developer" in candidate.resume_text
        assert "FastAPI" in candidate.resume_text

    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_resume_upload_rejects_unsupported_file(test_db):
    candidate = Candidate(
        full_name="Invalid Resume Test",
        email="invalid-resume@example.com",
        salary_currency="INR",
    )
    test_db.add(candidate)
    await test_db.commit()
    await test_db.refresh(candidate)

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/candidates/{candidate.id}/resume/upload",
                files={
                    "file": (
                        "resume.txt",
                        b"Some resume text",
                        "text/plain",
                    )
                },
            )

        assert response.status_code == 400
        assert "PDF and DOCX" in response.json()["detail"]

    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_resume_upload_rejects_oversized_file(test_db):
    candidate = Candidate(
        full_name="Oversized Resume Test",
        email="oversized-resume@example.com",
        salary_currency="INR",
    )
    test_db.add(candidate)
    await test_db.commit()
    await test_db.refresh(candidate)

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/candidates/{candidate.id}/resume/upload",
                files={
                    "file": (
                        "resume.docx",
                        b"x" * (5 * 1024 * 1024 + 1),
                        "application/octet-stream",
                    )
                },
            )

        assert response.status_code == 413

    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_resume_upload_missing_candidate(test_db):
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/candidates/{uuid4()}/resume/upload",
                files={
                    "file": (
                        "resume.docx",
                        make_docx("Python developer"),
                        "application/octet-stream",
                    )
                },
            )

        assert response.status_code == 404

    finally:
        app.dependency_overrides.pop(get_db, None)
