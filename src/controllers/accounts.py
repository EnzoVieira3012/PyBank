from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.controllers.deps import IdempotencyContext, require_idempotency_key
from src.database import get_session
from src.deps import client_ip, correlation_id, get_current_user
from src.models.account import Account
from src.models.user import User
from src.schemas.account import AccountOut, AmountIn
from src.services import accounts as accounts_service
from src.services import idempotency as idempotency_service

router = APIRouter(prefix="/api/v1", tags=["accounts"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
IdempotencyDep = Annotated[IdempotencyContext, Depends(require_idempotency_key)]


@router.post("/accounts", response_model=AccountOut, status_code=201)
async def create_account(user: CurrentUser, session: SessionDep) -> Account:
    return await accounts_service.criar_conta(session, user)


@router.get("/accounts", response_model=list[AccountOut])
async def list_accounts(user: CurrentUser, session: SessionDep) -> list[Account]:
    return await accounts_service.listar_contas(session, user)


@router.post("/accounts/{account_id}/deposits", status_code=201)
async def deposit(
    account_id: uuid.UUID,
    payload: AmountIn,
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
    account = await accounts_service.depositar(
        session,
        account_id,
        payload.amount,
        user,
        ip=client_ip(request),
        correlation_id=correlation_id(request),
    )
    body = AccountOut.model_validate(account).model_dump_json()
    await idempotency_service.complete(session, user.id, idem.key, 201, body)
    return Response(content=body, status_code=201, media_type="application/json")


@router.post("/accounts/{account_id}/withdrawals", status_code=201)
async def withdraw(
    account_id: uuid.UUID,
    payload: AmountIn,
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
    account = await accounts_service.sacar(
        session,
        account_id,
        payload.amount,
        user,
        ip=client_ip(request),
        correlation_id=correlation_id(request),
    )
    body = AccountOut.model_validate(account).model_dump_json()
    await idempotency_service.complete(session, user.id, idem.key, 201, body)
    return Response(content=body, status_code=201, media_type="application/json")
