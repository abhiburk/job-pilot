from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.models import User, UserSession
from backend.app.services.auth import hash_token
from backend.tests.auth_helpers import PASSWORD, api_client, csrf, register


@pytest.mark.asyncio
async def test_register_creates_session_and_hashes_password(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        body = await register(client, "New.User@Example.com", full_name="New User")

        assert body["user"]["email"] == "new.user@example.com"
        assert body["csrf_token"]
        assert settings.session_cookie_name in client.cookies

        me = await client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["email"] == "new.user@example.com"
        assert me.json()["csrf_token"] == body["csrf_token"]

    user = await test_db.scalar(select(User).where(User.email == "new.user@example.com"))
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2")

    # Only a digest of the session token is stored.
    raw_token = client.cookies.get(settings.session_cookie_name)
    session = await test_db.scalar(select(UserSession).where(UserSession.user_id == user.id))
    assert session.token_hash == hash_token(raw_token)
    assert session.token_hash != raw_token


@pytest.mark.asyncio
async def test_session_cookie_flags(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        monkeypatch.setattr(settings, "session_cookie_secure", True)
        response = await client.post(
            "/api/auth/register",
            json={"email": "flags@example.com", "password": PASSWORD},
        )

    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email_and_weak_password(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        await register(client, "dup@example.com")

        duplicate = await client.post(
            "/api/auth/register",
            json={"email": "DUP@example.com", "password": PASSWORD},
        )
        assert duplicate.status_code == 409

        weak = await client.post(
            "/api/auth/register",
            json={"email": "weak@example.com", "password": "short"},
        )
        assert weak.status_code == 422

        bad_email = await client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": PASSWORD},
        )
        assert bad_email.status_code == 422


@pytest.mark.asyncio
async def test_registration_can_be_disabled(test_db, monkeypatch):
    monkeypatch.setattr(settings, "registration_enabled", False)
    async with api_client(test_db, monkeypatch) as client:
        response = await client.post(
            "/api/auth/register",
            json={"email": "closed@example.com", "password": PASSWORD},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_login_and_invalid_credentials(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        await register(client, "login@example.com")
        client.cookies.clear()

        wrong = await client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": "wrong password!"},
        )
        unknown = await client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": PASSWORD},
        )
        # Same status and message whether the account exists or not.
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json() == {"detail": "Invalid email or password"}
        assert settings.session_cookie_name not in client.cookies

        ok = await client.post(
            "/api/auth/login",
            json={"email": "LOGIN@example.com", "password": PASSWORD},
        )
        assert ok.status_code == 200
        assert settings.session_cookie_name in client.cookies
        assert (await client.get("/api/auth/me")).status_code == 200


@pytest.mark.asyncio
async def test_inactive_user_cannot_log_in(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        await register(client, "inactive@example.com")
        user = await test_db.scalar(select(User).where(User.email == "inactive@example.com"))
        user.is_active = False
        await test_db.commit()

        assert (await client.get("/api/auth/me")).status_code == 401

        response = await client.post(
            "/api/auth/login",
            json={"email": "inactive@example.com", "password": PASSWORD},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_session(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        body = await register(client, "logout@example.com")
        old_cookie = client.cookies.get(settings.session_cookie_name)

        # Logout is a state change and needs the CSRF token.
        assert (await client.post("/api/auth/logout")).status_code == 403

        response = await client.post("/api/auth/logout", headers=csrf(body))
        assert response.status_code == 204
        assert (await client.get("/api/auth/me")).status_code == 401

        # Replaying the old cookie does not work either.
        client.cookies.set(settings.session_cookie_name, old_cookie)
        assert (await client.get("/api/auth/me")).status_code == 401

        # Logging out without a valid session still clears the cookie.
        client.cookies.clear()
        assert (await client.post("/api/auth/logout")).status_code == 204


@pytest.mark.asyncio
async def test_expired_session_is_rejected(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        await register(client, "expiry@example.com")

        session = await test_db.scalar(select(UserSession))
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await test_db.commit()

        response = await client.get("/api/auth/me")
        assert response.status_code == 401
        assert response.json()["detail"] == "Session expired"

        assert (await client.get("/api/candidates/me")).status_code == 401


@pytest.mark.asyncio
async def test_forged_session_cookie_is_rejected(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        client.cookies.set(settings.session_cookie_name, "forged-token-value")
        assert (await client.get("/api/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_unsafe_requests_require_csrf_token(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        body = await register(client, "csrf@example.com")
        payload = {"full_name": "CSRF Test", "email": "csrf-candidate@example.com"}

        missing = await client.post("/api/candidates", json=payload)
        assert missing.status_code == 403

        wrong = await client.post(
            "/api/candidates",
            json=payload,
            headers={"X-CSRF-Token": "not-the-token"},
        )
        assert wrong.status_code == 403

        ok = await client.post("/api/candidates", json=payload, headers=csrf(body))
        assert ok.status_code == 201


@pytest.mark.asyncio
async def test_unknown_origin_is_rejected_for_unsafe_methods(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": "x@example.com", "password": PASSWORD},
            headers={"Origin": "https://evil.example"},
        )
        assert response.status_code == 403

        allowed_origin = settings.allowed_origins[0]
        allowed = await client.post(
            "/api/auth/login",
            json={"email": "x@example.com", "password": PASSWORD},
            headers={"Origin": allowed_origin},
        )
        assert allowed.status_code == 401
        assert allowed.headers["access-control-allow-origin"] == allowed_origin
        assert allowed.headers["access-control-allow-credentials"] == "true"


@pytest.mark.asyncio
async def test_cors_preflight_does_not_allow_unknown_origin(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        response = await client.options(
            "/api/candidates",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_security_headers_present(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        response = await client.get("/api/auth/me")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


@pytest.mark.asyncio
async def test_repeated_failed_logins_are_throttled(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        await register(client, "brute@example.com")
        client.cookies.clear()

        for _ in range(settings.login_max_failures):
            response = await client.post(
                "/api/auth/login",
                json={"email": "brute@example.com", "password": "wrong password!"},
            )
            assert response.status_code == 401

        # Even the correct password is refused while locked.
        locked = await client.post(
            "/api/auth/login",
            json={"email": "brute@example.com", "password": PASSWORD},
        )
        assert locked.status_code == 429
        assert int(locked.headers["retry-after"]) > 0
        assert settings.session_cookie_name not in client.cookies


@pytest.mark.asyncio
async def test_change_password_signs_out_other_sessions(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        await register(client, "change@example.com")
        client.cookies.clear()

        first = await client.post(
            "/api/auth/login",
            json={"email": "change@example.com", "password": PASSWORD},
        )
        first_cookie = client.cookies.get(settings.session_cookie_name)
        client.cookies.clear()

        second = await client.post(
            "/api/auth/login",
            json={"email": "change@example.com", "password": PASSWORD},
        )

        wrong = await client.post(
            "/api/auth/password",
            json={"current_password": "nope", "new_password": "a new long password"},
            headers=csrf(second.json()),
        )
        assert wrong.status_code == 400

        changed = await client.post(
            "/api/auth/password",
            json={"current_password": PASSWORD, "new_password": "a new long password"},
            headers=csrf(second.json()),
        )
        assert changed.status_code == 204
        assert (await client.get("/api/auth/me")).status_code == 200

        client.cookies.set(settings.session_cookie_name, first_cookie)
        assert first.status_code == 200
        assert (await client.get("/api/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_update_account_requires_password_for_email_change(test_db, monkeypatch):
    async with api_client(test_db, monkeypatch) as client:
        body = await register(client, "account@example.com")

        renamed = await client.patch(
            "/api/auth/me", json={"full_name": "Renamed"}, headers=csrf(body)
        )
        assert renamed.status_code == 200
        assert renamed.json()["full_name"] == "Renamed"

        no_password = await client.patch(
            "/api/auth/me", json={"email": "moved@example.com"}, headers=csrf(body)
        )
        assert no_password.status_code == 400

        moved = await client.patch(
            "/api/auth/me",
            json={"email": "moved@example.com", "current_password": PASSWORD},
            headers=csrf(body),
        )
        assert moved.status_code == 200
        assert moved.json()["email"] == "moved@example.com"


@pytest.mark.asyncio
async def test_password_reset_flow(test_db, monkeypatch):
    sent = AsyncMock()

    async with api_client(test_db, monkeypatch) as client:
        await register(client, "reset@example.com")
        client.cookies.clear()

        with patch("backend.app.api.routes.auth.send_email", sent):
            unknown = await client.post(
                "/api/auth/password-reset/request",
                json={"email": "nobody@example.com"},
            )
            known = await client.post(
                "/api/auth/password-reset/request",
                json={"email": "reset@example.com"},
            )

        # No account enumeration: identical responses.
        assert unknown.status_code == known.status_code == 202
        assert unknown.json() == known.json()
        sent.assert_awaited_once()

        email_body = sent.await_args.kwargs["text_body"]
        token = email_body.split("token=")[1].split()[0]

        bad = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": "x" * 40, "new_password": "brand new password"},
        )
        assert bad.status_code == 400

        ok = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": token, "new_password": "brand new password"},
        )
        assert ok.status_code == 204

        reused = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": token, "new_password": "another new password"},
        )
        assert reused.status_code == 400

        old = await client.post(
            "/api/auth/login",
            json={"email": "reset@example.com", "password": PASSWORD},
        )
        assert old.status_code == 401

        new = await client.post(
            "/api/auth/login",
            json={"email": "reset@example.com", "password": "brand new password"},
        )
        assert new.status_code == 200


@pytest.mark.asyncio
async def test_expired_reset_token_is_rejected(test_db, monkeypatch):
    from backend.app.models import PasswordResetToken

    sent = AsyncMock()
    async with api_client(test_db, monkeypatch) as client:
        await register(client, "expired-reset@example.com")

        with patch("backend.app.api.routes.auth.send_email", sent):
            await client.post(
                "/api/auth/password-reset/request",
                json={"email": "expired-reset@example.com"},
            )
        token = sent.await_args.kwargs["text_body"].split("token=")[1].split()[0]

        reset = await test_db.scalar(select(PasswordResetToken))
        reset.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await test_db.commit()

        response = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": token, "new_password": "brand new password"},
        )
        assert response.status_code == 400
