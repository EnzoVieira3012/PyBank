#!/usr/bin/env bash
# Render Web Service - script de start.
# Uso: campo "Build Command" vazio; "Start Command" = ./render_deploy.sh
#
# Licoes de deploy Render:
#   - $PORT vem do ambiente Render; nunca fixar 8000
#   - host 0.0.0.0 obrigatorio (container)
#   - schema SEMPRE via alembic upgrade head; nunca create_all
#   - DATABASE_URL vem do dashboard Render (Postgres separado)
set -euo pipefail

alembic upgrade head
exec python -m uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"