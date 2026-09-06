# syntax=docker/dockerfile:1.7
# PyBank - multi-stage: build deps em uma imagem, runtime limpa em outra.

FROM python:3.13-slim AS builder
WORKDIR /build

# Deps de sistema para compilar pacotes que tem extensao C (asyncpg, etc).
# Sao necessarias no builder, NAO no runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


FROM python:3.13-slim AS runtime
WORKDIR /app

# libpq runtime do asyncpg (sem headers, sem gcc).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Usuario nao-root.
RUN useradd --create-home --shell /bin/bash pybank

COPY --from=builder /wheels /wheels
COPY requirements.txt ./
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

USER pybank
EXPOSE 8000

# Healthcheck: o proprio /health faz ping no DB.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=3).raise_for_status()" \
    || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
