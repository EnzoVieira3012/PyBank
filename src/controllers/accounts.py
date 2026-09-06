from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.deps import get_current_user
from src.models.account import Account
from src.models.user import User
from src.schemas.account import AccountOut, AmountIn
from src.services import accounts as accounts_service

router = APIRouter(prefix="/api/v1", tags=["accounts"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/accounts", response_model=AccountOut, status_code=201)
async def create_account(user: CurrentUser, session: SessionDep) -> Account:
    return await accounts_service.criar_conta(session, user)


@router.get("/accounts", response_model=list[AccountOut])
async def list_accounts(user: CurrentUser, session: SessionDep) -> list[Account]:
    return await accounts_service.listar_contas(session, user)


@router.post("/accounts/{account_id}/deposits", response_model=AccountOut, status_code=201)
async def deposit(
    account_id: uuid.UUID,
    payload: AmountIn,
    user: CurrentUser,
    session: SessionDep,
) -> Account:
    return await accounts_service.depositar(session, account_id, payload.amount, user)


@router.post("/accounts/{account_id}/withdrawals", response_model=AccountOut, status_code=201)
async def withdraw(
    account_id: uuid.UUID,
    payload: AmountIn,
    user: CurrentUser,
    session: SessionDep,
) -> Account:
    return await accounts_service.sacar(session, account_id, payload.amount, user)
