"""Rate limiting em memoria: janela fixa deslizante por (chave, janela) com TTL.

Sem lib externa: deque de timestamps por chave, expira ao passar da janela.
Escolha deliberada sobre slowapi: precisamos da identidade do usuario
autenticado como chave (key_func do slowapi so ve a Request, nao a resolucao
de dependencias) e de controle total do erro 429 + Retry-After.

ponytail: trocar por Redis (INCR + EXPIRE) quando houver mais de 1 instancia;
o contrato (allow/clear) fica o mesmo.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Depends, Request

from src.config import settings
from src.deps import get_current_user
from src.models.user import User


class RateLimitError(Exception):
    """Lancado ao estourar o limite; vira 429 com header Retry-After."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"rate limit exceeded, retry in {retry_after}s")


class RateLimiter:
    def __init__(self, times: Callable[[], int], seconds: int = 60) -> None:
        self._times = times  # callable le o settings em runtime: teste ajusta sem reiniciar
        self._seconds = seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> tuple[bool, int]:
        """Registra hit e decide. Retorna (permitido, retry_after_seg)."""
        now = time.monotonic()
        window_start = now - self._seconds
        hits = self._hits[key]
        while hits and hits[0] <= window_start:
            hits.popleft()
        limit = self._times()
        if len(hits) >= limit:
            retry_after = max(1, int(self._seconds - (now - hits[0])) + 1)
            return False, retry_after
        hits.append(now)
        return True, 0

    def clear(self) -> None:
        self._hits.clear()


def _check(limiter: RateLimiter, key: str) -> None:
    allowed, retry_after = limiter.allow(key)
    if not allowed:
        raise RateLimitError(retry_after)


login_limiter = RateLimiter(lambda: settings.RATE_LIMIT_LOGIN)
mutation_limiter = RateLimiter(lambda: settings.RATE_LIMIT_MUTATIONS)


async def limite_login(request: Request) -> None:
    """Por IP em /auth/login e /auth/refresh: protege contra brute-force."""
    host = request.client.host if request.client else "unknown"
    _check(login_limiter, f"ip:{host}")


async def limite_mutacao(user: User = Depends(get_current_user)) -> None:
    """Por usuario em deposits/withdrawals/transfers: nunca por IP, para nao
    derrubar quem compartilha NAT."""
    _check(mutation_limiter, f"user:{user.id}")