import subprocess
import sys

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.database import async_session, engine
from src.main import app


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations() -> None:
    """Garante schema real (Postgres via docker) antes da suite.

    Subprocess: alembic usa asyncio.run proprio — no mesmo processo
    fecharia o event loop do pytest (asyncpg/Windows).
    """
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=__file__.rsplit("tests", 1)[0],
    )


@pytest.fixture(autouse=True)
async def _clean_tables() -> None:
    """Isolamento: limpa dados antes de cada teste (DB real, nao fake)."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE transactions, refresh_tokens, idempotency_keys, "
                "audit_logs, accounts, users RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
async def db_session():
    async with async_session() as session:
        yield session


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
