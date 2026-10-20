
import argparse
import asyncio
import logging

from sqlalchemy import select

from backend.app.core.database import AsyncSessionLocal
from backend.app.models import Candidate
from backend.app.services.job_discovery import run_discovery
from backend.app.services.job_sources import DiscoveryQuery
from backend.app.services.job_matching import match_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main(query: DiscoveryQuery) -> None:
    stats = {
        "sources_succeeded": 0,
        "sources_failed": 0,
        "sources_skipped": 0,
        "jobs_created": 0,
        "candidates_matched": 0,
        "matching_failures": 0,
    }

    async with AsyncSessionLocal() as db:
        # Every enabled source is searched; failures and rate limits are
        # reported per source and do not stop the others.
        discovery = await run_discovery(db, query)

        for item in discovery["results"]:
            stats[f"sources_{item['status']}"] += 1
            stats["jobs_created"] += item["created"]
            logger.info("%s discovery: %s", item["source"], item)

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


def parse_args() -> DiscoveryQuery:
    parser = argparse.ArgumentParser(
        description="Discover jobs from all enabled sources, then re-match candidates.",
    )
    parser.add_argument("--keywords", help="Role or skill phrase, e.g. 'backend developer'")
    parser.add_argument("--country", default="IN", help="ISO country code (default: IN)")
    parser.add_argument("--work-mode", choices=["remote", "hybrid", "onsite"])
    parser.add_argument("--limit", type=int, default=50, help="Listings per source (max 50)")
    args = parser.parse_args()

    return DiscoveryQuery(
        keywords=args.keywords,
        country=args.country.upper() if args.country else None,
        work_mode=args.work_mode,
        limit=max(1, min(args.limit, 50)),
    )


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
