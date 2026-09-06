from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from src.models.account import Account
from src.models.idempotency import IdempotencyKey
from src.models.refresh_token import RefreshToken
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.enums import IdempotencyStatus, TransactionType


def quantize(value: str | Decimal, places: int = 2) -> Decimal:
    return Decimal(value).quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP)


def make_user(email: str = "user@example.com", password_hash: str = "hash-para-teste") -> User:
    return User(id=uuid.uuid4(), email=email, password_hash=password_hash)


def make_account(user: User, balance: str | Decimal = "0") -> Account:
    return Account(id=uuid.uuid4(), user_id=user.id, balance=quantize(balance))


def make_transaction(
    account: Account,
    type_: TransactionType = TransactionType.DEPOSIT,
    amount: str | Decimal = "10.00",
    counterpart_account_id: uuid.UUID | None = None,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        account_id=account.id,
        type=type_,
        amount=quantize(amount),
        counterpart_account_id=counterpart_account_id,
    )


def make_refresh_token(
    user: User,
    token_hash: str = "token-hash",
    expires_at: datetime | None = None,
    revoked: bool = False,
) -> RefreshToken:
    return RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at or datetime.now(UTC) + timedelta(days=7),
        revoked=revoked,
    )


def make_idempotency_key(
    user: User,
    key: str | None = None,
    status: IdempotencyStatus = IdempotencyStatus.PENDING,
) -> IdempotencyKey:
    return IdempotencyKey(
        id=uuid.uuid4(),
        user_id=user.id,
        key=key or str(uuid.uuid4()),
        fingerprint="fingerprint-teste",
        status=status,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
