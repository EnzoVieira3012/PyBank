"""Rate limit: 429 com Retry-After, escopo por IP (login) e por usuario (mutaveis)."""

from __future__ import annotations

from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio

PASSWORD = "senha-forte-123"


async def _register(client, email: str = "rl@example.com"):
    return await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})


async def _login(client, email: str = "rl@example.com"):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})


async def _auth(token: str):
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid4())}


@pytest.fixture(autouse=True)
def _no_op():
    """Reset agora vive em conftest.py (autouse global)."""
    yield


async def test_login_estoura_429_com_retry_after(client, monkeypatch) -> None:
    monkeypatch.setattr("src.config.settings.RATE_LIMIT_LOGIN", 3)
    await _register(client, "burst@example.com")
    # 3 tentativas com credencial invalida (todas 401) sao permitidas
    for _ in range(3):
        response = await client.post(
            "/api/v1/auth/login", json={"email": "burst@example.com", "password": "errado"}
        )
        assert response.status_code == 401
    # 4a: 429 com Retry-After em segundos
    response = await client.post(
        "/api/v1/auth/login", json={"email": "burst@example.com", "password": "errado"}
    )
    assert response.status_code == 429
    retry_after = int(response.headers["Retry-After"])
    assert 1 <= retry_after <= 61
    assert response.json() == {"detail": "rate limit exceeded"}


async def test_mutacao_429_por_usuario_nao_por_ip(client, monkeypatch) -> None:
    """Limite por usuario autenticado: A e B compartilham o mesmo IP (teste)
    mas tem contadores independentes."""
    monkeypatch.setattr("src.config.settings.RATE_LIMIT_MUTATIONS", 2)

    await _register(client, "a@example.com")
    await _register(client, "b@example.com")
    tok_a = (await _login(client, "a@example.com")).json()["access_token"]
    tok_b = (await _login(client, "b@example.com")).json()["access_token"]
    conta_a = (
        await client.post("/api/v1/accounts", json={}, headers=await _auth(tok_a))
    ).json()
    conta_b = (
        await client.post("/api/v1/accounts", json={}, headers=await _auth(tok_b))
    ).json()

    # A: 2 deps (limite) + 3o deve 429
    for _ in range(2):
        assert (
            await client.post(
                f"/api/v1/accounts/{conta_a['id']}/deposits",
                json={"amount": "1.00"},
                headers=await _auth(tok_a),
            )
        ).status_code == 201
    r = await client.post(
        f"/api/v1/accounts/{conta_a['id']}/deposits",
        json={"amount": "1.00"},
        headers=await _auth(tok_a),
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers

    # B ainda pode: contador e por usuario, nao por IP
    r = await client.post(
        f"/api/v1/accounts/{conta_b['id']}/deposits",
        json={"amount": "1.00"},
        headers=await _auth(tok_b),
    )
    assert r.status_code == 201


async def test_health_ignora_rate_limit(client) -> None:
    """Health check nao passa por /api/v1 e nao tem Depends de auth nem limit."""
    response = await client.get("/health")
    assert response.status_code == 200


async def test_headers_seguranca_presentes(client) -> None:
    response = await client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"