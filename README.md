# 🏦 PyBank

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-100%25_async-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/) [![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-4479A1?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/) [![Postgres](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/) [![Alembic](https://img.shields.io/badge/Alembic-Migrations-00C7B7)](https://alembic.sqlalchemy.org/) [![JWT](https://img.shields.io/badge/JWT-Auth-000000?logo=jsonwebtokens&logoColor=white)](https://jwt.io/) [![CI](https://img.shields.io/badge/CI-GitHub_Actions-181717?logo=github&logoColor=white)](https://github.com/EnzoVieira3012/PyBank/actions) [![LinkedIn](https://img.shields.io/badge/LinkedIn-Enzo%20Vieira-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/enzovieiratrabalho/)

**API bancária assíncrona em Python — nível pleno, projeto portfolio.**

PyBank é uma API REST bancária `100% async` construída com FastAPI, SQLAlchemy 2.0 e PostgreSQL. Aplica arquitetura de mercado: camadas separadas (models / schemas / services / controllers), transações atômicas com `SELECT FOR UPDATE`, trilha de auditoria, idempotência, autenticação JWT com refresh token e cobertura de testes ≥ 90%.

Open source (MIT License). Em desenvolvimento — Módulo 0 (setup) em andamento.

---

## 🛠️ Stack

| | |
|---|---|
| 🐍 **Python 3.13+** | Linguagem principal |
| ⚡ **FastAPI 100% async** | Framework HTTP, Pydantic v2 + pydantic-settings |
| 🗄️ **SQLAlchemy 2.0 async + asyncpg** | ORM assíncrono |
| 🔄 **Alembic** | Migrações (nunca `create_all` em produção) |
| 🐘 **PostgreSQL 16** | Banco de dados (docker-compose local e CI) |
| 🔐 **JWT + bcrypt** | Autenticação e refresh token |
| 🧪 **pytest + pytest-asyncio + httpx** | Testes unitários e de integração |
| 🧹 **ruff + mypy** | Lint e tipagem estática |
| 🚀 **GitHub Actions** | CI desde o primeiro push |

---

## 📦 Estrutura alvo

```
src/
├── main.py               # create_app factory + lifespan + error handlers
├── config.py             # pydantic-settings, fail-fast SECRET_KEY
├── logging_setup.py      # logs JSON + correlation ID
├── database.py           # engine async + session + pool_pre_ping
├── models/               # User, Account, Transaction, IdempotencyKey, AuditLog, RefreshToken
├── schemas/              # Pydantic In/Out + enums
├── services/             # lógica pura, sem HTTP
├── controllers/          # routers /api/v1
├── exceptions.py         # AccountNotFoundError(404), BusinessError(409), IdempotencyConflict(409)
├── security.py           # JWT + bcrypt
├── middleware.py         # request/correlation ID, headers
└── alembic/              # migrações
tests/
├── fixtures/
│   └── factories.py
├── conftest.py
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
pip install -r requirements.txt

# 4. Configuração
cp .env.example .env
# Edite .env: gere uma SECRET_KEY forte

# 5. Cria o schema (migrações Alembic)
alembic upgrade head

# 6. Sobe a API
python -m uvicorn src.main:app --reload
```

Docs interativas: **http://localhost:8000/docs**

---

## 🧪 Testes e qualidade

```powershell
# Testes
python -m pytest

# Cobertura (meta: ≥90%)
python -m pytest --cov=src --cov-report=term-missing

# Lint e formatação
ruff check .
ruff format .

# Tipagem
mypy src
```

---

## 🧱 Módulos (roadmap)

| # | Branch | Foco |
|---|--------|------|
| 0 | `feature/setup` | Fundação, venv, config, logs JSON + correlation ID |
| 1 | `feature/models` | Modelos SQLAlchemy + schemas + fixtures |
| 2 | `feature/db` | Postgres docker-compose + Alembic + migração inicial |
| 3 | `feature/auth` | JWT + refresh token + register/login |
| 4 | `feature/transactions` | Depósito/saque com atomic UPDATE |
| 5 | `feature/transfer` | Transferência com SELECT FOR UPDATE |
| 6 | `feature/audit` | Trilha de auditoria (antes/depois) |
| 7 | `feature/idempotency` | Idempotency-Key (409/replay/corrida) |
| 8 | `feature/statement` | Extrato e consultas |
| 9 | `feature/rate-limit` | Rate limiting |
| 10 | `feature/api` | REST /api/v1 completo |
| 11 | `feature/coverage` | Cobertura de testes ≥90% |
| 12 | `feature/ci` | GitHub Actions |
| 13 | `feature/docs` | README EN/PT |
| 14 | `feature/deploy` | Deploy |

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

## ✔️ Funcionalidades (planejadas)

| Recurso | Descrição |
|---------|-----------|
| **Autenticação** | Register/login com JWT + refresh token rotativo |
| **Contas** | Criação, saldo e consulta de conta |
| **Transações** | Depósito e saque com `UPDATE` atômico |
| **Transferências** | Entre contas com `SELECT FOR UPDATE` (sem corrida) |
| **Auditoria** | Trilha antes/depois de cada operação |
| **Idempotência** | `Idempotency-Key` — replay seguro e sem duplicidade |
| **Extrato** | Histórico paginado e ordenado |
| **Rate limit** | Proteção contra abuso |
| **Logs JSON** | Correlation ID em toda a cadeia de requests |

---

## 🏗️ Arquitetura

Separação rígida de camadas:

- **`models/`** — SQLAlchemy 2.0, `Base(DeclarativeBase)`, mixins `UUIDMixin`/`TimestampMixin`.
- **`schemas/`** — Pydantic In/Out, validação na borda.
- **`services/`** — lógica pura (depósito, saque, transferência), sem HTTP.
- **`controllers/`** — routers `/api/v1`, orquestram services.
- **`exceptions.py`** — `BusinessError(409)`, `AccountNotFoundError(404)`, `IdempotencyConflict(409)`.
- **`main.py`** — `create_app` factory + lifespan + `@app.exception_handler`.
- DRY: funções/mixins compartilhados, nunca lógica duplicada (lição do PyMetrics).

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
| `DATABASE_URL` | `postgresql+asyncpg://pybank:pybank@localhost:5432/pybank` | URL do Postgres |
| `SECRET_KEY` | *(obrigatória)* | Chave JWT — fail-fast se ausente ou `changeme` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Validade do access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Validade do refresh token |
| `RATE_LIMIT_TIMES` | `100` | Requests permitidos por janela |
| `RATE_LIMIT_SECONDS` | `60` | Janela do rate limit (s) |
| `CORS_ORIGINS` | `["http://localhost:8000"]` | Origens CORS (JSON list) |

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