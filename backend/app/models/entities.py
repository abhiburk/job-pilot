
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from sqlalchemy.orm import relationship


def uuid_pk():
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


def created_at_column():
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = uuid_pk()
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    phone: Mapped[str | None] = mapped_column(String(50))
    headline: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    preferred_locations: Mapped[list | None] = mapped_column(JSONB)
    preferred_job_titles: Mapped[list | None] = mapped_column(JSONB)
    preferred_employment_types: Mapped[list | None] = mapped_column(JSONB)
    preferred_work_modes: Mapped[list | None] = mapped_column(JSONB)

    years_experience: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    minimum_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_currency: Mapped[str] = mapped_column(
        String(3), default="INR", nullable=False
    )
    remote_only: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    resume_text: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    github_url: Mapped[str | None] = mapped_column(String(500))
    portfolio_url: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Experience(Base):
    __tablename__ = "experiences"

    id: Mapped[uuid.UUID] = uuid_pk()
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    employment_type: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    achievements: Mapped[list | None] = mapped_column(JSONB)
    technologies: Mapped[list | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = created_at_column()


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    category: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_at_column()


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "skill_id", name="uq_candidate_skill"
        ),
    )
    skill = relationship("Skill")

    id: Mapped[uuid.UUID] = uuid_pk()
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    proficiency: Mapped[str | None] = mapped_column(String(50))
    years_experience: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    is_primary: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    technologies: Mapped[list | None] = mapped_column(JSONB)
    achievements: Mapped[list | None] = mapped_column(JSONB)
    project_url: Mapped[str | None] = mapped_column(String(500))
    repository_url: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_featured: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = created_at_column()


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    website: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(150))
    size_range: Mapped[str | None] = mapped_column(String(100))
    headquarters: Mapped[str | None] = mapped_column(String(255))
    careers_url: Mapped[str | None] = mapped_column(String(500))
    research_data: Mapped[dict | None] = mapped_column(JSONB)
    researched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_job_id",
            name="uq_jobs_source_source_job_id",
        ),
        Index("ix_jobs_source_posted_at", "source", "posted_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    remote_type: Mapped[str | None] = mapped_column(String(50))
    employment_type: Mapped[str | None] = mapped_column(String(50))
    experience_level: Mapped[str | None] = mapped_column(String(100))

    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_currency: Mapped[str | None] = mapped_column(String(3))

    job_url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_job_id: Mapped[str | None] = mapped_column(String(255))
    source_metadata: Mapped[dict | None] = mapped_column(JSONB)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = created_at_column()
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class JobSkill(Base):
    __tablename__ = "job_skills"
    __table_args__ = (
        UniqueConstraint("job_id", "skill_id", name="uq_job_skill"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    importance: Mapped[str | None] = mapped_column(String(50))


class JobMatch(Base):
    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "job_id", name="uq_candidate_job_match"
        ),
        Index("ix_job_matches_score", "candidate_id", "score"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    skills_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    experience_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    preference_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    strengths: Mapped[list | None] = mapped_column(JSONB)
    gaps: Mapped[list | None] = mapped_column(JSONB)
    explanation: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_at_column()
    role_relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    salary_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2)) 
    score_coverage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "job_id", name="uq_candidate_job_application"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50), default="saved", nullable=False, index=True
    )
    application_url: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    notes: Mapped[str | None] = mapped_column(Text)
    submission_metadata: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    content_text: Mapped[str | None] = mapped_column(Text)
    storage_path: Mapped[str | None] = mapped_column(String(1000))
    generation_metadata: Mapped[dict | None] = mapped_column(JSONB)
    is_approved: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = created_at_column()


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    run_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False, index=True
    )
    input_data: Mapped[dict | None] = mapped_column(JSONB)
    output_data: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_column()


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_column()


class JobFeedback(Base):
    __tablename__ = "job_feedback"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "job_id", name="uq_candidate_job_feedback"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    rating: Mapped[int | None] = mapped_column(Integer)
    is_relevant: Mapped[bool | None] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()

class JobDigestDelivery(Base):
    __tablename__ = "job_digest_deliveries"

    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "job_id",
            name="uq_job_digest_candidate_job",
        ),
    )

    # Fixed: Added Mapped[int] type annotation
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class JobAIAnalysis(Base):
    __tablename__ = "job_ai_analyses"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "job_id",
            name="uq_candidate_job_ai_analysis",
        ),
        Index(
            "ix_job_ai_analyses_candidate_status",
            "candidate_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # pending, completed, or failed
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )

    # AI assessment
    fit_score: Mapped[int | None] = mapped_column(Integer)
    recommendation: Mapped[str | None] = mapped_column(String(30))
    summary: Mapped[str | None] = mapped_column(Text)

    strengths: Mapped[list | None] = mapped_column(JSONB)
    missing_requirements: Mapped[list | None] = mapped_column(JSONB)
    evidence_gaps: Mapped[list | None] = mapped_column(JSONB)
    concerns: Mapped[list | None] = mapped_column(JSONB)

    # Track the input and model used for reproducibility
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))
    model_version: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)

    analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

class TextEmbedding(Base):
    __tablename__ = "text_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "text_hash",
            "model_name",
            name="uq_text_embedding_hash_model",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    text_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    embedding: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = created_at_column()