import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.core.config import settings
from backend.app.core.database import engine
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.candidates import router as candidates_router
from backend.app.api.routes.jobs import router as jobs_router
from backend.app.api.routes.candidate_skills import router as candidate_router
from backend.app.api.routes.resumes import router as resume_router
from backend.app.api.routes.applications import router as applications_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="JobPilot",
    description="Agentic AI job search and application assistant",
    version="0.1.0",
    # Interactive docs are a development aid only.
    docs_url="/docs" if settings.is_local else None,
    redoc_url="/redoc" if settings.is_local else None,
    openapi_url="/openapi.json" if settings.is_local else None,
)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Browsers always send Origin on cross-origin unsafe requests. Rejecting
    # unknown origins backs up SameSite cookies and the CSRF token.
    origin = request.headers.get("origin")
    if (
        request.method in UNSAFE_METHODS
        and origin is not None
        and origin.rstrip("/") not in settings.allowed_origins
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": "Origin not allowed"},
        )

    response = await call_next(request)

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    if not request.url.path.startswith(("/docs", "/redoc")):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'",
        )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    if settings.cookie_secure:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )

    return response


# Added after the security middleware so it runs first and answers
# preflight requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
    expose_headers=["Retry-After"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )


app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(candidates_router)
app.include_router(candidate_router)
app.include_router(resume_router)
app.include_router(applications_router)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/health/db")
async def database_health_check():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
        }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
