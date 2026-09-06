import uuid
from decimal import Decimal

from src.models.account import Account
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.enums import TransactionType
from tests.fixtures.factories import (
    make_account,
    make_idempotency_key,
    make_refresh_token,
    make_transaction,
    make_user,
    quantize,
)


def test_quantize_rounds_half_up() -> None:
    assert quantize("9.995") == Decimal("10.00")
    assert quantize("10.004") == Decimal("10.00")
    assert quantize("0.005") == Decimal("0.01")


def test_make_user_defaults() -> None:
    user = make_user()
    assert isinstance(user, User)
    assert user.id is not None
    assert user.email == "user@example.com"
    assert user.password_hash == "hash-para-teste"


def test_make_account_quantizes_balance() -> None:
    user = make_user()
    account = make_account(user, balance="100.005")
    assert isinstance(account, Account)
    assert account.user_id == user.id
    assert account.balance == Decimal("100.01")


def test_make_transaction_defaults() -> None:
    user = make_user()
    account = make_account(user, balance="0")
    transaction = make_transaction(account)
    assert isinstance(transaction, Transaction)
    assert transaction.type is TransactionType.DEPOSIT
    assert transaction.amount == Decimal("10.00")
    assert transaction.counterpart_account_id is None


def test_make_transaction_with_counterpart() -> None:
    user = make_user()
    account = make_account(user)
    counterpart_id = uuid.uuid4()
    transaction = make_transaction(
        account,
        type_=TransactionType.TRANSFER,
        amount="25.50",
        counterpart_account_id=counterpart_id,
    )
    assert transaction.type is TransactionType.TRANSFER
    assert transaction.amount == Decimal("25.50")
    assert transaction.counterpart_account_id == counterpart_id


def test_make_refresh_token_defaults() -> None:
    user = make_user()
    token = make_refresh_token(user)
    assert token.revoked is False
    assert token.token_hash == "token-hash"
    assert token.expires_at is not None


def test_make_idempotency_key_defaults() -> None:
    user = make_user()
    key = make_idempotency_key(user)
    assert key.user_id == user.id
    assert key.status.value == "pending"
    assert key.fingerprint == "fingerprint-teste"
