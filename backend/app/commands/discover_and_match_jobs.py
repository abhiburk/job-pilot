
import asyncio
import logging

from sqlalchemy import select

from backend.app.core.database import AsyncSessionLocal
from backend.app.models import Candidate
from backend.app.services.job_ingestion import (
    discover_and_save_freehire_jobs,
    discover_and_save_jobs,
)
from backend.app.services.job_matching import match_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    stats = {
        "sources_succeeded": 0,
        "sources_failed": 0,
        "jobs_created": 0,
        "candidates_matched": 0,
        "matching_failures": 0,
    }

    async with AsyncSessionLocal() as db:
        # Run each source independently so one failure does not
        # prevent the other source from being processed.
        sources = [
            (
                "jobicy",
                lambda: discover_and_save_jobs(
                    db=db,
                    count=50,
                ),
            ),
            (
                "freehire",
                lambda: discover_and_save_freehire_jobs(
                    db=db,
                    query="Laravel PHP Python",
                    count=50,
                    country="IN",
                ),
            ),
        ]

        for source_name, discover in sources:
            try:
                result = await discover()
                stats["sources_succeeded"] += 1
                stats["jobs_created"] += result["created"]

                logger.info(
                    "%s discovery completed: %s",
                    source_name,
                    result,
                )
            except Exception:
                await db.rollback()
                stats["sources_failed"] += 1
                logger.exception(
                    "%s discovery failed",
                    source_name,
                )

        # Recalculate matches for every candidate against active jobs.
        result = await db.execute(select(Candidate))
        candidates = list(result.scalars().all())

        for candidate in candidates:
            try:
                result = await match_jobs(db, candidate.id)
                stats["candidates_matched"] += 1

                logger.info(
                    "Matching completed for candidate %s: %s",
                    candidate.id,
                    result,
                )
            except Exception:
                await db.rollback()
                stats["matching_failures"] += 1
                logger.exception(
                    "Matching failed for candidate %s",
                    candidate.id,
                )

    logger.info("Discovery pipeline summary: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
