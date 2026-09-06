from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update

pytestmark = pytest.mark.asyncio

PASSWORD = "senha-forte-123"
BASE = datetime(2026, 9, 1, 10, 0, 0)


async def _register(client, email: str = "extrato@example.com"):
    return await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})


async def _login(client, email: str = "extrato@example.com"):
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return r.json()["access_token"]


async def _auth_header(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": str(uuid4()),  # mutaveis exigem key; chave unica por request
    }


async def _criar_conta(client, token):
    return await client.post("/api/v1/accounts", headers=await _auth_header(token))


async def _depositar(client, token, account_id, amount):
    return await client.post(
        f"/api/v1/accounts/{account_id}/deposits",
        json={"amount": amount},
        headers=await _auth_header(token),
    )


async def _sacar(client, token, account_id, amount):
    return await client.post(
        f"/api/v1/accounts/{account_id}/withdrawals",
        json={"amount": amount},
        headers=await _auth_header(token),
    )


async def _set_created_at(account_id: str, datetimes: list[datetime]) -> None:
    """Fixar created_at dos lancamentos da conta (ordem cronologica) p/ testar
    filtros de data com bandas deterministas."""
    from src.database import engine
    from src.models.transaction import Transaction

    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                select(Transaction.id, Transaction.created_at)
                .where(Transaction.account_id == account_id)
                .order_by(Transaction.created_at)
            )
        ).all()
        assert len(rows) == len(datetimes), "quantidade de lancamentos difere da lista de datas"
        for (txn_id, _), dt in zip(rows, datetimes):
            await conn.execute(update(Transaction).where(Transaction.id == txn_id).values(created_at=dt))
        await conn.commit()


