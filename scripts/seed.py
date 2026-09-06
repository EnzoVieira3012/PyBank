"""Seed para medicao do indice do extrato: 1 user, 2 contas, 10k transacoes.

Uso: python scripts/seed.py
Roda no banco de desenvolvimento (DATABASE_URL do .env). Idempotente:
re-executar apaga e recria os dados do seed."""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from src.database import async_session, engine
from src.models.account import Account
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.enums import TransactionType

SEED_EMAIL = "seed@example.com"
N = 10_000


async def main() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": SEED_EMAIL})

    async with async_session() as session:
        user = User(email=SEED_EMAIL, password_hash="x")
        session.add(user)
        await session.flush()
        acc_a = Account(user_id=user.id, balance=Decimal(0))
        acc_b = Account(user_id=user.id, balance=Decimal(0))
        session.add_all([acc_a, acc_b])
        await session.commit()
        a_id, b_id = acc_a.id, acc_b.id

    now = datetime.now(UTC)
    types = [TransactionType.DEPOSIT, TransactionType.WITHDRAW, TransactionType.TRANSFER]
    rows = [
        {
            "id": uuid.uuid4(),
            "account_id": a_id if i % 2 == 0 else b_id,
            "type": types[i % 3],
            "amount": Decimal("10.00"),
            "created_at": now - timedelta(minutes=i),
        }
        for i in range(N)
    ]
    async with engine.begin() as conn:
        await conn.execute(insert(Transaction), rows)

    print(f"seed ok: {N} transacoes em 2 contas do user {SEED_EMAIL}")


if __name__ == "__main__":
    asyncio.run(main())
