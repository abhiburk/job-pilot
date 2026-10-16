
import httpx

JOBICY_API_URL = "https://jobicy.com/api/v2/remote-jobs"


async def fetch_jobs(
    count: int = 20,
    tag: str | None = None,
) -> list[dict]:
    params: dict[str, str | int] = {"count": count}

    if tag:
        params["tag"] = tag

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            JOBICY_API_URL,
            params=params,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

    if data.get("success") is False:
        raise RuntimeError(data.get("error", "Jobicy API request failed"))

    jobs = data.get("jobs", [])

    if not isinstance(jobs, list):
        raise RuntimeError("Jobicy returned an invalid jobs response")

    return jobs