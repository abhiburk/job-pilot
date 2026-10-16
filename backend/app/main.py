from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi import FastAPI
from backend.app.api.routes import candidate_skills
from backend.app.api.routes import resumes
from backend.app.core.database import engine
from backend.app.api.routes.candidates import router as candidates_router
from backend.app.api.routes.jobs import router as jobs_router
from backend.app.api.routes.candidate_skills import router as candidate_router
from backend.app.api.routes.resumes import router as resume_router
from backend.app.api.routes.applications import router as applications_router

app = FastAPI(
    title="JobPilot",
    description="Agentic AI job search and application assistant",
    version="0.1.0",
)

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