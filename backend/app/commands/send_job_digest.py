import asyncio
import logging

from backend.app.core.database import AsyncSessionLocal
from backend.app.services.job_digest import send_daily_job_digests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        stats = await send_daily_job_digests(db)

    logger.info("Daily job digest completed: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())