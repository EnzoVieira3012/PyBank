from src.schemas.enums import IdempotencyStatus, TransactionType


def test_transaction_type_values() -> None:
    assert TransactionType.DEPOSIT == "deposit"
    assert TransactionType.WITHDRAW == "withdraw"
    assert TransactionType.TRANSFER == "transfer"


def test_idempotency_status_values() -> None:
    assert IdempotencyStatus.PENDING == "pending"
    assert IdempotencyStatus.DONE == "done"


def test_enums_valid_strings() -> None:
    assert TransactionType("deposit") is TransactionType.DEPOSIT
    assert IdempotencyStatus("done") is IdempotencyStatus.DONE
