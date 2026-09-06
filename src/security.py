from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from src.config import settings

ALGORITHM = "HS256"


class CredentialsError(Exception):
    """Token ausente, invalido, expirado ou de tipo errado — vira 401 no handler."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _base_payload(user_id: uuid.UUID, token_type: str, expires_delta: timedelta) -> dict:
    now = datetime.now(UTC)
    return {
        "sub": str(user_id),
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }


def create_access_token(user_id: uuid.UUID) -> str:
    delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        _base_payload(user_id, "access", delta), settings.SECRET_KEY, algorithm=ALGORITHM
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        _base_payload(user_id, "refresh", delta), settings.SECRET_KEY, algorithm=ALGORITHM
    )


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_token(token: str, token_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise CredentialsError("token invalido ou expirado") from exc
    if payload.get("type") != token_type:
        raise CredentialsError("tipo de token invalido")
    return payload
