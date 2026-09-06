import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.config import settings
from src.controllers import auth, me
from src.database import engine
from src.logging_setup import setup_logging
from src.middleware import RequestContextMiddleware
from src.security import CredentialsError

logger = logging.getLogger("pybank")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings.validate_security()
    # Smoke check: falha rápido se o banco nao estiver alcancavel.
    # Migracoes sao manuais (alembic upgrade head) — nunca create_all aqui.
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("PyBank iniciado", extra={"request_id": "startup"})
    yield
    await engine.dispose()
    logger.info("PyBank encerrado", extra={"request_id": "shutdown"})


app = FastAPI(
    title="PyBank",
    version="0.1.0",
    description="API bancaria assincrona em FastAPI - projeto portfolio",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(CredentialsError)
async def credentials_error_handler(request: Request, exc: CredentialsError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": "invalid credentials"})


app.include_router(auth.router)
app.include_router(me.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
