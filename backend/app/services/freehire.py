
import httpx


BASE_URL = "https://freehire.me/api/v1"
SEARCH_URL = f"{BASE_URL}/agent/jobs/search"


async def fetch_jobs(
    query: str,
    count: int = 20,
    country: str | None = None,
    work_mode: str | None = None,
) -> list[dict]:
    params: dict[str, str | int] = {
        "q": query,
        "q_fields": "title,description,company,location",
        "description_format": "markdown",
        "limit": max(1, min(count, 100)),
        "offset": 0,
        "sort": "posted_at",
        "order": "desc",
    }

    if country:
        params["countries"] = country.upper()

    if work_mode:
        params["work_mode"] = work_mode.lower()

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(SEARCH_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    jobs = payload.get("data")

    if not isinstance(jobs, list):
        raise ValueError("Unexpected response from freehire API")

    return jobs
