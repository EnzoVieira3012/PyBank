"""Fixtures de teste. Suite roda em banco proprio `*_test` — dev (`pybank`) intocado."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _test_database_url() -> str:
    base = os.environ.get("DATABASE_URL") or _load_dotenv().get("DATABASE_URL")
    if not base:
        raise RuntimeError("DATABASE_URL ausente — configure .env")
    head, sep, tail = base.rpartition("/")
    if not sep or "/" not in head:
        raise RuntimeError("DATABASE_URL sem database no path")
    db_name, _, query = tail.partition("?")
    if db_name.endswith("_test"):
        return base
    return f"{head}/{db_name}_test{('?' + query) if query else ''}"


TEST_DATABASE_URL = _test_database_url()
# Antes de qualquer import de src: engines singletons (app/database) nascem apontando o teste.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from src.database import async_session, engine
from src.main import app


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_database() -> None:
    """Cria o database `*_test` no postgres do docker, se ainda nao existir."""
    db = TEST_DATABASE_URL.rsplit("/", 1)[1].split("?")[0]
    admin_url = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"

    async def _create() -> None:
        admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with admin_engine.connect() as conn:
                exists = await conn.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db}
                )
                if not exists:
                    await conn.execute(text(f'CREATE DATABASE "{db}"'))
        finally:
            await admin_engine.dispose()

    asyncio.run(_create())


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(_ensure_test_database: None) -> None:
    """Schema real no banco de teste antes da suite.

    Subprocess: alembic usa asyncio.run proprio — no mesmo processo fecharia o
    event loop do pytest (asyncpg/Windows).
    """
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
    )


@pytest.fixture(autouse=True)
async def _clean_tables() -> None:
    """Isolamento: limpa dados antes de cada teste (DB de teste real, dev intacto)."""
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


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Suite compartilha mesmo IP no httpx.AsyncClient; sem reset, o
    login_limiter esgota em 10 tentativas e derruba todos os outros testes.
    Tambem restaura o callable de limite: testes que mutam _times (ex:
    corrida x100) nao podem vazar para os vizinhos."""
    from src.config import settings
    from src.rate_limit import login_limiter, mutation_limiter

    login_limiter.clear()
    mutation_limiter.clear()
    login_limiter._times = lambda: settings.RATE_LIMIT_LOGIN
    mutation_limiter._times = lambda: settings.RATE_LIMIT_MUTATIONS
    yield
    login_limiter.clear()
    mutation_limiter.clear()
    login_limiter._times = lambda: settings.RATE_LIMIT_LOGIN
    mutation_limiter._times = lambda: settings.RATE_LIMIT_MUTATIONS
