"""Matrix de 3 falhas que o recrutador cobra: duplicado, corrida, saldo insuficiente.

Reproduziveis, sem mocks. A corrida usa asyncio.gather + AsyncClient (cada
request com seu proprio client/session), exercita SELECT FOR UPDATE e
deve manter invariante de saldo exato.
"""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from src.database import engine
from src.main import app
from src.models.audit import AuditLog
from src.models.transaction import Transaction

pytestmark = pytest.mark.asyncio

PASSWORD = "senha-forte-123"


# --- helpers ---------------------------------------------------------------

async def _register(client: AsyncClient, email: str) -> None:
    r = await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, email: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return r.json()["access_token"]


def _auth(token: str, key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key}


async def _saldo(account_id: str) -> Decimal:
    from src.models.account import Account

    async with engine.connect() as conn:
        row = (await conn.execute(select(Account.balance).where(Account.id == account_id))).first()
    return Decimal(row[0])


# --- 1) Duplicado: mesmo Idempotency-Key replay retorna resposta identica ---

async def test_falha_duplicado_idempotency_key_replay(client) -> None:
    """POST com mesma Idempotency-Key 2x: 1 efeito, 2 respostas identicas."""
    await _register(client, "dup@example.com")
    token = await _login(client, "dup@example.com")
    conta = (
        await client.post("/api/v1/accounts", json={}, headers=_auth(token, str(uuid4())))
    ).json()

    key = str(uuid4())
    payload = {"amount": "25.00"}
    headers = _auth(token, key)

    r1 = await client.post(f"/api/v1/accounts/{conta['id']}/deposits", json=payload, headers=headers)
    r2 = await client.post(f"/api/v1/accounts/{conta['id']}/deposits", json=payload, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    # corpo replay: bytes identicos
    assert r1.content == r2.content
    # so 1 deposito efetivado
    async with engine.connect() as conn:
        total = (
            await conn.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.account_id == conta["id"], Transaction.type == "deposit"
                )
            )
        ).scalar_one()
    assert total == 1
    assert await _saldo(conta["id"]) == Decimal("25.00")


# --- 2) Corrida: 100 saques concorrentes, saldo invariante ----------------

async def test_falha_corrida_100_saques_saldo_invariante() -> None:
    """100 saques de 1.00 contra saldo 100.00, em paralelo: 100 sucessos,
    saldo final 0.00, total transacionado 100.00. Invariante: soma nunca
    diverge do saldo inicial."""
    transport = ASGITransport(app=app)
    # corrida dispara 100 mutacoes no mesmo user: elevar limite para este teste
    from src.rate_limit import mutation_limiter

    mutation_limiter._times = lambda: 1000  # type: ignore[attr-defined]
    async with AsyncClient(transport=transport, base_url="http://test") as outer:
        await _register(outer, "race@example.com")
        token = await _login(outer, "race@example.com")
        # 1 conta com saldo 100.00
        conta = (
            await outer.post("/api/v1/accounts", json={}, headers=_auth(token, str(uuid4())))
        ).json()
        await outer.post(
            f"/api/v1/accounts/{conta['id']}/deposits",
            json={"amount": "100.00"},
            headers=_auth(token, str(uuid4())),
        )
        saldo_inicial = await _saldo(conta["id"])
        assert saldo_inicial == Decimal("100.00")

    async def _one_saque() -> int:
        # cada request com client proprio (session pool independente)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                f"/api/v1/accounts/{conta['id']}/withdrawals",
                json={"amount": "1.00"},
                headers=_auth(token, str(uuid4())),
            )
            return r.status_code

    t0 = time.perf_counter()
    statuses = await asyncio.gather(*(_one_saque() for _ in range(100)))
    elapsed = time.perf_counter() - t0

    sucessos = sum(1 for s in statuses if s == 201)
    saldo_final = await _saldo(conta["id"])

    # invariante exata: 100 sucessos, saldo 0.00, sem oversell
    assert sucessos == 100, f"esperado 100 sucessos, obtido {sucessos} (statuses={set(statuses)})"
    assert saldo_final == Decimal("0.00"), f"saldo final divergente: {saldo_final}"
    # invariante global: saldo inicial == total de saques
    assert Decimal("100.00") - saldo_final == Decimal(sucessos) * Decimal("1.00")

    # persistencia: 100 transacoes de saque alem do deposito inicial
    async with engine.connect() as conn:
        n_withdraws = (
            await conn.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.account_id == conta["id"], Transaction.type == "withdraw"
                )
            )
        ).scalar_one()
    assert n_withdraws == 100

    # 5 rodadas estaveis: rodamos mais 4x e checamos invariante
    for rodada in range(4):
        # reabastecer saldo
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                f"/api/v1/accounts/{conta['id']}/deposits",
                json={"amount": "100.00"},
                headers=_auth(token, str(uuid4())),
            )
        statuses2 = await asyncio.gather(*(_one_saque() for _ in range(100)))
        assert sum(1 for s in statuses2 if s == 201) == 100
        assert await _saldo(conta["id"]) == Decimal("0.00")

    # media de tempo da 1a corrida, so para medicoes (nao assert magro)
    assert elapsed < 60, f"corrida x100 demorou {elapsed:.1f}s (>60s)"

    # expose para medicoes
    test_falha_corrida_100_saques_saldo_invariante.elapsed_seconds = elapsed  # type: ignore[attr-defined]
    mutation_limiter._times = lambda: 100  # type: ignore[attr-defined]


