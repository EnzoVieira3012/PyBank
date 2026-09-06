from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.models.account import Account
from src.models.audit import AuditLog

PASSWORD = "senha-forte-123"
CORRELATION = "abc-123"

pytestmark = pytest.mark.asyncio


async def _register(client, email: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers={"X-Request-ID": CORRELATION},
    )
    assert resp.status_code == 201, resp.text


async def _login(client, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"X-Request-ID": CORRELATION},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_account(client, token: str) -> str:
    resp = await client.post("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _count_logs(db_session, action: str) -> int:
    return await db_session.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == action))


async def test_register_login_gravam_audit(client, db_session) -> None:
    await _register(client, "aud-auth@example.com")
    await _login(client, "aud-auth@example.com")

    assert await _count_logs(db_session, "register") == 1
    assert await _count_logs(db_session, "login") == 1

    register_log = (
        await db_session.scalars(select(AuditLog).where(AuditLog.action == "register"))
    ).one()
    assert register_log.correlation_id == CORRELATION
    assert register_log.ip is not None
    assert register_log.account_id is None

    login_log = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "login"))).one()
    assert login_log.user_id == register_log.user_id
    assert login_log.correlation_id == CORRELATION


async def test_deposit_audit_before_after(client, db_session) -> None:
    await _register(client, "aud-dep@example.com")
    token = await _login(client, "aud-dep@example.com")
    acc = await _create_account(client, token)

    resp = await client.post(
        f"/api/v1/accounts/{acc}/deposits",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": CORRELATION,
            "Idempotency-Key": str(uuid4()),
        },
        json={"amount": "100.00"},
    )
    assert resp.status_code == 201, resp.text

    logs = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "deposit"))).all()
    assert len(logs) == 1
    log = logs[0]
    assert str(log.account_id) == acc
    assert log.before == {"balance": "0.00"}
    assert log.after == {"balance": "100.00"}
    assert log.correlation_id == CORRELATION
    assert log.ip is not None


async def test_withdraw_audit_before_after(client, db_session) -> None:
    await _register(client, "aud-wd@example.com")
    token = await _login(client, "aud-wd@example.com")
    acc = await _create_account(client, token)
    await client.post(
        f"/api/v1/accounts/{acc}/deposits",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid4())},
        json={"amount": "100.00"},
    )

    resp = await client.post(
        f"/api/v1/accounts/{acc}/withdrawals",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": CORRELATION,
            "Idempotency-Key": str(uuid4()),
        },
        json={"amount": "25.00"},
    )
    assert resp.status_code == 201, resp.text

    logs = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "withdraw"))).all()
    assert len(logs) == 1
    assert logs[0].before == {"balance": "100.00"}
    assert logs[0].after == {"balance": "75.00"}
    assert logs[0].correlation_id == CORRELATION


async def test_transfer_audit_duas_contas(client, db_session) -> None:
    await _register(client, "aud-ta@example.com")
    await _register(client, "aud-tb@example.com")
    token_a = await _login(client, "aud-ta@example.com")
    token_b = await _login(client, "aud-tb@example.com")
    acc_a = await _create_account(client, token_a)
    acc_b = await _create_account(client, token_b)
    await client.post(
        f"/api/v1/accounts/{acc_a}/deposits",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid4())},
        json={"amount": "200.00"},
    )

    resp = await client.post(
        "/api/v1/transfers",
        headers={
            "Authorization": f"Bearer {token_a}",
            "X-Request-ID": CORRELATION,
            "Idempotency-Key": str(uuid4()),
        },
        json={"from_account_id": acc_a, "to_account_id": acc_b, "amount": "80.00"},
    )
    assert resp.status_code == 201, resp.text

    logs = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "transfer"))).all()
    assert len(logs) == 1
    log = logs[0]
    assert str(log.account_id) == acc_a
    assert log.before == {"from_balance": "200.00", "to_balance": "0.00"}
    assert log.after == {"from_balance": "120.00", "to_balance": "80.00"}
    assert log.correlation_id == CORRELATION


async def test_transfer_fracassada_sem_log_orfao(client, db_session) -> None:
    await _register(client, "aud-fa@example.com")
    await _register(client, "aud-fb@example.com")
    token_a = await _login(client, "aud-fa@example.com")
    token_b = await _login(client, "aud-fb@example.com")
    acc_a = await _create_account(client, token_a)
    acc_b = await _create_account(client, token_b)
    # A deposita 10, tenta transferir 50 -> 409 (saldo insuficiente)
    await client.post(
        f"/api/v1/accounts/{acc_a}/deposits",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid4())},
        json={"amount": "10.00"},
    )

    resp = await client.post(
        "/api/v1/transfers",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid4())},
        json={"from_account_id": acc_a, "to_account_id": acc_b, "amount": "50.00"},
    )
    assert resp.status_code == 409

    # rollback unico: nem transfer, nem audit — zero orfao
    assert await _count_logs(db_session, "transfer") == 0

    bal = await db_session.scalar(select(Account.balance).where(Account.id == acc_a))
    assert bal == 10
