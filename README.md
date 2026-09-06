# 🏦 PyBank

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-100%25_async-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/) [![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-4479A1)](https://www.sqlalchemy.org/) [![Postgres](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/) [![Alembic](https://img.shields.io/badge/Alembic-Migrations-00C7B7)](https://alembic.sqlalchemy.org/) [![JWT](https://img.shields.io/badge/JWT-Auth-000000)](https://jwt.io/) [![CI](https://img.shields.io/badge/CI-GitHub_Actions-181717?logo=github&logoColor=white)](https://github.com/EnzoVieira3012/PyBank/actions) [![LinkedIn](https://img.shields.io/badge/LinkedIn-Enzo_Vieira-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/enzovieiratrabalho/)

**API bancária assíncrona em Python — nível pleno, projeto portfolio.**

PyBank é uma API REST bancária `100% async` construída com FastAPI, SQLAlchemy 2.0 e PostgreSQL. Aplica arquitetura de mercado: camadas separadas (models / schemas / services / controllers), transações atômicas com `SELECT FOR UPDATE`, trilha de auditoria, idempotência, autenticação JWT com refresh token e cobertura de testes ≥ 90%.

Open source (MIT License). Em desenvolvimento — Módulos 0 a 3 concluídos (setup, models, db, auth).

---

## 🛠️ Stack

| | |
|---|---|
| 🐍 **Python 3.13+** | Linguagem principal |
| ⚡ **FastAPI 100% async** | Framework HTTP, Pydantic v2 + pydantic-settings |
| 🗄️ **SQLAlchemy 2.0 async + asyncpg** | ORM assíncrono |
| 🔄 **Alembic** | Migrações (nunca `create_all` em produção) |
| 🐘 **PostgreSQL 16** | Banco de dados (docker-compose local e CI) |
| 🔐 **JWT + bcrypt** | Autenticação e refresh token rotativo |
| 🧪 **pytest + pytest-asyncio + httpx** | Testes unitários e de integração (Postgres real) |
| 🧹 **ruff + mypy** | Lint e tipagem estática |
| 🚀 **GitHub Actions** | CI desde o primeiro push |

---

## 📦 Estrutura alvo

```
src/
├── main.py               # create_app factory + lifespan + error handlers
├── config.py             # pydantic-settings, fail-fast SECRET_KEY
├── logging_setup.py      # logs JSON + correlation ID
├── database.py           # engine async + session (commit/rollback) + pool_pre_ping
├── models/               # User, Account, Transaction, IdempotencyKey, AuditLog, RefreshToken
├── schemas/              # Pydantic In/Out + enums
├── security.py           # JWT, bcrypt, hash de refresh token
├── deps.py               # get_current_user (Bearer → 401)
├── controllers/          # routers /api/v1 (auth, me)
├── middleware.py         # request/correlation ID, security headers
└── alembic/              # migrações (env.py async, URL via settings)
tests/
├── fixtures/
│   └── factories.py      # dados de teste com ROUND_HALF_UP
├── conftest.py           # DB real + TRUNCATE por teste
├── unit/
└── integration/
docker-compose.yml
Dockerfile
.github/workflows/ci.yml
```

---

## 🚀 Como rodar local

> Requer **Docker** (Postgres 16) e **Python 3.13+**.

```powershell
# 1. Sobe o Postgres 16
docker compose up -d

# 2. Ambiente virtual
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Dependências
pip install -r requirements.txt -r requirements-dev.txt

# 4. Configuração
cp .env.example .env
# Edite .env: gere uma SECRET_KEY forte

# 5. Cria o schema (migrações Alembic)
alembic upgrade head

# 6. Sobe a API
python -m uvicorn src.main:app --reload
```

> 🔐 **Segurança**: credenciais do banco (`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`) e `SECRET_KEY` vivem **só** no `.env` (gitignored). O `docker-compose.yml` referencia o `.env` — nunca credenciais hardcoded em arquivos commitados. Mesma regra no `alembic.ini` (URL vazia, vem do `settings`).

Docs interativas: **http://localhost:8000/docs**

---

## 🧪 Testes e qualidade

```powershell
# Testes (requer Docker up — usa Postgres real, não fake)
python -m pytest

# Cobertura (meta: ≥90%)
python -m pytest --cov=src --cov-report=term-missing

# Lint e formatação
ruff check .
ruff format .

# Tipagem
mypy src
```

> Migrações são manuais (`alembic upgrade head`) — **nunca `create_all`** (síncrono, quebra com asyncpg). CI/deploy rodam migração por script. Cobertura de migrações e schema é validada nos testes de integração.

---

## 🧪 Testar no Postman

Collection pronta com **variáveis centralizadas** — configure uma vez, use em tudo:

1. **Download direto**: [PyBank.postman_collection.json](https://github.com/EnzoVieira3012/PyBank/releases/download/v0.4/PyBank.postman_collection.json) — clica e baixa o arquivo (Release asset, sem clone).
2. Coleção: [PyBank.postman_collection.json](https://raw.githubusercontent.com/EnzoVieira3012/PyBank/develop/docs/postman/PyBank.postman_collection.json) — a URL abre o JSON no navegador; no Postman não precisa baixar (ver passo 3) e, se quiser o arquivo, use o botão **↘ Download raw file** (canto superior direito da página).
3. Postman → **Import** → aba **Link** → cole a URL acima → importa direto (ou Import → File, se baixou).
3. Abra a collection → aba **Variables** — edite só aqui: `baseUrl`, `apiEmail`, `apiSenha`.
4. Rode `Login` primeiro — ele **preenche `accessToken`/`refreshToken` automaticamente** nos testes.
5. Endpoints protegidos (`Me`, `Logout`) já usam `Authorization: Bearer {{accessToken}}` — nada hardcoded.

| Request | Depende de |
|---------|-----------|
| `Health` | nada |
| `Register` | `apiEmail`/`apiSenha` |
| `Login` | `apiEmail`/`apiSenha` → grava tokens |
| `Refresh` | `refreshToken` (rotação: reuso → 401) |
| `Me` | `accessToken` |
| `Logout` | `accessToken` + `refreshToken` |

---

## 🔐 Autenticação

JWT HS256 com refresh token rotativo e revogável (armazenado como hash SHA-256 no banco — token puro nunca persiste).

| Endpoint | Descrição |
|----------|-----------|
| `POST /api/v1/auth/register` | Cria conta → 201 `UserOut`; e-mail duplicado → 409 |
| `POST /api/v1/auth/login` | Login → `{access_token, refresh_token, token_type}`; erro → 401 "invalid credentials" (não vaza existência) |
| `POST /api/v1/auth/refresh` | Rotação: revoga o refresh usado, emite par novo; reuso → 401 |
| `POST /api/v1/auth/logout` | Revoga o refresh token (requer auth) → 204 |
| `GET /api/v1/me` | Dados do usuário autenticado (`Authorization: Bearer`) |

Fluxo: `register` → `login` → `Authorize` (access token) → `/me`. Sem token ou token inválido → 401.

---

## 🔄 Operações (Contas)

Contas de débito com saldo `NUMERIC(18,2)` e constraint `balance >= 0` no banco (ex.: saque de `0.01` com saldo `0` → 409, nunca negativo).

| Endpoint | Descrição |
|----------|-----------|
| `POST /api/v1/accounts` | Cria conta para o usuário autenticado → 201 |
| `GET /api/v1/accounts` | Lista contas do usuário autenticado |
| `POST /api/v1/accounts/{id}/deposits` | `{amount}` creditado via `UPDATE ... RETURNING` atômico → 200 saldo novo |
| `POST /api/v1/accounts/{id}/withdrawals` | `{amount}` debitado; saldo insuficiente → 409; conta de outro usuário → 404 |

Depósito e saque usam UPDATE atômico com `RETURNING` — sem read-modify-write, sem corrida entre requisições concorrentes (teste cobre 2 saques paralelos: 1 passa, 1 → 409).

---

## 🗄️ Modelos (schema)

| Tabela | Campos principais | Constraints |
|--------|-------------------|-------------|
| `users` | `id` UUID PK, `email`, `password_hash` | UNIQUE email |
| `accounts` | `id`, `user_id` FK, `balance` Numeric(18,2) | **CHECK `balance >= 0`** |
| `transactions` | `id`, `account_id` FK, `type` enum (deposit/withdraw/transfer), `amount`, `counterpart_account_id` FK nullable | enums nativos |
| `idempotency_keys` | `id`, `user_id` FK, `key`, `fingerprint`, `status` enum (pending/done), `response_status`, `response_body`, `expires_at` | **UNIQUE (`user_id`, `key`)** |
| `audit_logs` | `id`, `user_id` FK nullable, `account_id` FK nullable, `action`, `before`/`after` JSON, `ip`, `correlation_id` | FKs opcionais |
| `refresh_tokens` | `id`, `user_id` FK, `token_hash`, `expires_at`, `revoked` | UNIQUE token_hash |

Todos os models herdam `UUIDMixin` (PK UUID default `uuid4`) + `TimestampMixin` (`created_at`/`updated_at`) — zero repetição de coluna.

---

## 🔧 Variáveis de ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `APP_NAME` | `PyBank` | Nome da aplicação |
| `API_V1_STR` | `/api/v1` | Prefixo das rotas v1 |
| `POSTGRES_USER` | *(obrigatório)* | Usuário do Postgres (docker-compose lê do `.env`) |
| `POSTGRES_PASSWORD` | *(obrigatório)* | Senha do Postgres — só no `.env`, nunca hardcoded |
| `POSTGRES_DB` | *(obrigatório)* | Nome do banco |
| `DATABASE_URL` | *(obrigatório)* | URL asyncpg completa |
| `SECRET_KEY` | *(obrigatória)* | Chave JWT — fail-fast se ausente ou `changeme` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Validade do access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Validade do refresh token |
| `RATE_LIMIT_TIMES` | `100` | Requests permitidos por janela |
| `RATE_LIMIT_SECONDS` | `60` | Janela do rate limit (s) |
| `CORS_ORIGINS` | `["http://localhost:8000"]` | Origens CORS (JSON list) |

---

## 🧱 Módulos (roadmap)

| # | Branch | Foco | Status |
|---|--------|------|--------|
| 0 | `feature/setup` | Fundação, venv, config, logs JSON + correlation ID | ✅ |
| 1 | `feature/models` | Modelos SQLAlchemy + schemas + fixtures | ✅ |
| 2 | `feature/db` | Postgres docker-compose + Alembic + migração inicial | ✅ |
| 3 | `feature/auth` | JWT + refresh token + register/login | ✅ |
| 4 | `feature/transactions` | Depósito/saque com atomic UPDATE | ✅ |
| 5 | `feature/transfer` | Transferência com SELECT FOR UPDATE | ⏳ |
| 6 | `feature/audit` | Trilha de auditoria (antes/depois) | ⏳ |
| 7 | `feature/idempotency` | Idempotency-Key (409/replay/corrida) | ⏳ |
| 8 | `feature/statement` | Extrato e consultas | ⏳ |
| 9 | `feature/rate-limit` | Rate limiting | ⏳ |
| 10 | `feature/api` | REST /api/v1 completo + error handlers | ⏳ |
| 11 | `feature/coverage` | Cobertura de testes ≥90% | ⏳ |
| 12 | `feature/ci` | GitHub Actions | ⏳ |
| 13 | `feature/docs` | README EN/PT | ⏳ |
| 14 | `feature/deploy` | Deploy | ⏳ |

---

## 🌿 Regras de git

1. Linha principal de trabalho: branch `develop`.
2. Cada módulo = uma branch `feature/<nome>` criada a partir de `develop`.
3. `main` só recebe merge de `develop`, no final do projeto.
4. Commits no padrão Conventional Commits, em português:
   - `feat(scope): mensagem`
   - `fix(scope): mensagem`
   - `docs(scope): mensagem`
   - `test(scope): mensagem`
5. **Nunca mergear**: a IA faz push da branch e o usuário abre o PR e faz o merge na `develop`.
6. Working tree sempre limpa (nada de arquivos temporários).
7. Nunca commitar: `.env`, segredos, `__pycache__`, bancos, venv.
8. Rodar Python sempre com `python -m ...`.
9. CI verde desde o primeiro push.

---

## 📜 Licença

Este projeto está licenciado sob a [MIT License](LICENSE).

---

## 📬 Contato

**Enzo Vieira**

- **LinkedIn**: [enzovieiratrabalho](https://www.linkedin.com/in/enzovieiratrabalho/)
- **GitHub**: [EnzoVieira3012](https://github.com/EnzoVieira3012)
- **Email**: [enzovieira.trabalho@outlook.com](mailto:enzovieira.trabalho@outlook.com)

*Projeto portfolio — Formação Python Backend Developer DIO*