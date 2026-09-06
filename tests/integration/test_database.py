from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.account import Account
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.enums import TransactionType
from tests.fixtures.factories import make_account, make_transaction, make_user

pytestmark = pytest.mark.asyncio


async def test_create_and_fetch_user(db_session) -> None:
    user = make_user(email="db@example.com")
    db_session.add(user)
    await db_session.commit()

    fetched = await db_session.get(User, user.id)
    assert fetched is not None
    assert fetched.email == "db@example.com"
    assert fetched.created_at is not None


async def test_create_account_with_balance(db_session) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()

    account = make_account(user, balance="100.50")
    db_session.add(account)
    await db_session.commit()

    fetched = await db_session.get(Account, account.id)
    assert fetched is not None
    assert fetched.balance == Decimal("100.50")
    assert fetched.user_id == user.id


async def test_insert_transaction_with_enum(db_session) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    account = make_account(user, balance="10.00")
    db_session.add(account)
    await db_session.flush()

    txn = make_transaction(account, type_=TransactionType.DEPOSIT, amount="5.00")
    db_session.add(txn)
    await db_session.commit()

    fetched = await db_session.get(Transaction, txn.id)
    assert fetched is not None
    assert fetched.type is TransactionType.DEPOSIT
    assert fetched.amount == Decimal("5.00")


async def test_unique_email_enforced_by_db(db_session) -> None:
    user = make_user(email="dup@example.com")
    db_session.add(user)
    await db_session.commit()

    with pytest.raises(IntegrityError):
        dup = make_user(email="dup@example.com")
        db_session.add(dup)
        await db_session.commit()
    await db_session.rollback()
