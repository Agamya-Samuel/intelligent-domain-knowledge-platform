"""
Pytest configuration — test database, fixtures, and overrides.

Uses an in-memory SQLite database for integration tests so no
external PostgreSQL instance is required during CI.

NOTE: SQLite does not support all PostgreSQL features (e.g., JSONB,
Arrays). Tests that depend on PG-specific behavior should be marked
with @pytest.mark.skipif.
"""

from __future__ import annotations

import pytest
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.main import app

# ── In-memory test database ──────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── SQLite pragmas (enable foreign keys) ────────────────────────────────


@event.listens_for(test_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def _setup_test_db():
    """Create all tables before tests, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client with no external dependencies."""
    return TestClient(app)


@pytest.fixture
def mock_user() -> dict[str, str]:
    """Return a mock user payload for auth token generation."""
    return {
        "sub": "test-user-123",
        "email": "test@example.com",
        "name": "Test User",
    }


@pytest.fixture
def auth_headers(mock_user: dict[str, str]) -> dict[str, str]:
    """Generate a valid HS256 JWT for testing (not JWE for simplicity)."""
    from jose import jwt
    from app.config import settings

    token = jwt.encode(mock_user, settings.AUTH_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_reranker(monkeypatch: pytest.MonkeyPatch):
    """Patch the reranker to avoid loading BGE-Reranker in tests."""
    import app.services.rag.reranker as reranker_module
    reranker_module._reranker_model = AsyncMock()
    reranker_module._reranker_model.predict = AsyncMock(return_value=[0.9, 0.8, 0.7])
    reranker_module._reranker_loaded = True
