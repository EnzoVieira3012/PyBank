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