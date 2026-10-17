from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from backend.app.core.config import settings
from backend.app.models.entities import (
    Candidate,
    Company,
    Job,
    JobDigestDelivery,
    JobMatch,
)
from backend.app.services.email_service import (
    escape_html,
    send_email,
)

logger = logging.getLogger(__name__)


def build_digest_email(rows: list[tuple]) -> tuple[str, str, str]:
    """Return (subject, plain text, HTML) for a candidate's digest."""

    subject = f"Your JobPilot job digest — {len(rows)} new jobs"
    text_lines = [
        "Here are your latest job matches from JobPilot.",
        "",
    ]
    html_parts = [
        "<html><body>",
        "<h2>Your latest job matches</h2>",
        "<p>Here are the new jobs matching your profile.</p>",
    ]

    for match, job, company_name in rows:
        company = company_name or "Company not specified"
        score = float(match.score or 0)
        coverage_value = getattr(match, "score_coverage", None)
        coverage = (
            float(coverage_value)
            if coverage_value is not None
            else None
        )
        location = job.location or "Location not specified"
        url = job.job_url or ""

        strengths = getattr(match, "strengths", None) or []
        gaps = getattr(match, "gaps", None) or []
        explanation = getattr(match, "explanation", None) or ""

        matched_skills = [
            item.removeprefix("Matching skill: ")
            for item in strengths
            if isinstance(item, str)
            and item.startswith("Matching skill: ")
        ]

        # Plain-text email
        text_lines.extend([
            f"{job.title} — {company}",
            f"Match score: {score:.0f}/100",
            (
                f"Data coverage: {coverage:.0f}%"
                if coverage is not None
                else "Data coverage: Not available"
            ),
            f"Location: {location}",
        ])

        if matched_skills:
            text_lines.append(
                "Matching skills: " + ", ".join(matched_skills)
            )

        if gaps:
            text_lines.append(
                "Potential gaps: "
                + "; ".join(str(gap) for gap in gaps)
            )

        if explanation:
            text_lines.append(f"Why it matches: {explanation}")

        if url.startswith(("https://", "http://")):
            text_lines.append(f"View job / Apply: {url}")

        text_lines.append("")

        # HTML email
        html_parts.append(
            "<section style='margin:20px 0;padding:16px;"
            "border:1px solid #ddd;border-radius:8px'>"
            f"<h3>{escape_html(job.title)}</h3>"
            f"<p>{escape_html(company)} · "
            f"{escape_html(location)}</p>"
            f"<p><strong>Match score: {score:.0f}/100</strong></p>"
            f"<p>Data coverage: "
            f"{f'{coverage:.0f}%' if coverage is not None else 'Not available'}"
            "</p>"
        )

        if matched_skills:
            skills_html = ", ".join(
                escape_html(skill) for skill in matched_skills
            )
            html_parts.append(
                f"<p><strong>Matching skills:</strong> {skills_html}</p>"
            )

        if gaps:
            gaps_html = "; ".join(
                escape_html(str(gap)) for gap in gaps
            )
            html_parts.append(
                f"<p><strong>Potential gaps:</strong> {gaps_html}</p>"
            )

        if explanation:
            html_parts.append(
                f"<p><strong>Why it matches:</strong> "
                f"{escape_html(explanation)}</p>"
            )

        if url.startswith(("https://", "http://")):
            html_parts.append(
                f"<p><a href='{escape_html(url)}'>View job / Apply</a></p>"
            )

        html_parts.append("</section>")

    html_parts.extend([
        "<p>You're receiving this because you have a JobPilot profile.</p>",
        "</body></html>",
    ])

    return subject, "\n".join(text_lines), "".join(html_parts)


async def send_candidate_digest(
    db: AsyncSession,
    candidate: Candidate,
) -> int:
    if not candidate.email:
        return 0

    already_sent = (
        select(JobDigestDelivery.id)
        .where(
            JobDigestDelivery.candidate_id == candidate.id,
            JobDigestDelivery.job_id == Job.id,
        )
        .exists()
    )

    query = (
        select(JobMatch, Job, Company.name)
        .join(Job, Job.id == JobMatch.job_id)
        .outerjoin(Company, Company.id == Job.company_id)
        .where(
            JobMatch.candidate_id == candidate.id,
            JobMatch.score >= settings.job_digest_min_score,
            JobMatch.score_coverage >= settings.job_digest_min_coverage,
            Job.is_active.is_(True),
            ~already_sent,
        )
        .order_by(
            JobMatch.score.desc(),
            Job.posted_at.desc().nulls_last(),
        )
        .limit(settings.job_digest_max_jobs)
    )

    result = await db.execute(query)
    rows = list(result.all())

    logger.info(
        "Job digest: candidate_id=%s has %s new jobs.",
        candidate.id,
        len(rows),
    )

    if not rows:
        return 0

    subject, text_body, html_body = build_digest_email(rows)

    # Send first. Only record delivery after SMTP confirms the send.
    await send_email(
        to_email=candidate.email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

    db.add_all([
        JobDigestDelivery(
            candidate_id=candidate.id,
            job_id=job.id,
        )
        for _, job, _ in rows
    ])

    await db.commit()
    return len(rows)


async def send_daily_job_digests(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(
        select(Candidate).where(Candidate.email.is_not(None))
    )
    candidates = list(result.scalars().all())

    sent_candidates = 0
    sent_jobs = 0
    failed_candidates = 0

    for candidate in candidates:
        try:
            count = await send_candidate_digest(db, candidate)
            if count:
                sent_candidates += 1
                sent_jobs += count
        except Exception:
            await db.rollback()
            failed_candidates += 1
            logger.exception(
                "Failed to send daily job digest for candidate_id=%s",
                candidate.id,
            )

    return {
        "candidates_checked": len(candidates),
        "candidates_emailed": sent_candidates,
        "jobs_emailed": sent_jobs,
        "failed_candidates": failed_candidates,
    }