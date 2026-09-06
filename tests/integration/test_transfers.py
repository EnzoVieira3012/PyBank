import asyncio
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from src.database import async_session
from src.models.account import Account
from src.models.transaction import Transaction
from src.schemas.enums import TransactionType
from src.services import accounts as accounts_service
from src.services import transfers as transfers_service

PASSWORD = "senha-forte-123"

pytestmark = pytest.mark.asyncio


async def _register(client, email: str) -> str:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _login(client, email: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_account(client, token: str) -> str:
    resp = await client.post("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _deposit(client, token: str, account_id: str, amount: str) -> None:
    resp = await client.post(
        f"/api/v1/accounts/{account_id}/deposits",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": amount},
    )
    assert resp.status_code == 201, resp.text


async def test_transfer_ok(client, db_session) -> None:
    await _register(client, "a@example.com")
    await _register(client, "b@example.com")
    token_a = await _login(client, "a@example.com")
    token_b = await _login(client, "b@example.com")
    acc_a = await _create_account(client, token_a)
    acc_b = await _create_account(client, token_b)
    await _deposit(client, token_a, acc_a, "100.00")

    resp = await client.post(
        "/api/v1/transfers",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"from_account_id": acc_a, "to_account_id": acc_b, "amount": "40.00"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["from_account_id"] == acc_a
    assert body["to_account_id"] == acc_b
    assert body["amount"] == "40.00"

    balances = {
        acc_id: (await db_session.scalar(select(Account.balance).where(Account.id == acc_id)))
        for acc_id in (acc_a, acc_b)
    }
    assert balances[acc_a] == Decimal("60.00")
    assert balances[acc_b] == Decimal("40.00")

    txs = (
        await db_session.scalars(
            select(Transaction).where(Transaction.type == TransactionType.TRANSFER)
        )
    ).all()
    assert len(txs) == 2
    acc_a_uuid, acc_b_uuid = UUID(acc_a), UUID(acc_b)
    assert {tx.account_id for tx in txs} == {acc_a_uuid, acc_b_uuid}
    assert {tx.counterpart_account_id for tx in txs} == {acc_b_uuid, acc_a_uuid}
    assert {tx.amount for tx in txs} == {Decimal("40.00")}


async def test_transfer_same_account_409(client, db_session) -> None:
    await _register(client, "same@example.com")
    token = await _login(client, "same@example.com")
    acc = await _create_account(client, token)
    await _deposit(client, token, acc, "100.00")

    resp = await client.post(
        "/api/v1/transfers",
        headers={"Authorization": f"Bearer {token}"},
        json={"from_account_id": acc, "to_account_id": acc, "amount": "10.00"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "transfer different accounts"

    balance = await db_session.scalar(select(Account.balance).where(Account.id == acc))
    assert balance == Decimal("100.00")


async def test_transfer_insufficient_rollback(client, db_session) -> None:
    await _register(client, "poor@example.com")
    await _register(client, "rich@example.com")
    token_a = await _login(client, "poor@example.com")
    token_b = await _login(client, "rich@example.com")
    acc_a = await _create_account(client, token_a)
    acc_b = await _create_account(client, token_b)
    await _deposit(client, token_a, acc_a, "10.00")

    resp = await client.post(
        "/api/v1/transfers",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"from_account_id": acc_a, "to_account_id": acc_b, "amount": "50.00"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "insufficient balance"

    balances = {
        acc_id: await db_session.scalar(select(Account.balance).where(Account.id == acc_id))
        for acc_id in (acc_a, acc_b)
    }
    assert balances[acc_a] == Decimal("10.00")
    assert balances[acc_b] == Decimal("0.00")
    txs = (
        await db_session.scalars(
            select(Transaction).where(Transaction.type == TransactionType.TRANSFER)
        )
    ).all()
    assert txs == []


async def test_transfer_destino_inexistente_404_rollback(client, db_session) -> None:
    await _register(client, "ghost@example.com")
    token_a = await _login(client, "ghost@example.com")
    acc_a = await _create_account(client, token_a)
    await _deposit(client, token_a, acc_a, "100.00")
    fantasma = "00000000-0000-0000-0000-000000000000"

    resp = await client.post(
        "/api/v1/transfers",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"from_account_id": acc_a, "to_account_id": fantasma, "amount": "50.00"},
    )
    assert resp.status_code == 404

    balance = await db_session.scalar(select(Account.balance).where(Account.id == acc_a))
    assert balance == Decimal("100.00")


async def test_transfer_origem_de_outro_user_404(client, db_session) -> None:
    await _register(client, "owner@example.com")
    await _register(client, "intruder@example.com")
    token_a = await _login(client, "owner@example.com")
    token_b = await _login(client, "intruder@example.com")
    acc_a = await _create_account(client, token_a)
    acc_b = await _create_account(client, token_b)
    await _deposit(client, token_a, acc_a, "100.00")

    # B tenta transferir da conta de A
    resp = await client.post(
        "/api/v1/transfers",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"from_account_id": acc_a, "to_account_id": acc_b, "amount": "10.00"},
    )
    assert resp.status_code == 404

    balance = await db_session.scalar(select(Account.balance).where(Account.id == acc_a))
    assert balance == Decimal("100.00")


async def test_corrida_100_transfers_saldo_invariante(db_session) -> None:
    """50x A->B e 50x B->A em paralelo, com lock em ordem fixa:
    deadlock impossivel e soma dos saldos invariante (nada se perde)."""
    from sqlalchemy import func

    from src.models.user import User

    async with async_session() as session:
        user_a = User(email="race-a@example.com", password_hash="x")
        user_b = User(email="race-b@example.com", password_hash="x")
        session.add_all([user_a, user_b])
        await session.flush()
        user_a_id, user_b_id = user_a.id, user_b.id
        await session.commit()

    async with async_session() as session:
        ua = await session.get(User, user_a_id)
        ub = await session.get(User, user_b_id)
        acc_a = await accounts_service.criar_conta(session, ua)
        acc_b = await accounts_service.criar_conta(session, ub)
        await session.commit()
        a_id, b_id = acc_a.id, acc_b.id

    async with async_session() as session:
        ua = await session.get(User, user_a_id)
        ub = await session.get(User, user_b_id)
        await accounts_service.depositar(session, a_id, Decimal("10000.00"), ua)
        await accounts_service.depositar(session, b_id, Decimal("10000.00"), ub)
        await session.commit()

    async def _transfer(from_id, to_id, donor_id):
        async with async_session() as session:
            donor = await session.get(User, donor_id)
            await transfers_service.transferir(session, from_id, to_id, Decimal("100.00"), donor)
            await session.commit()

    tasks = [_transfer(a_id, b_id, user_a_id) for _ in range(50)] + [
        _transfer(b_id, a_id, user_b_id) for _ in range(50)
    ]
    await asyncio.gather(*tasks)

    async with async_session() as session:
        bal_a = await session.scalar(select(Account.balance).where(Account.id == a_id))
        bal_b = await session.scalar(select(Account.balance).where(Account.id == b_id))
        n_tx = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.type == TransactionType.TRANSFER)
        )
        assert bal_a + bal_b == Decimal("20000.00")
        assert bal_a >= 0 and bal_b >= 0
        assert n_tx == 200
