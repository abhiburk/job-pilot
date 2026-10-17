# backend/app/services/job_matching.py

import re
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Candidate, CandidateSkill, Job, JobMatch, Skill
from backend.app.services.embedding_service import (
    EmbeddingService,
    cosine_similarity,
)

MODEL_VERSION = "rules-v2"

WEIGHTS = {
    "role_relevance": Decimal("0.20"),
    "skills": Decimal("0.40"),
    "experience": Decimal("0.15"),
    "preferences": Decimal("0.15"),
    "salary": Decimal("0.10"),
}

KNOWN_SKILLS = [
    "Laravel",
    "PHP",
    "Python",
    "FastAPI",
    "Django",
    "JavaScript",
    "TypeScript",
    "React",
    "Vue",
    "Node.js",
    "PostgreSQL",
    "MySQL",
    "SQL",
    "Redis",
    "RabbitMQ",
    "Docker",
    "Kubernetes",
    "AWS",
    "Git",
    "CI/CD",
    "REST API",
    "Microservices",
    "System Design",
    "LLM",
    "RAG",
    "Machine Learning",
]

SKILL_ALIASES = {
    "PostgreSQL": ["postgres", "postgresql"],
    "Node.js": ["node.js", "nodejs"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"],
    "REST API": ["rest api", "restful api", "rest apis"],
    "CI/CD": ["ci/cd", "continuous integration", "continuous delivery"],
    "Machine Learning": ["machine learning", "ml"],
    "LLM": ["llm", "large language model", "large language models"],
    "RAG": ["rag", "retrieval augmented generation"],
    "Vue": ["vue", "vue.js", "vuejs"],
    "React": ["react", "react.js", "reactjs"],
}


def normalize(value: str | None) -> str:
    """Normalize text for matching."""
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def contains_term(text: str, term: str) -> bool:
    """Match a phrase without matching it inside unrelated words."""
    if not text or not term:
        return False

    pattern = r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)"
    return re.search(pattern, text.lower()) is not None


def extract_skills(text: str | None) -> set[str]:
    """Extract known skills and their supported aliases."""
    normalized_text = normalize(text)
    found: set[str] = set()

    for skill in KNOWN_SKILLS:
        terms = SKILL_ALIASES.get(skill, [skill])

        if any(contains_term(normalized_text, term) for term in terms):
            found.add(skill)

    return found


def extract_candidate_skills(text: str | None) -> set[str]:
    """Extract candidate skills while filtering explicitly weak evidence."""
    if not text:
        return set()

    weak_evidence = re.compile(
        r"(?:"
        r"learning(?:\s+about)?|"
        r"interested\s+in|"
        r"want(?:s)?\s+to\s+learn|"
        r"beginner\s+(?:in|with)|"
        r"no\s+experience\s+with|"
        r"not\s+experienced\s+in|"
        r"not\s+skilled\s+in|"
        r"haven't\s+used|"
        r"have\s+not\s+used"
        r")\s*$",
        re.IGNORECASE,
    )

    found = set()

    for skill in KNOWN_SKILLS:
        aliases = SKILL_ALIASES.get(skill, [skill])

        for alias in aliases:
            pattern = re.compile(
                rf"(?<!\w){re.escape(alias)}(?!\w)",
                re.IGNORECASE,
            )

            for match in pattern.finditer(text):
                # Check only the text immediately before this mention.
                prefix = text[max(0, match.start() - 45):match.start()]

                if not weak_evidence.search(prefix):
                    found.add(skill)
                    break

    return found


