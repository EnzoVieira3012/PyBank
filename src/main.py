"""Factory da aplicacao + error handlers uniformes.

create_app() injeta settings/middleware/routers; testes sobrescrevem
dependencias (ex.: get_session) via app.dependency_overrides. O modulo
expoe `app = create_app()` para `uvicorn src.main:app`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.api import api_router
from src.config import Settings, settings
from src.database import async_session, engine
from src.exceptions import BusinessError
from src.logging_setup import setup_logging
from src.middleware import RequestContextMiddleware
from src.rate_limit import RateLimitError
from src.security import CredentialsError

logger = logging.getLogger("pybank")

OPENAPI_TAGS: list[dict[str, str]] = [
    {"name": "auth", "description": "Cadastro, login, refresh e logout."},
    {"name": "me", "description": "Dados do usuario autenticado."},
    {"name": "accounts", "description": "Contas, depositos e saques."},
    {"name": "transfers", "description": "Transferencias entre contas (SELECT FOR UPDATE)."},
    {"name": "statements", "description": "Extrato paginado com filtros por tipo e data."},
]


def _error_envelope(
    request: Request,
    status_code: int,
    detail: str,
) -> dict[str, Any]:
    return {
        "detail": detail,
        "status_code": status_code,
        "path": request.url.path,
        "method": request.method,
        "correlation_id": getattr(request.state, "correlation_id", None),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    cfg: Settings = app.state.settings
    cfg.validate_security()
    # Smoke check: falha rapido se o banco nao estiver alcancavel.
    # Migracoes sao manuais (alembic upgrade head) - nunca create_all aqui.
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("PyBank iniciado", extra={"request_id": "startup"})
    yield
    await engine.dispose()
    logger.info("PyBank encerrado", extra={"request_id": "shutdown"})


def create_app(cfg: Settings | None = None) -> FastAPI:
    """Factory principal. Aceita settings opcional para tests isolados."""
    app = FastAPI(
        title="PyBank API",
        version="1.0.0",
        description=(
            "API bancaria assincrona em FastAPI - portfolio. "
            "Auth JWT, contas, deposito, saque, transferencia com lock, "
            "auditoria, idempotencia, extrato e rate limiting."
        ),
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    app.state.settings = cfg or settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app.state.settings.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.add_middleware(RequestContextMiddleware)

    # --- error handlers (polimorfismo: BusinessError cobre todas as filhas) ---
    @app.exception_handler(CredentialsError)
    async def _creds(request: Request, exc: CredentialsError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=_error_envelope(request, 401, "invalid credentials"),
        )

    @app.exception_handler(BusinessError)
    async def _biz(request: Request, exc: BusinessError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(request, exc.status_code, exc.detail),
        )

    @app.exception_handler(RateLimitError)
    async def _rl(request: Request, exc: RateLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content=_error_envelope(request, 429, "rate limit exceeded"),
            headers={"Retry-After": str(exc.retry_after)},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # exc.errors() pode trazer Decimal/bytes; jsonable_encoder normaliza.
        return JSONResponse(
            status_code=422,
            content=_error_envelope(request, 422, "validation error")
            | {"errors": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "erro nao tratado",
            extra={"correlation_id": getattr(request.state, "correlation_id", None)},
        )
        return JSONResponse(
            status_code=500,
            content=_error_envelope(request, 500, "internal server error"),
        )

    # --- routers ---
    app.include_router(api_router)

    # --- health: ping no banco via session; 503 se DB fora ---
    @app.get("/health", tags=["health"], summary="Health check com ping no DB")
    async def health() -> JSONResponse:
        try:
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - queremos 503 explicito
            logger.warning("health: banco indisponivel: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "degraded", "database": "unreachable"},
            )
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "database": "ok"},
        )

    return app


# Compatibilidade com `uvicorn src.main:app`
app = create_app()
