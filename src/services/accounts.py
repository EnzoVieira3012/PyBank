from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import AccountNotFoundError, BusinessError
from src.models.account import Account
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.enums import TransactionType
from src.services.audit import registrar


async def criar_conta(session: AsyncSession, user: User) -> Account:
    account = Account(user_id=user.id)
    session.add(account)
    await session.flush()
    await session.refresh(account)
    return account


async def listar_contas(session: AsyncSession, user: User) -> list[Account]:
    result = await session.scalars(
        select(Account).where(Account.user_id == user.id).order_by(Account.created_at)
    )
    return list(result)


async def depositar(
    session: AsyncSession,
    account_id: uuid.UUID,
    amount: Decimal,
    user: User,
    ip: str | None = None,
    correlation_id: str | None = None,
) -> Account:
    """Atomic UPDATE: balance = balance + amount — nunca read-modify-write."""
    bal_before = await session.scalar(
        select(Account.balance).where(Account.id == account_id, Account.user_id == user.id)
    )
    if bal_before is None:
        raise AccountNotFoundError()

    bal_after = (
        await session.execute(
            update(Account)
            .where(Account.id == account_id, Account.user_id == user.id)
            .values(balance=Account.balance + amount)
            .returning(Account.balance)
        )
    ).scalar_one()

    session.add(Transaction(account_id=account_id, type=TransactionType.DEPOSIT, amount=amount))
    await registrar(
        session,
        action="deposit",
        user_id=user.id,
        account_id=account_id,
        before={"balance": str(bal_before)},
        after={"balance": str(bal_after)},
        ip=ip,
        correlation_id=correlation_id,
    )
    account = await session.get(Account, account_id)
    await session.refresh(account)
    return account


async def sacar(
    session: AsyncSession,
    account_id: uuid.UUID,
    amount: Decimal,
    user: User,
    ip: str | None = None,
    correlation_id: str | None = None,
) -> Account:
    """Atomic UPDATE com guarda de saldo: balance >= amount — CheckConstraint e backstop."""
    bal_before = await session.scalar(
        select(Account.balance).where(Account.id == account_id, Account.user_id == user.id)
    )
    if bal_before is None:
        raise AccountNotFoundError()

    row = (
        await session.execute(
            update(Account)
            .where(
                Account.id == account_id,
                Account.user_id == user.id,
                Account.balance >= amount,
            )
            .values(balance=Account.balance - amount)
            .returning(Account.balance)
        )
    ).first()
    if row is None:
        raise BusinessError("insufficient balance")
    bal_after = row[0]

    session.add(Transaction(account_id=account_id, type=TransactionType.WITHDRAW, amount=amount))
    await registrar(
        session,
        action="withdraw",
        user_id=user.id,
        account_id=account_id,
        before={"balance": str(bal_before)},
        after={"balance": str(bal_after)},
        ip=ip,
        correlation_id=correlation_id,
    )
    account = await session.get(Account, account_id)
    await session.refresh(account)
    return account
