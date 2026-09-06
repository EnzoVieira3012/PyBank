"""Regressao: mutacoes visiveis IMEDIATAMENTE apos a resposta.
Bug de producao (achado no smoke de deploy): get_session commitava no
teardown (depois do yield/response do FastAPI); register+login em rajada
falhava ~1/5 com 401 (login nao enxergava o user ainda nao commitado).
Fix: commit explicito em toda rota mutante (auth, accounts, transfers).
"""

import time

import httpx

API = "/api/v1"


def _new_email() -> str:
    return f"vis-{int(time.time() * 1000)}-{id(object())}@pybank.dev"


async def test_mutation_visible_immediately(client: httpx.AsyncClient) -> None:
    """Burst register->login / deposit->saldo sem pausa: 100% 200."""
    for _ in range(8):
        email, pw = _new_email(), "Str0ng!Pass123"
        r = await client.post(
            f"{API}/auth/register", json={"email": email, "password": pw, "full_name": "Vis"}
        )
        assert r.status_code == 201, f"register {r.status_code}: {r.text}"

        r = await client.post(f"{API}/auth/login", json={"email": email, "password": pw})
        assert r.status_code == 200, (
            f"login logo apos register {r.status_code}: {r.text} — commit nao visivel"
        )
        tok = r.json()["access_token"]
        auth = {"Authorization": f"Bearer {tok}"}

        r = await client.post(f"{API}/accounts", headers=auth)
        assert r.status_code == 201, f"create account {r.status_code}: {r.text}"
        aid = r.json()["id"]

        r = await client.post(
            f"{API}/accounts/{aid}/deposits",
            headers={**auth, "Idempotency-Key": f"vis-{email}"},
            json={"amount": 10.0},
        )
        assert r.status_code == 201, f"deposit {r.status_code}: {r.text}"

        r = await client.get(f"{API}/accounts", headers=auth)
        cur = next(a for a in r.json() if a["id"] == str(aid))
        assert float(cur["balance"]) == 10.0, f"saldo imediato incorreto: {cur['balance']}"
