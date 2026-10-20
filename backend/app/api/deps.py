import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models import Candidate, User, UserSession
from backend.app.services.auth import hash_token


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "X-CSRF-Token"


@dataclass
class AuthContext:
    user: User
    session: UserSession


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )


async def get_auth_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """Resolve the session cookie and enforce CSRF on unsafe methods."""
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise _unauthorized("Not authenticated")

    session = await db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_token(token))
    )
    if session is None or session.revoked_at is not None:
        raise _unauthorized("Not authenticated")

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise _unauthorized("Session expired")

    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Not authenticated")

    if request.method not in SAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER, "")
        if not supplied or not hmac.compare_digest(
            supplied, session.csrf_token
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing or invalid",
            )

    return AuthContext(user=user, session=session)


async def get_current_user(
    auth: AuthContext = Depends(get_auth_context),
) -> User:
    return auth.user


async def get_owned_candidate(
    db: AsyncSession,
    candidate_id: UUID,
    user: User,
) -> Candidate:
    """Load a candidate owned by the user, or 404.

    Candidates belonging to someone else are reported exactly like missing
    ones so IDs cannot be probed.
    """
    candidate = await db.get(Candidate, candidate_id)

    if candidate is None or candidate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    return candidate
