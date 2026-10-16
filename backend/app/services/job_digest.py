from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

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
        url = job.job_url or ""

        text_lines.extend([
            f"{job.title} — {company}",
            f"Match score: {score:.0f}/100",
            f"Location: {job.location or 'Not specified'}",
            f"Apply: {url}",
            "",
        ])

        html_parts.append(
            "<section style='margin:20px 0;padding:16px;"
            "border:1px solid #ddd;border-radius:8px'>"
            f"<h3>{escape_html(job.title)}</h3>"
            f"<p>{escape_html(company)} · "
            f"{escape_html(job.location or 'Location not specified')}</p>"
            f"<p><strong>Match score: {score:.0f}/100</strong></p>"
            + (
                f"<p><a href='{escape_html(url)}'>View job / Apply</a></p>"
                if url.startswith(("https://", "http://"))
                else ""
            )
            + "</section>"
        )

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

    print(f"Job digest: {candidate.email} has {len(rows)} new jobs.")

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
            # Continue processing other candidates.
            # Configure application logging to capture the exception.

    return {
        "candidates_checked": len(candidates),
        "candidates_emailed": sent_candidates,
        "jobs_emailed": sent_jobs,
        "failed_candidates": failed_candidates,
    }