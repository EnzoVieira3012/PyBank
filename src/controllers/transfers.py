from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.controllers.deps import IdempotencyContext, require_idempotency_key
from src.database import get_session
from src.deps import client_ip, correlation_id, get_current_user
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.transfer import TransferIn, TransferOut
from src.services import idempotency as idempotency_service
from src.services import transfers as transfers_service

router = APIRouter(prefix="/api/v1", tags=["transfers"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
IdempotencyDep = Annotated[IdempotencyContext, Depends(require_idempotency_key)]


@router.post("/transfers", status_code=201)
async def transfer(
    payload: TransferIn,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
    idem: IdempotencyDep,
) -> Response:
    claim = await idempotency_service.try_claim(session, user.id, idem.key, idem.fingerprint)
    if not claim.claimed:
        return Response(
            content=claim.replay_body,
            status_code=claim.replay_status or 500,
            media_type="application/json",
        )
    tx: Transaction = await transfers_service.transferir(
        session,
        payload.from_account_id,
        payload.to_account_id,
        payload.amount,
        user,
        ip=client_ip(request),
        correlation_id=correlation_id(request),
    )
    body = TransferOut(
        id=tx.id,
        from_account_id=payload.from_account_id,
        to_account_id=payload.to_account_id,
        amount=payload.amount,
        created_at=tx.created_at,
    ).model_dump_json()
    await idempotency_service.complete(session, user.id, idem.key, 201, body)
    return Response(content=body, status_code=201, media_type="application/json")
