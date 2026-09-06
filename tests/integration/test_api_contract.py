"""Contrato da API: error handlers uniformes, status codes, health 503."""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.config import Settings
from src.main import create_app


def test_factory_aceita_settings_alternativos() -> None:
    cfg = Settings(DATABASE_URL="postgresql+asyncpg://x/y", SECRET_KEY="a" * 32, CORS_ORIGINS=[])
    app = create_app(cfg)
    assert app.title == "PyBank API"
    assert app.state.settings is cfg


def test_openapi_tags_descritos() -> None:
    app = create_app()
    paths = app.openapi()
    tags = {t["name"] for t in paths["tags"]}
    assert {"auth", "accounts", "transfers", "statements", "me"} <= tags


async def test_erro_validacao_tem_envelope_uniforme(client) -> None:
    """422 com `errors` estruturado + envelope de debug."""
    # cadastro sem email/password -> 422
    response = await client.post("/api/v1/auth/register", json={"email": "", "password": "x"})
    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "validation error"
    assert body["status_code"] == 422
    assert body["path"] == "/api/v1/auth/register"
    assert body["method"] == "POST"
    assert body["correlation_id"]
    assert isinstance(body["errors"], list)
    assert body["errors"][0]["loc"]


async def test_erro_business_tem_correlation_id(client) -> None:
    """404/409 via BusinessError herdam envelope de debug."""
    user_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "envteste@example.com", "password": "senha-forte-123"},
    )
    assert user_resp.status_code == 201
    login = await client.post(
        "/api/v1/auth/login", json={"email": "envteste@example.com", "password": "senha-forte-123"}
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid4())}

    # transferencia com conta inexistente -> 404
    response = await client.post(
        "/api/v1/transfers",
        json={"from_account_id": str(uuid4()), "to_account_id": str(uuid4()), "amount": "1.00"},
        headers=headers,
    )
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert body["correlation_id"]


async def test_health_503_quando_banco_cai() -> None:
    """Factory com engine ruim -> /health 503 com database: unreachable."""
    # engine aponta pra porta morta: falha rapido
    bad_engine = create_async_engine("postgresql+asyncpg://postgres:postgres@127.0.0.1:1/naoexiste")
    BadSession = async_sessionmaker(bad_engine, expire_on_commit=False)

    # patch da factory: substitui async_session dentro do main
    import src.main as main_mod

    original = main_mod.async_session
    main_mod.async_session = BadSession  # type: ignore[assignment]
    try:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # pular lifespan (senão try do startup explode)
            app.router.lifespan_context = asynccontextmanager(lambda _app: _noop())
            response = await ac.get("/health")
            assert response.status_code == 503
            assert response.json() == {"status": "degraded", "database": "unreachable"}
    finally:
        main_mod.async_session = original  # type: ignore[assignment]
        await bad_engine.dispose()


async def _noop():  # helper de lifespan
    yield
