import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.schemas.account import AccountCreate, AccountOut
from src.schemas.enums import TransactionType
from src.schemas.transaction import TransactionOut
from src.schemas.user import UserCreate, UserOut


def test_user_create_valid() -> None:
    user = UserCreate(email="enzo@example.com", password="senha-forte-123")
    assert user.email == "enzo@example.com"


def test_user_create_invalid_email() -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="nao-e-email", password="senha-forte-123")


def test_user_create_password_short() -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="enzo@example.com", password="curta")


def test_account_create_negative_balance_rejected() -> None:
    with pytest.raises(ValidationError):
        AccountCreate(user_id=uuid.uuid4(), initial_balance=Decimal("-1.00"))


def test_account_create_too_many_decimals_rejected() -> None:
    with pytest.raises(ValidationError):
        AccountCreate(user_id=uuid.uuid4(), initial_balance=Decimal("10.999"))


def test_user_out_from_attributes() -> None:
    user = UserOut(
        id=uuid.uuid4(),
        email="enzo@example.com",
        created_at="2026-09-06T10:00:00Z",
    )
    assert str(user.email) == "enzo@example.com"


def test_account_out_balance_decimal() -> None:
    account = AccountOut(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        balance=Decimal("1234.50"),
        created_at="2026-09-06T10:00:00Z",
    )
    assert account.balance == Decimal("1234.50")


def test_transaction_out_enum_value() -> None:
    transaction = TransactionOut(
        id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        type="deposit",
        amount=Decimal("50.00"),
        counterpart_account_id=None,
        created_at="2026-09-06T10:00:00Z",
    )
    assert transaction.type is TransactionType.DEPOSIT


def test_transaction_out_invalid_type_rejected() -> None:
    with pytest.raises(ValidationError):
        TransactionOut(
            id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            type="pix",
            amount=Decimal("50.00"),
            counterpart_account_id=None,
            created_at="2026-09-06T10:00:00Z",
        )
