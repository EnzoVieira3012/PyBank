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
) -> Account:
    """Atomic UPDATE: balance = balance + amount — nunca read-modify-write."""
    result = await session.execute(
        update(Account)
        .where(Account.id == account_id, Account.user_id == user.id)
        .values(balance=Account.balance + amount)
        .returning(Account.balance)
    )
    if result.first() is None:
        raise AccountNotFoundError()

    session.add(Transaction(account_id=account_id, type=TransactionType.DEPOSIT, amount=amount))
    await session.flush()
    account = await session.get(Account, account_id)
    await session.refresh(account)
    return account


async def sacar(
    session: AsyncSession,
    account_id: uuid.UUID,
    amount: Decimal,
    user: User,
) -> Account:
    """Atomic UPDATE com guarda de saldo: balance >= amount — CheckConstraint e backstop."""
    result = await session.execute(
        update(Account)
        .where(
            Account.id == account_id,
            Account.user_id == user.id,
            Account.balance >= amount,
        )
        .values(balance=Account.balance - amount)
        .returning(Account.balance)
    )
    if result.first() is None:
        exists = await session.scalar(
            select(Account.id).where(Account.id == account_id, Account.user_id == user.id)
        )
        if exists is None:
            raise AccountNotFoundError()
        raise BusinessError("insufficient balance")

    session.add(Transaction(account_id=account_id, type=TransactionType.WITHDRAW, amount=amount))
    await session.flush()
    account = await session.get(Account, account_id)
    await session.refresh(account)
    return account
