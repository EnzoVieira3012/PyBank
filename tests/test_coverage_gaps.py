"""Cobertura explicita para modulos pequenos que o teste de fluxo nao exercita."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from src.logging_setup import JsonFormatter, setup_logging
from src.models.audit import AuditLog
from src.models.idempotency import IdempotencyKey
from src.schemas.audit import AuditLogOut
from src.schemas.enums import IdempotencyStatus
from src.schemas.idempotency import IdempotencyKeyOut


def test_audit_log_out_serializa_model() -> None:
    log = AuditLog(
        id=uuid4(),
        user_id=uuid4(),
        account_id=uuid4(),
        action="deposit",
        before=None,
        after={"balance": "10.00"},
        ip="127.0.0.1",
        correlation_id="cid-xyz",
        created_at=datetime(2026, 9, 6, 12, 0, 0, tzinfo=UTC),
    )
    out = AuditLogOut.model_validate(log)
    assert out.action == "deposit"
    assert out.after == {"balance": "10.00"}
    assert out.correlation_id == "cid-xyz"
    assert out.created_at.year == 2026


def test_idempotency_key_out_serializa_model() -> None:
    key = IdempotencyKey(
        id=uuid4(),
        user_id=uuid4(),
        key="k-1",
        status=IdempotencyStatus.PENDING,
        expires_at=datetime(2026, 9, 6, 13, 0, 0, tzinfo=UTC),
    )
    out = IdempotencyKeyOut.model_validate(key)
    assert out.key == "k-1"
    assert out.status == IdempotencyStatus.PENDING


def test_json_formatter_com_request_id() -> None:
    record = logging.LogRecord(
        name="pybank",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="ola",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    payload = JsonFormatter().format(record)
    assert '"level": "INFO"' in payload
    assert '"request_id": "req-123"' in payload
    assert '"message": "ola"' in payload


def test_json_formatter_sem_request_id() -> None:
    record = logging.LogRecord(
        name="pybank",
        level=logging.WARNING,
        pathname="x.py",
        lineno=1,
        msg="sem",
        args=(),
        exc_info=None,
    )
    payload = JsonFormatter().format(record)
    assert "request_id" not in payload


def test_setup_logging_substitui_handlers() -> None:
    root = logging.getLogger()
    antes = list(root.handlers)
    setup_logging(level=logging.DEBUG)
    depois = list(root.handlers)
    assert len(depois) == 1
    assert root.level == logging.DEBUG
    # restaura estado global
    for h in antes:
        root.addHandler(h)
    for h in depois:
        root.removeHandler(h)
