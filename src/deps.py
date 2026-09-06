from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.models.user import User
from src.security import CredentialsError, decode_token

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    request: Request,
    session: SessionDep,
) -> User:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise CredentialsError("token ausente")
    token = auth.removeprefix("Bearer ").strip()
    if not token:
        raise CredentialsError("token ausente")

    payload = decode_token(token, "access")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise CredentialsError("token invalido") from exc

    user = await session.get(User, user_id)
    if user is None:
        raise CredentialsError("usuario inexistente")
    return user
