from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.deps import get_current_user
from src.models.user import User
from src.schemas.enums import TransactionType
from src.schemas.statement import StatementOut
from src.schemas.transaction import TransactionOut
from src.services import statements as statements_service

router = APIRouter(prefix="/api/v1", tags=["statements"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/accounts/{account_id}/statement", response_model=StatementOut)
async def statement(
    account_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    type: TransactionType | None = None,
    from_date: Annotated[datetime | None, Query(alias="from")] = None,
    to_date: Annotated[datetime | None, Query(alias="to")] = None,
) -> StatementOut:
    itens, meta = await statements_service.obter_extrato(
        session,
        account_id,
        user,
        page=page,
        page_size=page_size,
        type=type,
        from_date=from_date,
        to_date=to_date,
    )
    return StatementOut(
        account_id=account_id,
        items=[TransactionOut.model_validate(t) for t in itens],
        meta=meta,
    )