"""Agregador central de rotas — APIRouter unico montado na factory.

Cada controller declara seu prefixo (/api/v1/...) e tags; este modulo
apenas agrega. main.py inclui somente `api_router`.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.controllers import accounts, auth, me, statements, transfers

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(accounts.router)
api_router.include_router(transfers.router)
api_router.include_router(statements.router)
api_router.include_router(me.router)