# --- 3) Saldo insuficiente: 409 e NADA gravado -----------------------------

async def test_falha_saldo_insuficiente_409_sem_efeito(client) -> None:
    """Saque e transferencia com saldo < valor -> 409. 0 transactions, 0 audit_logs."""
    await _register(client, "insuf@example.com")
    token = await _login(client, "insuf@example.com")
    conta = (
        await client.post("/api/v1/accounts", json={}, headers=_auth(token, str(uuid4())))
    ).json()
    # saldo 10.00
    await client.post(
        f"/api/v1/accounts/{conta['id']}/deposits",
        json={"amount": "10.00"},
        headers=_auth(token, str(uuid4())),
    )

    # baseline: conta existe + 1 deposito + 1 audit
    async with engine.connect() as conn:
        before_tx = (
            await conn.execute(
                select(func.count(Transaction.id)).where(Transaction.account_id == conta["id"])
            )
        ).scalar_one()
        before_audit = (
            await conn.execute(
                select(func.count(AuditLog.id)).where(AuditLog.account_id == conta["id"])
            )
        ).scalar_one()

    # saque de 50.00 (saldo 10.00) -> 409
    r_saque = await client.post(
        f"/api/v1/accounts/{conta['id']}/withdrawals",
        json={"amount": "50.00"},
        headers=_auth(token, str(uuid4())),
    )
    assert r_saque.status_code == 409

    # transferencia de 50.00 -> 409 (cria segunda conta pra ser mesmo-user)
    await client.post("/api/v1/accounts", json={}, headers=_auth(token, str(uuid4())))
    contas = (
        await client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
    ).json()
    origem, destino = contas[0]["id"], contas[1]["id"]

    r_transf = await client.post(
        "/api/v1/transfers",
        json={"from_account_id": origem, "to_account_id": destino, "amount": "50.00"},
        headers=_auth(token, str(uuid4())),
    )
    assert r_transf.status_code == 409

    # pos-condicao: zero transacoes novas, zero audit novo, saldo intacto
    async with engine.connect() as conn:
        after_tx = (
            await conn.execute(
                select(func.count(Transaction.id)).where(Transaction.account_id == conta["id"])
            )
        ).scalar_one()
        after_audit = (
            await conn.execute(
                select(func.count(AuditLog.id)).where(AuditLog.account_id == conta["id"])
            )
        ).scalar_one()
    assert after_tx == before_tx, f"transacao gravada indevidamente: {before_tx}->{after_tx}"
    assert after_audit == before_audit, f"audit gravado indevidamente: {before_audit}->{after_audit}"
    assert await _saldo(conta["id"]) == Decimal("10.00")