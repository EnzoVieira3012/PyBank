from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import BusinessError
from src.models.idempotency import IdempotencyKey
from src.schemas.enums import IdempotencyStatus

TTL = timedelta(hours=24)


@dataclass
class ClaimResult:
    claimed: bool = False
    replay_status: int | None = None
    replay_body: str | None = None


async def try_claim(
    session: AsyncSession,
    user_id: uuid.UUID,
    key: str,
    fingerprint: str,
) -> ClaimResult:
    """Tenta o claim da chave. UNIQUE(user_id, key) resolve a corrida de forma
    atomica (INSERT ON CONFLICT DO NOTHING): exatamente um request vence.

    - venceu -> claimed (executa a operacao)
    - outro em voo (pending) -> 409 "request in progress"
    - mesma chave, body diferente -> 409 "reuse with different payload"
    - done -> replay (resposta gravada devolvida para repeticao)
    - expirada (TTL 24h) -> reset e re-claim como novo
    """
    now = datetime.now(UTC)

    inserted = await session.execute(
        pg_insert(IdempotencyKey)
        .values(
            user_id=user_id,
            key=key,
            fingerprint=fingerprint,
            status=IdempotencyStatus.PENDING,
            expires_at=now + TTL,
        )
        .on_conflict_do_nothing(constraint="uq_idempotency_user_key")
        .returning(IdempotencyKey.id)
    )
    if inserted.first() is not None:
        return ClaimResult(claimed=True)

    row = await session.scalar(
        select(IdempotencyKey).where(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key)
    )
    if row is None:  # corrida: o outro ainda nao commitou o INSERT
        raise BusinessError("request in progress")

    if row.fingerprint != fingerprint:
        raise BusinessError("idempotency key reuse with different payload")

    if row.status == IdempotencyStatus.DONE and row.expires_at > now:
        return ClaimResult(
            claimed=False,
            replay_status=row.response_status,
            replay_body=row.response_body,
        )

    if row.status == IdempotencyStatus.PENDING and row.expires_at > now:
        raise BusinessError("request in progress")

    # chave expirada: reset e re-claim como novo
    await session.execute(
        update(IdempotencyKey)
        .where(IdempotencyKey.id == row.id)
        .values(
            status=IdempotencyStatus.PENDING,
            fingerprint=fingerprint,
            response_status=None,
            response_body=None,
            expires_at=now + TTL,
        )
    )
    await session.flush()
    return ClaimResult(claimed=True)


async def complete(
    session: AsyncSession,
    user_id: uuid.UUID,
    key: str,
    response_status: int,
    response_body: str,
) -> None:
    """Grava o resultado no claim pendente — mesmo commit da operacao
    (get_session). Operacao que falhou da rollback junto: chave some,
    retry pode re-executar limpo."""
    await session.execute(
        update(IdempotencyKey)
        .where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.key == key,
            IdempotencyKey.status == IdempotencyStatus.PENDING,
        )
        .values(
            status=IdempotencyStatus.DONE,
            response_status=response_status,
            response_body=response_body,
        )
    )
    await session.flush()
