
import httpx
import pytest

from backend.app.services import freehire


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAsyncClient:
    response = None
    request_params = None

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, params):
        type(self).request_params = params
        return type(self).response


@pytest.mark.asyncio
async def test_fetch_jobs_returns_data(monkeypatch):
    FakeAsyncClient.response = FakeResponse(
        {"data": [{"title": "Backend Engineer"}]}
    )
    monkeypatch.setattr(
        freehire.httpx, "AsyncClient", FakeAsyncClient
    )

    jobs = await freehire.fetch_jobs("Laravel", count=10)

    assert jobs == [{"title": "Backend Engineer"}]
    assert FakeAsyncClient.request_params["q"] == "Laravel"
    assert FakeAsyncClient.request_params["limit"] == 10


@pytest.mark.asyncio
async def test_fetch_jobs_applies_country_and_work_mode(monkeypatch):
    FakeAsyncClient.response = FakeResponse({"data": []})
    monkeypatch.setattr(
        freehire.httpx, "AsyncClient", FakeAsyncClient
    )

    await freehire.fetch_jobs(
        "Python",
        country="in",
        work_mode="remote",
    )

    assert FakeAsyncClient.request_params["countries"] == "IN"
    assert FakeAsyncClient.request_params["work_mode"] == "remote"


@pytest.mark.asyncio
async def test_fetch_jobs_rejects_unexpected_response(monkeypatch):
    FakeAsyncClient.response = FakeResponse({"unexpected": []})
    monkeypatch.setattr(
        freehire.httpx, "AsyncClient", FakeAsyncClient
    )

    with pytest.raises(ValueError, match="Unexpected response"):
        await freehire.fetch_jobs("Laravel")


@pytest.mark.asyncio
async def test_fetch_jobs_propagates_http_errors(monkeypatch):
    request = httpx.Request(
        "GET", "https://freehire.me/api/v1/agent/jobs/search"
    )
    response = httpx.Response(503, request=request)

    class ErrorResponse(FakeResponse):
        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "Service unavailable",
                request=request,
                response=response,
            )

    FakeAsyncClient.response = ErrorResponse({})
    monkeypatch.setattr(
        freehire.httpx, "AsyncClient", FakeAsyncClient
    )

    with pytest.raises(httpx.HTTPStatusError):
        await freehire.fetch_jobs("Laravel")
