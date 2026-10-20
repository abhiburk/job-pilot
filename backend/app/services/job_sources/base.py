from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from typing import Any


WORK_MODES = ("remote", "hybrid", "onsite")
FILTERS = ("keywords", "country", "work_mode")


@dataclass(frozen=True)
class DiscoveryQuery:
    """Source-independent search request.

    Each source maps what it supports and reports the rest as ignored, so
    the caller never has to know which provider understands which filter.
    """

    keywords: str | None = None
    # ISO 3166-1 alpha-2 country code, e.g. "IN".
    country: str | None = None
    work_mode: str | None = None
    # Maximum listings requested from each source.
    limit: int = 20

    def active_filters(self) -> list[str]:
        return [name for name in FILTERS if getattr(self, name)]


class JobSource(ABC):
    """A job provider that can be searched and normalized into Job rows.

    To add a provider: subclass this, implement `fetch` and `normalize`,
    and register an instance in `job_sources/__init__.py`.
    """

    #: Stable identifier stored in `jobs.source`. Never change it once used.
    key: str
    label: str
    description: str
    homepage: str
    #: Which DiscoveryQuery filters the provider applies server-side.
    supported_filters: frozenset[str] = frozenset()
    #: The provider lists remote jobs only.
    remote_only: bool = False
    #: Upper bound for `limit` accepted by the provider.
    max_limit: int = 50
    #: Minimum time between requests required by the provider's terms.
    min_interval: timedelta | None = None

    def ignored_filters(self, query: DiscoveryQuery) -> list[str]:
        ignored = [
            name
            for name in query.active_filters()
            if name not in self.supported_filters
        ]
        # A remote-only source satisfies work_mode=remote by definition.
        if self.remote_only and query.work_mode == "remote":
            ignored = [name for name in ignored if name != "work_mode"]
        return ignored

    def skip_reason(self, query: DiscoveryQuery) -> str | None:
        """Why this source cannot serve the query at all, if it cannot."""
        if self.remote_only and query.work_mode in {"hybrid", "onsite"}:
            return f"{self.label} lists remote jobs only."
        return None

    @abstractmethod
    async def fetch(self, query: DiscoveryQuery) -> list[Any]:
        """Return raw listings from the provider."""

    @abstractmethod
    def normalize(self, raw: Any) -> dict | None:
        """Map one raw listing to Job fields, or None to skip it."""

    def describe(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "homepage": self.homepage,
            "supported_filters": sorted(self.supported_filters),
            "remote_only": self.remote_only,
            "max_limit": self.max_limit,
            "min_interval_minutes": (
                int(self.min_interval.total_seconds() // 60)
                if self.min_interval
                else None
            ),
        }
