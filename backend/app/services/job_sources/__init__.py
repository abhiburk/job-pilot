"""Registry of job providers.

Discovery, the API and the UI are driven by this registry, so adding a
provider means writing one `JobSource` subclass and registering it here.
Providers can be switched off with the JOB_SOURCES_DISABLED setting.
"""

from backend.app.core.config import settings
from backend.app.services.job_sources.base import DiscoveryQuery, JobSource
from backend.app.services.job_sources.providers import (
    FreeHireSource,
    JobicySource,
    RemotiveSource,
)


_REGISTRY: dict[str, JobSource] = {}


def register(source: JobSource) -> JobSource:
    if source.key in _REGISTRY:
        raise ValueError(f"Job source '{source.key}' is already registered")
    _REGISTRY[source.key] = source
    return source


def all_sources() -> list[JobSource]:
    return list(_REGISTRY.values())


def is_enabled(source: JobSource) -> bool:
    return source.key not in settings.disabled_job_sources


def enabled_sources() -> list[JobSource]:
    return [source for source in all_sources() if is_enabled(source)]


def get_source(key: str) -> JobSource | None:
    return _REGISTRY.get(key)


register(JobicySource())
register(FreeHireSource())
register(RemotiveSource())


__all__ = [
    "DiscoveryQuery",
    "JobSource",
    "all_sources",
    "enabled_sources",
    "get_source",
    "is_enabled",
    "register",
]
