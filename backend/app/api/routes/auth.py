import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthContext, get_auth_context
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models import User
from backend.app.schemas.auth import (
    AccountUpdate,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    SessionResponse,
    UserRead,
)
from backend.app.services.auth import (
    authenticate_user,
    consume_password_reset_token,
    create_password_reset_token,
    create_session,
    hash_password,
    login_rate_limiter,
    normalize_email,
    revoke_all_sessions,
    verify_password,
)
from backend.app.services.email_service import send_email


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

INVALID_CREDENTIALS = "Invalid email or password"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _start_session(
    db: AsyncSession,
    user: User,
    request: Request,
    response: Response,
) -> SessionResponse:
    token, csrf_token, session = await create_session(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    await db.refresh(user)

    _set_session_cookie(response, token)
    return SessionResponse(
        user=UserRead.model_validate(user),
        csrf_token=csrf_token,
        expires_at=session.expires_at,
    )


@router.post(
    "/register",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if not settings.registration_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled",
        )

    user = User(
        email=normalize_email(payload.email),
        full_name=(payload.full_name or "").strip() or None,
        password_hash=hash_password(payload.password),
    )
    db.add(user)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc

    return await _start_session(db, user, request, response)


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    email = normalize_email(payload.email)
    keys = (f"ip:{_client_ip(request)}", f"email:{email}")

    retry_after = login_rate_limiter.retry_after(*keys)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await authenticate_user(db, email, payload.password)
    if user is None:
        login_rate_limiter.record_failure(*keys)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
        )

    login_rate_limiter.reset(f"email:{email}")
    return await _start_session(db, user, request, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Logout must work even with an expired session, so it does not use the
    # strict dependency. Revocation still requires a valid CSRF token.
    response = Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        auth = await get_auth_context(request, db)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            raise
        _clear_session_cookie(response)
        return response

    auth.session.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    _clear_session_cookie(response)
    return response


@router.get("/me", response_model=SessionResponse)
async def get_me(auth: AuthContext = Depends(get_auth_context)):
    return SessionResponse(
        user=UserRead.model_validate(auth.user),
        csrf_token=auth.session.csrf_token,
        expires_at=auth.session.expires_at,
    )


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: AccountUpdate,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    user = auth.user
    changes = payload.model_dump(exclude_unset=True)

    if "full_name" in changes:
        user.full_name = (changes["full_name"] or "").strip() or None

    new_email = changes.get("email")
    if new_email is not None and normalize_email(new_email) != user.email:
        if not payload.current_password or not verify_password(
            user.password_hash, payload.current_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to change your email",
            )
        user.email = normalize_email(new_email)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc

    await db.refresh(user)
    return user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    user = auth.user
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)

    # Sign out every other session; keep the one making the change.
    await revoke_all_sessions(db, user.id, except_session_id=auth.session.id)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Same response whether or not the account exists.
    accepted = {
        "message": "If an account exists for this email, a reset link has been sent."
    }

    email = normalize_email(payload.email)
    keys = (f"reset-ip:{_client_ip(request)}", f"reset-email:{email}")
    if login_rate_limiter.retry_after(*keys) is not None:
        return accepted
    login_rate_limiter.record_failure(*keys)

    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        return accepted

    token = await create_password_reset_token(db, user)
    await db.commit()

    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
    text_body = (
        "A password reset was requested for your JobPilot account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        f"This link expires in {settings.password_reset_ttl_minutes} minutes. "
        "If you did not request it, ignore this email."
    )

    try:
        await send_email(
            to_email=user.email,
            subject="Reset your JobPilot password",
            text_body=text_body,
        )
    except Exception:
        # Logged by the email service; do not reveal delivery state.
        logger.warning("Password reset email could not be delivered")

    return accepted


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    user = await consume_password_reset_token(db, payload.token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired",
        )

    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    await revoke_all_sessions(db, user.id)
    await db.commit()

    login_rate_limiter.reset(f"email:{user.email}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
