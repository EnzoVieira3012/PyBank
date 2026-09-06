from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass
class IdempotencyContext:
    key: str
    fingerprint: str


async def require_idempotency_key(request: Request) -> IdempotencyContext:
    """Header Idempotency-Key obrigatorio nos metodos mutaveis.

    fingerprint = sha256 do BODY CRU (bytes exatos como chegaram) — nunca
    re-canonicalizado, senao whitespace/order de campos viraria falso 409."""
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")
    body = await request.body()
    fingerprint = hashlib.sha256(body).hexdigest()
    return IdempotencyContext(key=key, fingerprint=fingerprint)
