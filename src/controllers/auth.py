from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_session
from src.deps import client_ip, correlation_id, get_current_user
from src.models.refresh_token import RefreshToken
from src.models.user import User
from src.rate_limit import limite_login
from src.schemas.auth import LoginIn, RefreshIn, TokenOut
from src.schemas.user import UserCreate, UserOut
from src.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from src.services.audit import registrar

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

INVALID_CREDENTIALS = "invalid credentials"

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


async def _issue_token_pair(session: AsyncSession, user: User) -> TokenOut:
    refresh_token = create_refresh_token(user.id)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
    )


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email.lower()))


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    payload: UserCreate,
    session: SessionDep,
    request: Request,
) -> User:
    if await _get_user_by_email(session, payload.email) is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        # Corrida: e-mail criado entre a checagem e o flush
        raise HTTPException(status_code=409, detail="email already registered") from exc
    await registrar(
        session,
        action="register",
        user_id=user.id,
        ip=client_ip(request),
        correlation_id=correlation_id(request),
    )
    await session.commit()  # visivel antes da resposta: evita corrida register->login
    return user


@router.post(
    "/login",
    response_model=TokenOut,
    dependencies=[Depends(limite_login)],
    summary="Autenticar (limite por IP)",
)
async def login(
    payload: LoginIn,
    session: SessionDep,
    request: Request,
) -> TokenOut:
    user = await _get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    await registrar(
        session,
        action="login",
        user_id=user.id,
        ip=client_ip(request),
        correlation_id=correlation_id(request),
    )
    tokens = await _issue_token_pair(session, user)
    await session.commit()  # rotacao/refresh token + auditoria persistidos antes da resposta
    return tokens


@router.post(
    "/refresh",
    response_model=TokenOut,
    dependencies=[Depends(limite_login)],
    summary="Renovar tokens (limite por IP)",
)
async def refresh(
    req: RefreshIn,
    session: SessionDep,
    request: Request,
) -> TokenOut:
    stored = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(req.refresh_token))
    )
    if stored is None or stored.revoked:
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    user = await session.get(User, stored.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)

    stored.revoked = True  # rotacao: token usado morre no banco
    await registrar(
        session,
        action="refresh",
        user_id=user.id,
        ip=client_ip(request),
        correlation_id=correlation_id(request),
    )
    tokens = await _issue_token_pair(session, user)
    await session.commit()  # rotacao/refresh token + auditoria persistidos antes da resposta
    return tokens


@router.post("/logout", status_code=204)
async def logout(
    req: RefreshIn,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
) -> Response:
    stored = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(req.refresh_token))
    )
    if stored is not None and stored.user_id == user.id:
        stored.revoked = True
    await registrar(
        session,
        action="logout",
        user_id=user.id,
        ip=client_ip(request),
        correlation_id=correlation_id(request),
    )
    await session.commit()  # revogacao + auditoria persistidas antes da resposta
    return Response(status_code=204)