async def test_extrato_pagina_1_meta(client) -> None:
    await _register(client)
    token = await _login(client)
    account = (await _criar_conta(client, token)).json()
    for valor in ("10.00", "20.00", "30.00"):
        assert (await _depositar(client, token, account["id"], valor)).status_code == 201

    response = await client.get(
        f"/api/v1/accounts/{account['id']}/statement", headers=await _auth_header(token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["account_id"] == account["id"]
    assert len(body["items"]) == 3
    assert body["meta"] == {"page": 1, "page_size": 20, "total_items": 3, "total_pages": 1}
    for item in body["items"]:
        assert item["type"] == "deposit"
        assert item["amount"] in ("10.00", "20.00", "30.00")
        assert item["id"]


async def test_extrato_paginacao_ordem(client) -> None:
    await _register(client)
    token = await _login(client)
    account = (await _criar_conta(client, token)).json()
    for valor in ("1.00", "2.00", "3.00", "4.00", "5.00"):
        assert (await _depositar(client, token, account["id"], valor)).status_code == 201
    await _set_created_at(
        account["id"],
        [BASE + timedelta(minutes=i) for i in range(5)],  # 1o lanco = mais antigo
    )

    page1 = (
        await client.get(
            f"/api/v1/accounts/{account['id']}/statement?page=1&page_size=2",
            headers=await _auth_header(token),
        )
    ).json()
    page2 = (
        await client.get(
            f"/api/v1/accounts/{account['id']}/statement?page=2&page_size=2",
            headers=await _auth_header(token),
        )
    ).json()
    page3 = (
        await client.get(
            f"/api/v1/accounts/{account['id']}/statement?page=3&page_size=2",
            headers=await _auth_header(token),
        )
    ).json()

    # mais recentes primeiro: pag1 = lancos 5 e 4; pag2 = 3 e 2; pag3 = 1
    assert [i["amount"] for i in page1["items"]] == ["5.00", "4.00"]
    assert [i["amount"] for i in page2["items"]] == ["3.00", "2.00"]
    assert [i["amount"] for i in page3["items"]] == ["1.00"]
    for page in (page1, page2, page3):
        assert page["meta"]["total_items"] == 5
        assert page["meta"]["total_pages"] == 3


async def test_extrato_filtro_tipo(client) -> None:
    await _register(client)
    token = await _login(client)
    account = (await _criar_conta(client, token)).json()
    for valor in ("10.00", "20.00", "30.00"):
        assert (await _depositar(client, token, account["id"], valor)).status_code == 201
    assert (await _sacar(client, token, account["id"], "5.00")).status_code == 201

    response = await client.get(
        f"/api/v1/accounts/{account['id']}/statement?type=deposit",
        headers=await _auth_header(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 3
    assert all(i["type"] == "deposit" for i in body["items"])

    response = await client.get(
        f"/api/v1/accounts/{account['id']}/statement?type=withdraw",
        headers=await _auth_header(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["amount"] == "5.00"


async def test_extrato_from_inclusivo(client) -> None:
    await _register(client)
    token = await _login(client)
    account = (await _criar_conta(client, token)).json()
    for valor in ("10.00", "20.00"):
        assert (await _depositar(client, token, account["id"], valor)).status_code == 201
    await _set_created_at(account["id"], [BASE, BASE + timedelta(minutes=30)])

    # from == created_at do primeiro -> inclui os dois (boundary inclusiva)
    response = await client.get(
        f"/api/v1/accounts/{account['id']}/statement?from={BASE.isoformat()}",
        headers=await _auth_header(token),
    )
    assert response.status_code == 200
    assert response.json()["meta"]["total_items"] == 2

    # from entre os dois -> so o mais novo
    response = await client.get(
        f"/api/v1/accounts/{account['id']}/statement?from={(BASE + timedelta(minutes=15)).isoformat()}",
        headers=await _auth_header(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["amount"] == "20.00"


async def test_extrato_to_inclusivo(client) -> None:
    await _register(client)
    token = await _login(client)
    account = (await _criar_conta(client, token)).json()
    for valor in ("10.00", "20.00"):
        assert (await _depositar(client, token, account["id"], valor)).status_code == 201
    await _set_created_at(account["id"], [BASE, BASE + timedelta(minutes=30)])

    # to == created_at do segundo -> inclui os dois (boundary inclusiva)
    response = await client.get(
        f"/api/v1/accounts/{account['id']}/statement?to={(BASE + timedelta(minutes=30)).isoformat()}",
        headers=await _auth_header(token),
    )
    assert response.status_code == 200
    assert response.json()["meta"]["total_items"] == 2

    # to entre os dois -> so o mais antigo
    response = await client.get(
        f"/api/v1/accounts/{account['id']}/statement?to={(BASE + timedelta(minutes=15)).isoformat()}",
        headers=await _auth_header(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["amount"] == "10.00"


async def test_extrato_conta_outro_usuario_404(client) -> None:
    await _register(client, "dono@example.com")
    tok_dono = await _login(client, "dono@example.com")
    conta = (await _criar_conta(client, tok_dono)).json()

    await _register(client, "invasor@example.com")
    tok_invasor = await _login(client, "invasor@example.com")
    response = await client.get(
        f"/api/v1/accounts/{conta['id']}/statement", headers=await _auth_header(tok_invasor)
    )
    assert response.status_code == 404


async def test_extrato_page_invalida_422(client) -> None:
    await _register(client)
    token = await _login(client)
    account = (await _criar_conta(client, token)).json()
    response = await client.get(
        f"/api/v1/accounts/{account['id']}/statement?page=0",
        headers=await _auth_header(token),
    )
    assert response.status_code == 422


async def test_extrato_page_size_invalida_422(client) -> None:
    await _register(client)
    token = await _login(client)
    account = (await _criar_conta(client, token)).json()
    for page_size in ("0", "200"):
        response = await client.get(
            f"/api/v1/accounts/{account['id']}/statement?page_size={page_size}",
            headers=await _auth_header(token),
        )
        assert response.status_code == 422, f"page_size {page_size}"