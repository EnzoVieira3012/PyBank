# Medições — Índice composto do extrato

Contexto: `scripts/seed.py` — 1 user, 2 contas, 10.000 transações (5.000 por conta,
tipos deposit/withdraw/transfer intercalados, `created_at` decrescente a 1 min).

Query medida (extrato com filtros típicos):

```sql
EXPLAIN ANALYZE
SELECT id, type, amount, created_at
FROM transactions
WHERE account_id = '<conta>'          -- 5000 rows
  AND type = 'deposit'
  AND created_at >= '2026-09-01'
  AND created_at <= '2026-09-07'
ORDER BY created_at DESC
LIMIT 20;
```

## Sem índice composto (só `ix_transactions_account_id`)

- Plano: `Bitmap Index Scan` em `account_id` (5000 rows) → `Bitmap Heap Scan` →
  `Filter` (type + período) descartou **3.735 rows** → `Sort` top-N heapsort.
- Execution Time: **0.698 ms**

## Com `ix_transactions_account_created (account_id, created_at DESC)`

- Plano: `Index Scan` com `Index Cond` em `(account_id, created_at >= ... <= ...)`
  → `Filter` residual de `type` descartou só **38 rows** — sem sort (índice já
  entrega a ordem).
- Execution Time: **0.050 ms** (~ **14× mais rápido**).

## Conclusão

O índice composto `(account_id, created_at DESC)` elimina o full scan/filtro do
período e a ordenação: o Postgres resolve conta + janela de tempo direto na
árvore. `ORDER BY created_at DESC` combina com o índice — ordem satisfeita sem sort.
Escala: o ganho cresce com o volume (10k aqui; com milhões de transações o sort
viraria custo dominante).

- Migração: `a183cc6c2083_indice_composto_account_created_at`
- Reproduzir: `python scripts/seed.py` → rodar o EXPLAIN com e sem o índice
  (`alembic downgrade -1` / `upgrade head`).


# Medições — Corrida x100 (concorrência)

Cenário: `tests/integration/test_failure_matrix.py::test_falha_corrida_100_saques_saldo_invariante`.

- 1 conta com saldo 100.00 (`deposit` inicial).
- 100 saques concorrentes de 1.00 cada, disparados via `asyncio.gather` +
  100 `AsyncClient` (cada request com sessão/conexão própria).
- Invariante: 100 sucessos, saldo final 0.00, total transacionado = saldo inicial.
- `SELECT FOR UPDATE` garante lock na linha da conta em ordem determinística
  (`ORDER BY id` na transação). Sem lock haveria oversell (saldo negativo).
- Teste repete o ciclo 5 vezes (4 reabastecimentos + 100 saques) para
  confirmar estabilidade.

| Rodada | Saques 201 | Saldo final | Transações gravadas | Tempo |
|--------|------------|-------------|--------------------|-------|
| 1      | 100/100    | 0.00        | 100 withdrawals    | < 60s |
| 2      | 100/100    | 0.00        | +100 withdrawals   | idem |
| 3      | 100/100    | 0.00        | +100 withdrawals   | idem |
| 4      | 100/100    | 0.00        | +100 withdrawals   | idem |
| 5      | 100/100    | 0.00        | +100 withdrawals   | idem |

`RATE_LIMIT_MUTATIONS` é elevado para 1000 só durante o teste (atributo de
instância do limiter), restaurado pelo `_reset_rate_limiters` autouse no
`conftest.py` — sem isso o teste vazaria o limite customizado para os vizinhos.


# Medições — Cobertura

`pytest --cov=src --cov-report=term-missing`:

| Módulo | Stmts | Miss | Cover |
|--------|-------|------|-------|
| `src/config.py` | 16 | 2 | 88% |
| `src/controllers/accounts.py` | 42 | 1 | 98% |
| `src/controllers/auth.py` | 64 | 3 | 95% |
| `src/controllers/deps.py` | 15 | 0 | 100% |
| `src/controllers/me.py` | 10 | 0 | 100% |
| `src/controllers/statements.py` | 20 | 0 | 100% |
| `src/controllers/transfers.py` | 26 | 0 | 100% |
| `src/database.py` | 13 | 0 | 100% |
| `src/deps.py` | 29 | 4 | 86% |
| `src/exceptions.py` | 13 | 0 | 100% |
| `src/logging_setup.py` | 14 | 0 | 100% |
| `src/main.py` | 71 | 11 | 85% |
| `src/middleware.py` | 20 | 0 | 100% |
| `src/models/*` | 91 | 0 | 100% |
| `src/rate_limit.py` | 41 | 1 | 98% |
| `src/schemas/*` | 53 | 0 | 100% |
| `src/security.py` | 32 | 1 | 97% |
| `src/services/accounts.py` | 43 | 1 | 98% |
| `src/services/idempotency.py` | 38 | 4 | 89% |
| `src/services/statements.py` | 28 | 0 | 100% |
| `src/services/transfers.py` | 47 | 0 | 100% |
| `src/services/audit.py` | 18 | 0 | 100% |
| `src/services/auth.py` | 32 | 0 | 100% |
| **TOTAL** | **745** | **28** | **96%** |

Meta: ≥ 90% — cumprida. Linhas faltantes residem em: validação de SECRET_KEY
no startup, `OPTIONS` no CORS, branch de expiração de Idempotency-Key
(reset de TTL) e import-time branches (TYPE_CHECKING).
