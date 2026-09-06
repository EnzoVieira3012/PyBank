import asyncio

import pytest
from sqlalchemy import func, select

from src.database import async_session
from src.exceptions import BusinessError
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.enums import TransactionType
from src.services import idempotency as idem_service

PASSWORD = "senha-forte-123"

pytestmark = pytest.mark.asyncio


async def _register(client, email: str) -> None:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text


async def _login(client, email: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_account(client, token: str) -> str:
    resp = await client.post("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _count_deposits(db_session) -> int:
    return await db_session.scalar(
        select(func.count(Transaction.id)).where(Transaction.type == TransactionType.DEPOSIT)
    )


async def test_replay_mesma_resposta_uma_execucao(client, db_session) -> None:
    await _register(client, "idem-replay@example.com")
    token = await _login(client, "idem-replay@example.com")
    acc = await _create_account(client, token)

    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": "chave-dep-1",
    }
    r1 = await client.post(
        f"/api/v1/accounts/{acc}/deposits", headers=headers, json={"amount": "100.00"}
    )
    r2 = await client.post(
        f"/api/v1/accounts/{acc}/deposits", headers=headers, json={"amount": "100.00"}
    )
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text
    assert r1.json() == r2.json()  # replay: resposta identica

    from src.models.account import Account

    balance = await db_session.scalar(select(Account.balance).where(Account.id == acc))
    assert balance == 100  # nao somou de novo
    assert await _count_deposits(db_session) == 1  # 1 transacao executada


async def test_key_ausente_400(client, db_session) -> None:
    await _register(client, "idem-no@example.com")
    token = await _login(client, "idem-no@example.com")
    acc = await _create_account(client, token)

    resp = await client.post(
        f"/api/v1/accounts/{acc}/deposits",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "100.00"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Idempotency-Key header required"


async def test_mesma_key_body_diferente_409(client, db_session) -> None:
    await _register(client, "idem-conf@example.com")
    token = await _login(client, "idem-conf@example.com")
    acc = await _create_account(client, token)

    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": "chave-conf",
    }
    r1 = await client.post(
        f"/api/v1/accounts/{acc}/deposits", headers=headers, json={"amount": "100.00"}
    )
    assert r1.status_code == 201

    r2 = await client.post(
        f"/api/v1/accounts/{acc}/deposits", headers=headers, json={"amount": "200.00"}
    )
    assert r2.status_code == 409
    assert r2.json()["detail"] == "idempotency key reuse with different payload"

    from src.models.account import Account

    balance = await db_session.scalar(select(Account.balance).where(Account.id == acc))
    assert balance == 100  # segundo request nao executou nada


async def test_transfer_replay(client, db_session) -> None:
    await _register(client, "idem-ta@example.com")
    await _register(client, "idem-tb@example.com")
    token_a = await _login(client, "idem-ta@example.com")
    token_b = await _login(client, "idem-tb@example.com")
    acc_a = await _create_account(client, token_a)
    acc_b = await _create_account(client, token_b)
    await client.post(
        f"/api/v1/accounts/{acc_a}/deposits",
        headers={
            "Authorization": f"Bearer {token_a}",
            "Idempotency-Key": "chave-dep-a",
        },
        json={"amount": "100.00"},
    )

    headers = {
        "Authorization": f"Bearer {token_a}",
        "Idempotency-Key": "chave-transfer-1",
    }
    payload = {"from_account_id": acc_a, "to_account_id": acc_b, "amount": "40.00"}
    r1 = await client.post("/api/v1/transfers", headers=headers, json=payload)
    r2 = await client.post("/api/v1/transfers", headers=headers, json=payload)
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201
    assert r1.json() == r2.json()

    from src.models.account import Account

    bal_a = await db_session.scalar(select(Account.balance).where(Account.id == acc_a))
    bal_b = await db_session.scalar(select(Account.balance).where(Account.id == acc_b))
    assert bal_a == 60  # debito unico
    assert bal_b == 40
    n_tx = await db_session.scalar(
        select(func.count(Transaction.id)).where(Transaction.type == TransactionType.TRANSFER)
    )
    assert n_tx == 2  # so o par do primeiro request


async def test_corrida_claim_um_so_ganha_e_replay(db_session) -> None:
    async with async_session() as session:
        user = User(email="idem-race@example.com", password_hash="x")
        session.add(user)
        await session.commit()
        uid = user.id  # commit expira o resto, capturar id dentro do with

    async def _claim():
        async with async_session() as session:
            try:
                r = await idem_service.try_claim(session, uid, "chave-corrida", "fp-x")
                await session.commit()
                return ("claimed", r.claimed)
            except BusinessError as exc:
                await session.rollback()
                return ("erro", str(exc))

    results = await asyncio.gather(_claim(), _claim())
    claimed = [r for r in results if r[0] == "claimed"]
    errors = [r for r in results if r[0] == "erro"]
    assert len(claimed) == 1  # exatamente um ganha a chave
    assert len(errors) == 1
    assert errors[0][1] == "request in progress"  # outro ve a corrida

    # ganhador completa; retry da chave -> replay da resposta gravada
    async with async_session() as session:
        await idem_service.complete(session, uid, "chave-corrida", 201, '{"ok": 1}')
        await session.commit()

    async with async_session() as session:
        r = await idem_service.try_claim(session, uid, "chave-corrida", "fp-x")
        assert r.claimed is False
        assert r.replay_status == 201
        assert r.replay_body == '{"ok": 1}'
