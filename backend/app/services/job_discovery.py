"""Source-independent job discovery.

Runs one DiscoveryQuery against every enabled (or selected) provider,
respects each provider's request-frequency terms, and stores the results
through the shared ingestion path. Each attempt is recorded in agent_runs
(run_type "job_discovery:<source key>") so limits survive restarts.
"""

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import AgentRun
from backend.app.services.job_ingestion import save_normalized_jobs
from backend.app.services.job_sources import (
    DiscoveryQuery,
    JobSource,
    enabled_sources,
    get_source,
    is_enabled,
)


logger = logging.getLogger(__name__)

RUN_TYPE_PREFIX = "job_discovery:"
# Runs that actually contacted (or are contacting) the provider.
ATTEMPT_STATUSES = ("running", "succeeded", "failed")


def run_type(source: JobSource) -> str:
    return f"{RUN_TYPE_PREFIX}{source.key}"


@dataclass
class SourceResult:
    source: str
    label: str
    status: str  # succeeded | failed | skipped
    fetched: int = 0
    created: int = 0
    skipped: int = 0
    message: str | None = None
    ignored_filters: list[str] = field(default_factory=list)
    next_available_at: datetime | None = None


class UnknownSourceError(ValueError):
    pass


def select_sources(keys: list[str] | None) -> list[JobSource]:
    if not keys:
        return enabled_sources()

    selected = []
    for key in dict.fromkeys(keys):
        source = get_source(key)
        if source is None or not is_enabled(source):
            raise UnknownSourceError(f"Unknown or disabled job source: {key}")
        selected.append(source)
    return selected


async def last_attempt_at(db: AsyncSession, source: JobSource) -> datetime | None:
    value = await db.scalar(
        select(func.max(AgentRun.started_at)).where(
            AgentRun.run_type == run_type(source),
            AgentRun.status.in_(ATTEMPT_STATUSES),
        )
    )
    if value is not None and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


async def next_available_at(db: AsyncSession, source: JobSource) -> datetime | None:
    """When the provider's terms allow the next request, or None if now."""
    if source.min_interval is None:
        return None
    last = await last_attempt_at(db, source)
    if last is None:
        return None
    available = last + source.min_interval
    return available if available > datetime.now(timezone.utc) else None


async def latest_runs(db: AsyncSession) -> dict[str, AgentRun]:
    """Most recent attempt per source key."""
    result = await db.execute(
        select(AgentRun)
        .where(
            AgentRun.run_type.startswith(RUN_TYPE_PREFIX),
            AgentRun.status.in_(ATTEMPT_STATUSES),
        )
        .order_by(AgentRun.started_at.desc())
    )
    latest: dict[str, AgentRun] = {}
    for run in result.scalars().all():
        latest.setdefault(run.run_type.removeprefix(RUN_TYPE_PREFIX), run)
    return latest


def _interval_text(interval: timedelta) -> str:
    minutes = int(interval.total_seconds() // 60)
    amount, unit = (minutes // 60, "hour") if minutes % 60 == 0 else (minutes, "minute")
    return f"{amount} {unit}" if amount == 1 else f"{amount} {unit}s"


async def _fetch(source: JobSource, query: DiscoveryQuery):
    try:
        return await source.fetch(query), None
    except Exception as exc:  # provider errors must not stop other sources
        logger.warning("Job source %s fetch failed: %s", source.key, exc)
        return None, exc


async def run_discovery(
    db: AsyncSession,
    query: DiscoveryQuery,
    source_keys: list[str] | None = None,
) -> dict:
    sources = select_sources(source_keys)
    results: dict[str, SourceResult] = {}
    runnable: list[tuple[JobSource, AgentRun]] = []
    query_data = asdict(query)

    for source in sources:
        result = SourceResult(
            source=source.key,
            label=source.label,
            status="skipped",
            ignored_filters=source.ignored_filters(query),
        )
        results[source.key] = result

        reason = source.skip_reason(query)
        if reason:
            result.message = reason
            continue

        available_at = await next_available_at(db, source)
        if available_at is not None:
            result.next_available_at = available_at
            result.message = (
                f"{source.label} allows one request every "
                f"{_interval_text(source.min_interval)}."
            )
            continue

        run = AgentRun(
            run_type=run_type(source),
            status="running",
            input_data=query_data,
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        runnable.append((source, run))

    # Persist "running" rows first so concurrent requests see the attempt.
    await db.commit()

    fetched = await asyncio.gather(
        *(_fetch(source, query) for source, _ in runnable)
    )

    for (source, run), (raw_jobs, error) in zip(runnable, fetched):
        result = results[source.key]

        if error is None:
            # Some providers ignore the requested limit; apply it uniformly.
            raw_jobs = list(raw_jobs)[: query.limit]
            try:
                normalized = [
                    job for raw in raw_jobs if (job := source.normalize(raw))
                ]
                saved = await save_normalized_jobs(
                    db=db,
                    normalized_jobs=normalized,
                    source=source.key,
                    fetched_count=len(raw_jobs),
                )
                result.status = "succeeded"
                result.fetched = saved["fetched"]
                result.created = saved["created"]
                result.skipped = saved["skipped"]
            except Exception as exc:
                logger.exception("Saving jobs from %s failed", source.key)
                error = exc

        if error is not None:
            result.status = "failed"
            result.message = f"{source.label} could not provide valid results."

        run = await db.get(AgentRun, run.id) or run
        run.status = result.status
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = str(error)[:1000] if error else None
        run.output_data = {
            "fetched": result.fetched,
            "created": result.created,
            "skipped": result.skipped,
        }
        await db.commit()

    ordered = [results[source.key] for source in sources]
    return {
        "query": query_data,
        "results": [asdict(item) for item in ordered],
        "totals": {
            "fetched": sum(item.fetched for item in ordered),
            "created": sum(item.created for item in ordered),
            "skipped": sum(item.skipped for item in ordered),
            "succeeded": sum(item.status == "succeeded" for item in ordered),
            "failed": sum(item.status == "failed" for item in ordered),
        },
    }
