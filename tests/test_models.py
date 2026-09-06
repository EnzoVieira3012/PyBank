from sqlalchemy import CheckConstraint, UniqueConstraint

import src.models  # noqa: F401 — garante que todos os models registram em Base.metadata
from src.models import Account, IdempotencyKey, RefreshToken, Transaction, User
from src.models.base import Base


def test_all_models_registered() -> None:
    tables = set(Base.metadata.tables)
    assert {
        "users",
        "accounts",
        "transactions",
        "idempotency_keys",
        "audit_logs",
        "refresh_tokens",
    } <= tables


def test_account_has_balance_check_constraint() -> None:
    table = Account.__table__
    checks = [
        c
        for c in table.constraints
        if isinstance(c, CheckConstraint) and c.name == "ck_accounts_balance_non_negative"
    ]
    assert len(checks) == 1
    assert "balance >= 0" in str(checks[0].sqltext)


def test_user_email_unique() -> None:
    assert User.__table__.c.email.unique


def test_refresh_token_hash_unique() -> None:
    assert RefreshToken.__table__.c.token_hash.unique


def test_idempotency_user_key_unique() -> None:
    table = IdempotencyKey.__table__
    uniques = [
        c
        for c in table.constraints
        if isinstance(c, UniqueConstraint) and c.name == "uq_idempotency_user_key"
    ]
    assert len(uniques) == 1
    assert {"user_id", "key"} <= set(uniques[0].columns.keys())


def test_transaction_type_is_native_enum() -> None:
    column = Transaction.__table__.columns["type"]
    assert column.type.name == "transaction_type"
