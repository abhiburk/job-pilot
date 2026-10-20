
import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from backend.app.core.database import Base
from backend.app import models  # noqa: F401
from backend.app.models import User
from backend.app.services.auth import hash_password, login_rate_limiter


@pytest_asyncio.fixture
async def test_db():
    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "Set TEST_DATABASE_URL to your dedicated jobpilot_test database."
        )

    if not database_url.endswith("/jobpilot_test"):
        raise RuntimeError(
            "Refusing to run integration tests against a database "
            "other than jobpilot_test."
        )

    engine = create_async_engine(database_url)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        async with session_factory() as session:
            yield session

    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)

        await engine.dispose()


@pytest_asyncio.fixture
async def test_user(test_db):
    """A persisted account that owns the candidates created in a test."""
    user = User(
        email="owner@example.com",
        full_name="Test Owner",
        password_hash=hash_password("correct horse battery"),
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture(autouse=True)
def reset_login_rate_limiter():
    login_rate_limiter.clear()
    yield
    login_rate_limiter.clear()
