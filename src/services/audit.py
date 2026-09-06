from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit import AuditLog


async def registrar(
    session: AsyncSession,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
    correlation_id: str | None = None,
) -> None:
    """Insere AuditLog na MESMA transacao da operacao — o commit do get_session
    persiste o log junto da operacao; qualquer rollback apaga o log junto
    (coerencia total, zero orfao)."""
    session.add(
        AuditLog(
            user_id=user_id,
            account_id=account_id,
            action=action,
            before=before,
            after=after,
            ip=ip,
            correlation_id=correlation_id,
        )
    )
    await session.flush()