def normalize_title(value: str | None) -> str:
    """Normalize job titles while preserving technical symbols."""
    value = normalize(value)
    value = re.sub(r"[^a-z0-9+#.]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def title_matches(preferred: str, actual: str) -> bool:
    """
    Avoid arbitrary substring matches.
    A preferred title must match the actual title or appear as a phrase.
    """
    preferred_normalized = normalize_title(preferred)
    actual_normalized = normalize_title(actual)

    if not preferred_normalized or not actual_normalized:
        return False

    return (
        preferred_normalized == actual_normalized
        or contains_term(actual_normalized, preferred_normalized)
    )


def calculate_role_relevance_score(
    job: Job,
    candidate: Candidate,
) -> Decimal:
    """
    Score job-title relevance for a software engineering candidate.
    Preferred titles and matching technical skills receive the strongest scores.
    """
    title = normalize_title(job.title)

    preferred_titles = getattr(candidate, "preferred_job_titles", None) or []
    if any(title_matches(item, title) for item in preferred_titles if item):
        return Decimal("100.00")

    candidate_profile = " ".join(
        filter(
            None,
            [
                getattr(candidate, "headline", None),
                getattr(candidate, "summary", None),
                getattr(candidate, "resume_text", None),
            ],
        )
    )

    candidate_skills = extract_skills(candidate_profile)
    title_skills = extract_skills(job.title)

    if candidate_skills & title_skills:
        return Decimal("95.00")

    high_relevance = (
        "backend developer",
        "back end developer",
        "backend engineer",
        "back end engineer",
        "php developer",
        "laravel developer",
        "full stack developer",
        "fullstack developer",
        "software engineer",
        "software developer",
        "application developer",
        "web developer",
    )

    if any(contains_term(title, term) for term in high_relevance):
        return Decimal("85.00")

    medium_relevance = (
        "technical lead",
        "solutions architect",
        "software architect",
        "platform engineer",
        "devops engineer",
    )

    if any(contains_term(title, term) for term in medium_relevance):
        return Decimal("65.00")

    lower_relevance = (
        "frontend developer",
        "front end developer",
        "ui developer",
        "qa engineer",
        "test engineer",
        "data engineer",
        "data scientist",
        "machine learning engineer",
    )

    if any(contains_term(title, term) for term in lower_relevance):
        return Decimal("35.00")

    # Generic engineering titles are not assumed to be a strong match.
    if any(
        contains_term(title, term)
        for term in ("engineer", "developer", "programmer", "architect")
    ):
        return Decimal("25.00")

    return Decimal("0.00")


def calculate_experience_score(
    candidate_years: int | float | Decimal | None,
    experience_level: str | None,
) -> Decimal | None:
    """Return experience fit, or None when the role's level is unknown."""
    if candidate_years is None or not experience_level:
        return None

    level = normalize(experience_level)

    try:
        years = Decimal(str(candidate_years))
    except Exception:
        return None

    if years < 0:
        return None

    if any(term in level for term in ("senior", "lead", "principal", "staff")):
        if years >= 5:
            return Decimal("100.00")
        if years >= 3:
            return Decimal("60.00")
        return Decimal("30.00")

    if any(term in level for term in ("mid", "intermediate", "associate")):
        if Decimal("2") <= years <= Decimal("6"):
            return Decimal("100.00")
        if years > 6:
            return Decimal("70.00")
        return Decimal("50.00")

    if any(
        term in level
        for term in ("junior", "entry", "graduate", "intern", "fresher")
    ):
        return Decimal("100.00") if years <= 3 else Decimal("75.00")

    return None


def calculate_preference_score(
    candidate: Candidate,
    job: Job,
) -> Decimal | None:
    """Compare the job with the candidate's stated title, mode, and location preferences."""
    scores: list[Decimal] = []

    preferred_titles = getattr(candidate, "preferred_job_titles", None) or []
    if preferred_titles:
        scores.append(
            Decimal("100.00")
            if any(title_matches(item, job.title or "") for item in preferred_titles)
            else Decimal("0.00")
        )

    preferred_modes = getattr(candidate, "preferred_work_modes", None) or []
    job_mode = normalize(
        getattr(job, "remote_type", None)
        or getattr(job, "work_mode", None)
    )

    if preferred_modes and job_mode:
        mode_aliases = {
            "remote": {"remote", "fully remote", "work from home", "wfh"},
            "hybrid": {"hybrid"},
            "onsite": {"onsite", "on-site", "office", "in-office"},
        }

        normalized_preferences = {normalize(item) for item in preferred_modes}
        job_mode_aliases = mode_aliases.get(job_mode, {job_mode})

        matched = any(
            preference in job_mode_aliases
            or job_mode in mode_aliases.get(preference, {preference})
            for preference in normalized_preferences
        )

        scores.append(Decimal("100.00") if matched else Decimal("0.00"))

    preferred_locations = getattr(candidate, "preferred_locations", None) or []
    job_location = normalize(getattr(job, "location", None))

    if preferred_locations and job_location:
        location_matches = any(
            normalize(location) in job_location
            for location in preferred_locations
            if normalize(location)
        )
        scores.append(
            Decimal("100.00") if location_matches else Decimal("0.00")
        )

    if not scores:
        return None

    return sum(scores, Decimal("0")) / Decimal(len(scores))


def calculate_salary_score(
    candidate_minimum: int | float | Decimal | None,
    job_minimum: int | float | Decimal | None,
    job_maximum: int | float | Decimal | None,
    candidate_currency: str | None,
    job_currency: str | None,
) -> Decimal | None:
    """
    Compare salary only when the necessary information is available.
    Currency mismatches are never silently converted.
    """
    if candidate_minimum is None:
        return None

    if job_minimum is None and job_maximum is None:
        return None

    candidate_ccy = normalize(candidate_currency)
    job_ccy = normalize(job_currency)

    if not candidate_ccy or not job_ccy or candidate_ccy != job_ccy:
        return None

    try:
        minimum = Decimal(str(candidate_minimum))
        lower = Decimal(str(job_minimum)) if job_minimum is not None else None
        upper = Decimal(str(job_maximum)) if job_maximum is not None else None
    except Exception:
        return None

    if minimum <= 0:
        return None

    if upper is not None and upper >= minimum:
        return Decimal("100.00")

    if lower is not None and lower >= minimum:
        return Decimal("100.00")

    return Decimal("0.00")


def calculate_skills_score(
    matched_skills: set[str],
    missing_skills: set[str],
    title_skills: set[str],
    description_skills: set[str],
) -> Decimal:
    """Prioritize skills explicitly mentioned in the title."""
    all_job_skills = title_skills | description_skills

    if not all_job_skills:
        return Decimal("50.00")

    title_matches = matched_skills & title_skills
    description_matches = matched_skills & description_skills

    title_score = (
        Decimal(len(title_matches)) / Decimal(len(title_skills)) * 100
        if title_skills
        else None
    )

    description_score = (
        Decimal(len(description_matches)) / Decimal(len(description_skills)) * 100
        if description_skills
        else None
    )

    if title_score is not None and description_score is not None:
        score = title_score * Decimal("0.70") + description_score * Decimal("0.30")
    elif title_score is not None:
        score = title_score
    elif description_score is not None:
        score = description_score
    else:
        return Decimal("50.00")

    # One description-only skill is weak evidence of an overall fit.
    if not title_matches and len(description_matches) <= 1:
        score = min(score, Decimal("40.00"))

    return score.quantize(Decimal("0.01"))



def weighted_score(components: dict[str, Any]) -> Decimal:
    """Calculate a score using available components and fixed weights."""
    total = Decimal("0")

    for name, weight in WEIGHTS.items():
        value = components.get(name)

        # Unknown components contribute nothing; they are not a score of 50.
        if value is None:
            continue

        normalized_value = max(
            Decimal("0"),
            min(Decimal("100"), Decimal(str(value))),
        )
        total += normalized_value * weight

    return total.quantize(Decimal("0.01"))


def calculate_score_coverage(components: dict[str, Any]) -> Decimal:
    """Return the percentage of total scoring weight that was assessed."""
    available_weight = sum(
        (
            weight
            for name, weight in WEIGHTS.items()
            if components.get(name) is not None
        ),
        Decimal("0"),
    )

    total_weight = sum(WEIGHTS.values(), Decimal("0"))

    if total_weight == 0:
        return Decimal("0.00")

    return (
        available_weight / total_weight * Decimal("100")
    ).quantize(Decimal("0.01"))


def build_match_explanation(
    score: Decimal,
    title_skills: set[str] | None = None,
    description_skills: set[str] | None = None,
    candidate_skills: set[str] | None = None,
    matched: set[str] | list[str] | None = None,
    gaps: set[str] | list[str] | None = None,
    preference_score: Decimal | None = None,
    experience_score: Decimal | None = None,
    salary_score: Decimal | None = None,
    **kwargs,
) -> str:
    title_skills = title_skills or set()
    description_skills = description_skills or set()
    candidate_skills = candidate_skills or set()
    matched = set(matched or kwargs.get("matched_skills") or [])
    gaps = set(gaps or kwargs.get("missing_skills") or kwargs.get("missing") or [])

    if score >= 80:
        label = "Strong match"
    elif score >= 60:
        label = "Good match"
    elif score >= 40:
        label = "Partial match"
    else:
        label = "Low match"

    details = [f"{label}: {score:.2f}/100."]

    if not candidate_skills:
        details.append("No recognized technical skills were identified.")
    else:
        title_matches = matched & title_skills
        description_matches = matched & description_skills

        if title_matches:
            details.append(
                "Matching title skills: " + ", ".join(sorted(title_matches)) + "."
            )

        if title_skills:
            details.append(
                f"Matched {len(title_matches)} of {len(title_skills)} "
                "recognized skills in the job title."
            )

        if description_matches:
            details.append(
                "Matching description skills: "
                + ", ".join(sorted(description_matches)) + "."
            )

        if matched:
            details.append(
                "Matching skills: " + ", ".join(sorted(matched)) + "."
            )

        if gaps:
            details.append(
                "Skills not found in your profile: "
                + ", ".join(sorted(skill.lower() for skill in gaps))
                + "."
            )

    if experience_score is None:
        details.append("Experience fit could not be fully assessed.")

    if preference_score is not None and preference_score >= 50:
        details.append("This job matches at least one saved job preference.")

    if salary_score is None:
        details.append("Salary fit could not be assessed because comparable salary data is unavailable.")

    return " ".join(details)

def build_candidate_embedding_text(candidate) -> str:
    return "\n".join(
        part.strip()
        for part in [
            getattr(candidate, "headline", None),
            getattr(candidate, "summary", None),
            getattr(candidate, "resume_text", None),
        ]
        if part and part.strip()
    )


def build_job_embedding_text(job) -> str:
    return "\n".join(
        part.strip()
        for part in [
            getattr(job, "title", None),
            getattr(job, "description", None),
            getattr(job, "experience_level", None),
            getattr(job, "location", None),
        ]
        if part and part.strip()
    )

async def match_jobs(
    db: AsyncSession,
    candidate_id,
) -> dict[str, Any]:
    """Match a candidate to active jobs and upsert the results."""
    candidate = await db.get(Candidate, candidate_id)

    if candidate is None:
        raise ValueError("Candidate not found")

    skill_query = (
        select(Skill.name)
        .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
        .where(CandidateSkill.candidate_id == candidate_id)
    )
    skill_result = await db.execute(skill_query)
    candidate_skills = set(skill_result.scalars().all())

    candidate_skills.update(
        extract_candidate_skills(
            " ".join(
                filter(
                    None,
                    [
                        candidate.headline,
                        candidate.summary,
                        candidate.resume_text,
                    ],
                )
            )
        )
    )

    profile_text = " ".join(
        filter(
            None,
            [
                getattr(candidate, "headline", None),
                getattr(candidate, "summary", None),
                getattr(candidate, "resume_text", None),
            ],
        )
    )
    candidate_skills |= extract_skills(profile_text)

    jobs_result = await db.execute(select(Job).where(Job.is_active.is_(True)))
    jobs = jobs_result.scalars().all()

    embedding_service = EmbeddingService()
    candidate_embedding = None

    try:
        candidate_text = build_candidate_embedding_text(candidate)

        if candidate_text:
            candidate_embedding = await embedding_service.get_embedding(
                db,
                candidate_text,
            )
    except Exception:
        # We'll preserve rule-based matching if Gemini is unavailable.
        # Log this exception in the production implementation.
        candidate_embedding = None

    processed = 0
    try:
        for job in jobs:
            title_skills = extract_skills(job.title)
            description_skills = extract_skills(job.description)

            job_skills = title_skills | description_skills
            matched_skills = candidate_skills & job_skills
            missing_skills = job_skills - candidate_skills

            skills_score = calculate_skills_score(
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                title_skills=title_skills,
                description_skills=description_skills,
            )

            role_score = calculate_role_relevance_score(job, candidate)

            if candidate_embedding is not None:
                job_text = build_job_embedding_text(job)

                if job_text:
                    job_embedding = await embedding_service.get_embedding(
                        db,
                        job_text,
                    )

                    similarity = cosine_similarity(
                        candidate_embedding,
                        job_embedding,
                    )

                    semantic_score = Decimal(
                        str(max(0.0, min(100.0, similarity * 100)))
                    ).quantize(Decimal("0.01"))

                    if role_score is not None:
                        role_score = (
                            Decimal(str(role_score)) * Decimal("0.75")
                            + semantic_score * Decimal("0.25")
                        ).quantize(Decimal("0.01"))

            experience_score = calculate_experience_score(
                getattr(candidate, "years_experience", None),
                getattr(job, "experience_level", None),
            )

            preference_score = calculate_preference_score(candidate, job)

            salary_score = calculate_salary_score(
                getattr(candidate, "minimum_salary", None),
                getattr(job, "salary_min", None),
                getattr(job, "salary_max", None),
                getattr(candidate, "salary_currency", None),
                getattr(job, "salary_currency", None),
            )

            components = {
                "role_relevance": role_score,
                "skills": skills_score,
                "experience": experience_score,
                "preferences": preference_score,
                "salary": salary_score,
            }

            score = weighted_score(components)
            coverage = calculate_score_coverage(components)

            # Prevent unrelated roles from receiving a high score just because
            # several components have missing data.
            if role_score == 0:
                score = min(score, Decimal("20.00"))

            score = score.quantize(Decimal("0.01"))

            strengths = [
                f"Matching skill: {skill}"
                for skill in sorted(matched_skills)
            ]

            if preference_score is not None and preference_score >= 75:
                strengths.append("Matches one or more stated job preferences.")

            explanation = build_match_explanation(
                score=score,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                experience_score=experience_score,
                preference_score=preference_score,
                salary_score=salary_score,
            )

            payload = {
                "candidate_id": candidate_id,
                "job_id": job.id,
                "score": score,
                "role_relevance_score": role_score,
                "skills_score": skills_score,
                "experience_score": experience_score,
                "preference_score": preference_score,
                "salary_score": salary_score,
                "strengths": strengths,
                "gaps": sorted(missing_skills),
                "explanation": explanation,
                "model_version": MODEL_VERSION,
                "score_coverage": coverage,
            }

            statement = insert(JobMatch).values(**payload)
            statement = statement.on_conflict_do_update(
                constraint="uq_candidate_job_match",
                set_={
                    key: getattr(statement.excluded, key)
                    for key in payload
                    if key not in {"candidate_id", "job_id"}
                },
            )

            await db.execute(statement)
            processed += 1
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await embedding_service.close()

    return {
        "candidate_id": str(candidate_id),
        "jobs_processed": processed,
        "model_version": MODEL_VERSION,
    }
