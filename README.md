# PyBank — Async Banking API

[![CI](https://github.com/EnzoVieira3012/PyBank/actions/workflows/ci.yml/badge.svg)](https://github.com/EnzoVieira3012/PyBank/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-96%25-3fb950)](https://github.com/EnzoVieira3012/PyBank)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

> **Português?** [README.pt-BR.md](README.pt-BR.md)

Async banking API built with FastAPI + PostgreSQL that processes deposits and transfers **without duplicating or losing money under concurrency**.

That's the whole project: **one workflow, not twelve features**. Every design decision (idempotency at the DB constraint level, `SELECT ... FOR UPDATE` with fixed lock order, atomic `UPDATE ... RETURNING`, audit trail) exists to hold that single invariant:

> **1 request = 1 effect. Money never appears twice, never disappears.**

---

## Badges

| Metric | Value |
|--------|-------|
| Tests | 94 passing (lint + mypy + Postgres 16 real + Docker build on CI) |
| Coverage | **96%** (goal ≥ 90%) |
| Runtime | Python 3.13, FastAPI, SQLAlchemy 2 (async), asyncpg, Alembic |
| CI | GitHub Actions — 3 jobs: lint, tests, docker |

---

## Architecture

```
                        ┌──────────────────────────────────────────────┐
                        │                 Client / Postman             │
                        └──────────────────────┬───────────────────────┘
                                               │ HTTPS / JSON
                                               ▼
                        ┌──────────────────────────────────────────────┐
                        │              FastAPI app (async)             │
                        │                                              │
                        │  RequestContextMiddleware ── correlation_id  │
                        │       │        │          │                  │
                        │       ▼        ▼          ▼                  │
                        │  CORS     security   RateLimiter             │
                        │  headers  headers    (60s window)            │
                        │                                              │
                        │              APIRouter /api/v1               │
                        │  auth · accounts · transfers · statements    │
                        └──────────────────────┬───────────────────────┘
                                               │
                                               ▼
                        ┌──────────────────────────────────────────────┐
                        │            Services (business rules)         │
                        │  accounts · transfers · statements · audit   │
                        │  idempotency · auth                          │
                        └──────────────────────┬───────────────────────┘
                                               │ SQLAlchemy 2 (async)
                                               ▼
                        ┌──────────────────────────────────────────────┐
                        │            PostgreSQL 16 (single DB)         │
                        │                                              │
                        │  UNIQUE(user_id, key)  ── idempotency        │
                        │  CHECK (balance >= 0)   ── oversell guard     │
                        │  enum types            ── no magic strings   │
                        │  composite index       ── statement queries  │
                        └──────────────────────────────────────────────┘
```

**Constraints live in the database, not in the app.** The app is just the orchestrator; the DB is the source of truth:

- `UNIQUE (user_id, key)` on `idempotency_keys` — race-safe dedup at the constraint level
- `CHECK (balance >= 0)` on `accounts` — final backstop against oversell
- Native PG `enum` for transaction types — no invalid values possible
- `SELECT ... FOR UPDATE ... ORDER BY id` — deterministic lock order, deadlock-free

---

## The Problem

Banking operations are stateful and concurrent. Two retries of the same deposit, or 100 simultaneous withdrawals on one balance — naive code duplicates money or oversells it.

PyBank treats that as **one workflow with three failure modes**, each proven by a test:

| Failure | What happens | Proof |
|---------|--------------|-------|
| Same request arrives twice | 1 effect; 2nd response is a byte-identical replay | integration test, same `Idempotency-Key` |
| Balance changes concurrently | Only 1 operation wins; invariant holds | 100-way race, 5 cycles |
| Insufficient balance | `409`, nothing written | integration test (0 transactions, 0 audit rows) |

---

## Endpoints

| Method | Path | Auth | Success | Description |
|--------|------|------|---------|-------------|
| POST | `/api/v1/auth/register` | — | 201 | Create user |
| POST | `/api/v1/auth/login` | — | 200 | Login (IP rate-limited) |
| POST | `/api/v1/auth/refresh` | — | 200 | Rotate tokens (IP rate-limited) |
| POST | `/api/v1/auth/logout` | yes | 204 | Revoke refresh token |
| GET | `/api/v1/me` | yes | 200 | Current user |
| POST | `/api/v1/accounts` | yes | 201 | Create account |
| GET | `/api/v1/accounts` | yes | 200 | List accounts |
| POST | `/api/v1/accounts/{id}/deposits` | yes | 201 | Deposit (user rate-limited) |
| POST | `/api/v1/accounts/{id}/withdrawals` | yes | 201 | Withdraw (user rate-limited) |
| POST | `/api/v1/transfers` | yes | 201 | Transfer (user rate-limited) |
| GET | `/api/v1/accounts/{id}/statement` | yes | 200 | Paginated statement |
| GET | `/health` | — | 200/503 | Health check with live DB ping |

Docs (dev, local): [Swagger UI](http://localhost:8000/docs) · [ReDoc](http://localhost:8000/redoc) · [OpenAPI JSON](http://localhost:8000/openapi.json)

Docs (prod, live): [API base URL](https://pybank-api-jlt5.onrender.com) · [Swagger UI](https://pybank-api-jlt5.onrender.com/docs) · [ReDoc](https://pybank-api-jlt5.onrender.com/redoc) · [OpenAPI JSON](https://pybank-api-jlt5.onrender.com/openapi.json)

![Swagger UI](docs/assets/swagger.png)

Every error returns a uniform envelope (with `correlation_id` for log correlation):

```json
{
  "detail": "human-readable message",
  "status_code": 404,
  "path": "/api/v1/transfers",
  "method": "POST",
  "correlation_id": "uuid-v4"
}
```

| Status | When |
|--------|------|
| 400 | Business rule with specific body (e.g., transfer missing `Idempotency-Key`) |
| 401 | Invalid credentials / expired token |
| 404 | Account not found (or not yours — never leaks existence) |
| 409 | Conflict: idempotency key in use, insufficient balance, same-account transfer |
| 422 | Pydantic validation (envelope includes `errors[]`) |
| 429 | Rate limit exceeded (`Retry-After` header) |
| 500 | Unexpected error — logged, never exposed |

---

## Failure Table (what happens when…)

| Failure | Behavior | Proof |
|---------|----------|-------|
| Same request body arrives 2× (retry) | 1 effect; 2nd response is a byte-identical replay of the stored response; nothing re-executes | `test_failure_matrix` — duplicate scenario |
| Same key, different body | `409 idempotency key reuse different payload` — never mixes payloads | integration test |
| 2 concurrent requests, same key | `UNIQUE(user_id, key)` + `INSERT ... ON CONFLICT DO NOTHING` — exactly 1 executes; the other gets `409 request in progress` or replay | race test |
| Balance changes concurrently (100 simultaneous ops) | Only 1 operation wins per row lock; invariant `balance >= 0` holds | `test_falha_corrida_100_saques...` — 100/100 success, final balance 0.00, 0 oversell, 5 cycles |
| Withdrawal/transfer > balance | `409`, full rollback — 0 transactions, 0 audit rows | integration test — insufficient balance |
| Brute-force login attempts | Per-IP limit: 10/min → `429` + `Retry-After` | rate-limit tests |
| API abuse (spam mutations) | Per-user limit: 100/min on deposits/withdrawals/transfers → `429` | rate-limit tests |
| Transfer A→B and B→A concurrently | Fixed lock order (`ORDER BY id`) — serializes, deadlock impossible | transfer tests |
| Idempotency key expired (24h TTL) | Accepted as new claim | TTL test |

---

## Rejected Decisions (ADR)

| Decision | Rejected option | Why |
|----------|-----------------|-----|
| **Postgres `UNIQUE` for idempotency** | Redis | Constraint-level atomicity, zero extra infra, durable across restarts. Redis only pays off with horizontal multi-instance scaling — revisit at deploy |
| **`SELECT ... FOR UPDATE` with fixed order** | Optimistic locking (version column) | Pessimistic lock serializes the cash flow with one query; optimistic would retry-fail a losing writer. Optimistic becomes viable on a hot single row (very high contention) |
| **Offset pagination** | Cursor-based | Offset + composite index is enough at current volume; cursor avoids the deep-page scan past ~100k rows — swap when needed |
| **Direct `bcrypt`** | `passlib` | `passlib` breaks with `bcrypt>=4.1` (known incompatibility); direct `bcrypt` is stable, fewer deps |

---

## Measurements

### Concurrency race ×100 — 5 cycles

Scenario: 1 account with `100.00`, 100 concurrent withdrawals of `1.00`, via `asyncio.gather` + 100 independent `AsyncClient` sessions.

Without the row lock, this test would oversell (negative balance). With `SELECT ... FOR UPDATE ... ORDER BY id`:

| Cycle | Withdrawals 201 | Final balance | Transactions persisted | Time |
|-------|-----------------|---------------|------------------------|------|
| 1 | 100/100 | 0.00 | 100 withdrawals | < 60s |
| 2 | 100/100 | 0.00 | +100 | idem |
| 3 | 100/100 | 0.00 | +100 | idem |
| 4 | 100/100 | 0.00 | +100 | idem |
| 5 | 100/100 | 0.00 | +100 | idem |

Invariant: `money in = money out` on every cycle. Reproduce: `python -m pytest tests/integration/test_failure_matrix.py`.

### Composite index — before / after

Query: single account statement (5,000 rows) filtered by `type` + date window, `ORDER BY created_at DESC LIMIT 20` — 10,000 seeded transactions.

| Index | Plan | Execution time |
|-------|------|----------------|
| None (only `account_id`) | Bitmap scan → filter discarded 3,735 rows → top-N sort | **0.698 ms** |
| `(account_id, created_at DESC)` | Index scan on the window, residual filter discarded only 38 rows, no sort | **0.050 ms** — **~14× faster** |

Migration: `a183cc6c2083_indice_composto_account_created_at`. Reproduce: `python scripts/seed.py` → `EXPLAIN ANALYZE` with and without the index (`alembic downgrade -1` / `upgrade head`).

### Test suite

94 tests · coverage **96%** (goal ≥ 90%) · runs on a real Postgres 16 (test DB `pybank_test`, isolated from dev) · 5 targeted tests cover the gaps the happy path misses (JSON formatter, small schemas, logging setup).

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pytest --cov=src --cov-report=term-missing
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src
```

---

## Run locally

Requirements: Docker (Postgres 16) + Python 3.13.

```powershell
# 1. env (never commit real secrets — copy from template)
Copy-Item .env.example .env
#    fill POSTGRES_*, DATABASE_URL, SECRET_KEY in .env

# 2. database
docker compose up -d
.venv\Scripts\python.exe -m alembic upgrade head    # migrations, never create_all

# 3. API
.venv\Scripts\python.exe -m uvicorn src.main:app --reload
# http://localhost:8000/docs
```

Migrations are always explicit (`alembic upgrade head`) — never `create_all` (synchronous, breaks with asyncpg). CI applies migrations by script; schema correctness is validated by integration tests.

### Postman

Collection with centralized variables — set `baseUrl`, `apiEmail`, `apiSenha` once; `Login` auto-fills `accessToken`/`refreshToken`; protected endpoints use `Bearer {{accessToken}}`.

- [Download release asset](https://github.com/EnzoVieira3012/PyBank/releases/download/v0.4/PyBank.postman_collection.json)
- [Raw collection](https://raw.githubusercontent.com/EnzoVieira3012/PyBank/develop/docs/postman/PyBank.postman_collection.json)

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `PyBank` | App name |
| `API_V1_STR` | `/api/v1` | API prefix |
| `POSTGRES_USER` | *required* | Postgres user (`docker-compose` reads `.env`) |
| `POSTGRES_PASSWORD` | *required* | Postgres password — `.env` only, never hardcoded |
| `POSTGRES_DB` | *required* | Database name |
| `DATABASE_URL` | *required* | Full asyncpg URL |
| `SECRET_KEY` | *required* | JWT key — fail-fast if missing or `changeme` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `RATE_LIMIT_LOGIN` | `10` | Login attempts per IP per 60s window |
| `RATE_LIMIT_MUTATIONS` | `100` | Mutations per user per 60s window |
| `CORS_ORIGINS` | `["http://localhost:8000"]` | Allowed origins (JSON list) |

---

## Deploy

Two paths, same image (multi-stage `Dockerfile`, non-root user, healthcheck).

### Option A — VPS with Docker Compose (recommended)

```bash
cp .env.example .env        # fill real secrets — .env never committed
docker compose -f docker-compose.prod.yml run --rm app alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --build
curl http://localhost:8000/health
```

Checklist (hardening):

- Firewall: `ufw allow 22/tcp; ufw allow 80/tcp; ufw allow 443/tcp` — **5432 stays internal** (`docker-compose.prod.yml` does not expose it)
- SSH: key auth only, `PasswordAuthentication no`, `fail2ban`
- HTTPS: Caddy / Traefik / certbot reverse proxy on 80/443 → `app:8000`
- `.env`: `chmod 600`
- Rate limiting already in-app (login per-IP, mutations per-user) — optional nginx `limit_req` in front
- Logs: JSON formatter on stdout → docker logs / journald; add UptimeRobot ping on `/health`

### Option B — Render (free tier)

1. Create **free Postgres** — copy its `Internal Database URL` into `DATABASE_URL` below (Render may give `postgres://`; convert to `postgresql+asyncpg://`)
2. Create **free Web Service** linked to this repo (branch `main`) — Runtime `Python 3`, Build Command empty, Start Command `./render_deploy.sh`
3. Environment (dashboard): `DATABASE_URL`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `RATE_LIMIT_LOGIN`, `RATE_LIMIT_MUTATIONS`, `CORS_ORIGINS`
4. Wait for auto-deploy; check `https://<service>.onrender.com/health` → `200`
5. Add UptimeRobot monitor on `/health` (free) — the app itself is free-tier friendly (no Redis, no workers)
6. Put the public URL in the Swagger `baseUrl` Postman variable

Always free plan — this app uses no paid-only Render features (in-process rate limiter, no background workers, no extra infra).

---

## Key mechanisms

- **Idempotency**: `Idempotency-Key` header required on all mutating POSTs (missing → 400). Same key + same body → stored byte-identical replay. Same key + different body → 409. The key row commits or rolls back **with** the operation — a failed op frees the key for retry.
- **Atomic money movement**: deposit/withdraw use single `UPDATE ... RETURNING` — no read-modify-write, no race window. Transfers lock both accounts in one query (`FOR UPDATE ORDER BY id`), write 2 `Transaction` rows + debit + credit in one commit, roll back everything on any error.
- **Auth**: JWT access (30 min, HS256) + rotating refresh token (7 days, hashed at rest, `UNIQUE token_hash`). Logout revokes; refresh rotation reuses the old token — reuse after rotation → 401.
- **Audit**: every mutation writes `audit_logs` with `before`/`after` JSON, client IP, and the request `correlation_id` — compliance trace without extra infra.

## Project structure

```
src/
  main.py            # app factory, error envelope, health check
  config.py          # env settings (fail-fast on SECRET_KEY)
  middleware.py      # correlation_id, security headers
  rate_limit.py      # in-memory sliding window (no Redis, no slowapi)
  controllers/       # HTTP layer: auth, accounts, transfers, statements
  services/          # business rules: transfers, statements, idempotency, audit
  models/            # SQLAlchemy models (UUID + timestamp mixins)
  schemas/           # Pydantic v2 schemas
tests/
  integration/       # failure matrix, race ×100, idempotency, rate limits
```

## License & contact

[MIT](LICENSE) · Enzo Vieira — [LinkedIn](https://www.linkedin.com/in/enzovieiratrabalho/) · [GitHub](https://github.com/EnzoVieira3012) · [Email](mailto:enzovieira.trabalho@outlook.com)

*Portfolio project — Python Backend Developer (DIO)*