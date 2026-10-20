import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models import PasswordResetToken, User, UserSession


logger = logging.getLogger(__name__)

_password_hasher = PasswordHasher()

# Verified against when the email is unknown so that response time does not
# reveal whether an account exists.
_DUMMY_HASH = _password_hasher.hash(secrets.token_urlsafe(16))


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), expected_hash)


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User | None:
    user = await db.scalar(
        select(User).where(User.email == normalize_email(email))
    )

    if user is None:
        verify_password(_DUMMY_HASH, password)
        return None

    if not verify_password(user.password_hash, password):
        return None

    if not user.is_active:
        return None

    if _password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    return user


async def create_session(
    db: AsyncSession,
    user: User,
    user_agent: str | None = None,
) -> tuple[str, str, UserSession]:
    """Create a session; returns (session token, CSRF token, row)."""
    now = datetime.now(timezone.utc)

    # Opportunistically drop this user's dead sessions.
    await db.execute(
        delete(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.expires_at < now,
        )
    )

    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)

    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(session_token),
        csrf_token=csrf_token,
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    user.last_login_at = now

    return session_token, csrf_token, session


async def revoke_all_sessions(
    db: AsyncSession,
    user_id,
    except_session_id=None,
) -> None:
    statement = update(UserSession).where(
        UserSession.user_id == user_id,
        UserSession.revoked_at.is_(None),
    )
    if except_session_id is not None:
        statement = statement.where(UserSession.id != except_session_id)

    await db.execute(statement.values(revoked_at=datetime.now(timezone.utc)))


async def create_password_reset_token(
    db: AsyncSession,
    user: User,
) -> str:
    now = datetime.now(timezone.utc)

    # Only the newest reset link is valid.
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=now
            + timedelta(minutes=settings.password_reset_ttl_minutes),
        )
    )
    return token


async def consume_password_reset_token(
    db: AsyncSession,
    token: str,
) -> User | None:
    now = datetime.now(timezone.utc)

    reset = await db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(token)
        )
    )

    if reset is None or reset.used_at is not None:
        return None

    expires_at = reset.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now:
        return None

    user = await db.get(User, reset.user_id)
    if user is None or not user.is_active:
        return None

    reset.used_at = now
    return user


class LoginRateLimiter:
    """Sliding-window counter of failed logins, keyed by IP and by email.

    State is per process. Behind several workers or instances, each keeps
    its own counters; see docs/deployment.md.
    """

    def __init__(self, max_failures: int, window_seconds: int):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        attempts = self._failures[key]
        while attempts and now - attempts[0] > self.window_seconds:
            attempts.popleft()
        if not attempts:
            self._failures.pop(key, None)
            return deque()
        return attempts

    def retry_after(self, *keys: str) -> int | None:
        """Seconds until a locked key unlocks, or None when allowed."""
        now = time.monotonic()
        waits = []
        for key in keys:
            attempts = self._prune(key, now)
            if len(attempts) >= self.max_failures:
                waits.append(int(self.window_seconds - (now - attempts[0])) + 1)
        return max(waits) if waits else None

    def record_failure(self, *keys: str) -> None:
        now = time.monotonic()
        for key in keys:
            self._failures[key].append(now)

    def reset(self, *keys: str) -> None:
        for key in keys:
            self._failures.pop(key, None)

    def clear(self) -> None:
        self._failures.clear()


login_rate_limiter = LoginRateLimiter(
    max_failures=settings.login_max_failures,
    window_seconds=settings.login_failure_window_seconds,
)
