from enum import StrEnum


class TransactionType(StrEnum):
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    TRANSFER = "transfer"


class IdempotencyStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
