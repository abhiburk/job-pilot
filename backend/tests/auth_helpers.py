from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.main import app


PASSWORD = "correct horse battery"


@asynccontextmanager
async def api_client(test_db, monkeypatch):
    """HTTP client against the real app and the PostgreSQL test session.

    Cookies are not marked Secure so they survive plain-HTTP test requests.
    """
    monkeypatch.setattr(settings, "session_cookie_secure", False)

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


async def register(client, email, password=PASSWORD, full_name=None):
    response = await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def csrf(session_body: dict) -> dict:
    return {"X-CSRF-Token": session_body["csrf_token"]}
