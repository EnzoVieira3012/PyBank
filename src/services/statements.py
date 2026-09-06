from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import AccountNotFoundError
from src.models.account import Account
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.common import PageMeta
from src.schemas.enums import TransactionType


async def obter_extrato(
    session: AsyncSession,
    account_id: uuid.UUID,
    user: User,
    *,
    page: int,
    page_size: int,
    type_: TransactionType | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> tuple[Sequence[Transaction], PageMeta]:
    """Extrato paginado da conta. Filtros dinamicos: type exato, created_at
    >= from_date e <= to_date (boundaries inclusivas). Mais recentes primeiro.

    Sem o indice composto (account_id, created_at) viraria full scan —
    medido em docs/medicoes.md."""
    conta = await session.scalar(
        select(Account.id).where(Account.id == account_id, Account.user_id == user.id)
    )
    if conta is None:
        raise AccountNotFoundError()

    where = [Transaction.account_id == account_id]
    if type_ is not None:
        where.append(Transaction.type == type_)
    if from_date is not None:
        where.append(Transaction.created_at >= from_date)
    if to_date is not None:
        where.append(Transaction.created_at <= to_date)

    total = await session.scalar(select(func.count()).select_from(Transaction).where(*where))
    total_pages = math.ceil(total / page_size) if total else 0

    itens = (
        await session.scalars(
            select(Transaction)
            .where(*where)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    meta = PageMeta(page=page, page_size=page_size, total_items=total or 0, total_pages=total_pages)
    return itens, meta
