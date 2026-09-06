import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.logging_setup import setup_logging
from src.middleware import RequestContextMiddleware

logger = logging.getLogger("pybank")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings.validate_security()
    logger.info("PyBank iniciado", extra={"request_id": "startup"})
    yield
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
