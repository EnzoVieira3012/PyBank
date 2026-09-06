from __future__ import annotations


class BusinessError(Exception):
    status_code = 409
    detail = "business error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.detail
        super().__init__(self.detail)


class AccountNotFoundError(BusinessError):
    status_code = 404
    detail = "account not found"


class IdempotencyConflictError(BusinessError):
    status_code = 409
    detail = "idempotency key conflict"
