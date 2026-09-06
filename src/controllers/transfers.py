from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.deps import get_current_user
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.transfer import TransferIn, TransferOut
from src.services import transfers as transfers_service

router = APIRouter(prefix="/api/v1", tags=["transfers"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/transfers", response_model=TransferOut, status_code=201)
async def transfer(
    payload: TransferIn,
    user: CurrentUser,
    session: SessionDep,
) -> TransferOut:
    tx: Transaction = await transfers_service.transferir(
        session,
        payload.from_account_id,
        payload.to_account_id,
        payload.amount,
        user,
    )
    return TransferOut(
        id=tx.id,
        from_account_id=payload.from_account_id,
        to_account_id=payload.to_account_id,
        amount=payload.amount,
        created_at=tx.created_at,
    )
