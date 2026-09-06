import asyncio
from decimal import Decimal

import pytest

pytestmark = pytest.mark.asyncio

PASSWORD = "senha-forte-123"


async def _register(client, email: str = "ops@example.com"):
    return await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})


async def _login(client, email: str = "ops@example.com"):
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return r.json()["access_token"]


async def _auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


async def _criar_conta(client, token):
    return await client.post("/api/v1/accounts", headers=await _auth_header(token))


async def test_criar_conta_201(client) -> None:
    await _register(client)
    token = await _login(client)
    response = await _criar_conta(client, token)
    assert response.status_code == 201
    body = response.json()
    assert Decimal(body["balance"]) == Decimal("0.00")
    assert body["id"]


async def test_listar_contas(client) -> None:
    await _register(client)
    token = await _login(client)
    await _criar_conta(client, token)
    await _criar_conta(client, token)
    response = await client.get("/api/v1/accounts", headers=await _auth_header(token))
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_deposito_atualiza_saldo(client) -> None:
    await _register(client)
    token = await _login(client)
    account = (await _criar_conta(client, token)).json()
    response = await client.post(
        f"/api/v1/accounts/{account['id']}/deposits",
        json={"amount": "100.50"},
        headers=await _auth_header(token),
    )
    assert response.status_code == 201
    assert Decimal(response.json()["balance"]) == Decimal("100.50")


async def test_deposito_valor_zero_ou_negativo_422(client) -> None:
    await _register(client)
    token = await _login(client)
    account = (await _criar_conta(client, token)).json()
    for valor in ("0", "-5"):
        response = await client.post(
            f"/api/v1/accounts/{account['id']}/deposits",
            json={"amount": valor},
            headers=await _auth_header(token),
        )
        assert response.status_code == 422, f"valor {valor}"


async def test_saque_atualiza_saldo(client) -> None:
    await _register(client)
    token = await _login(client)
    account = (await _criar_conta(client, token)).json()
    await client.post(
        f"/api/v1/accounts/{account['id']}/deposits",
        json={"amount": "100.00"},
        headers=await _auth_header(token),
    )
    response = await client.post(
        f"/api/v1/accounts/{account['id']}/withdrawals",
        json={"amount": "60.00"},
        headers=await _auth_header(token),
    )
    assert response.status_code == 201
    assert Decimal(response.json()["balance"]) == Decimal("40.00")


async def test_saque_saldo_insuficiente_409(client) -> None:
    await _register(client)
    token = await _login(client)
    account = (await _criar_conta(client, token)).json()
    await client.post(
        f"/api/v1/accounts/{account['id']}/deposits",
        json={"amount": "10.00"},
        headers=await _auth_header(token),
    )
    response = await client.post(
        f"/api/v1/accounts/{account['id']}/withdrawals",
        json={"amount": "20.00"},
        headers=await _auth_header(token),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "insufficient balance"


async def test_sacar_conta_inexistente_404(client) -> None:
    await _register(client)
    token = await _login(client)
    response = await client.post(
        "/api/v1/accounts/00000000-0000-0000-0000-000000000000/withdrawals",
        json={"amount": "10.00"},
        headers=await _auth_header(token),
    )
    assert response.status_code == 404


async def test_conta_de_outro_usuario_parece_404(client) -> None:
    # user1 cria conta; user2 tenta sacar dela -> 404 (nao expoe existencia)
    await _register(client, "dono@example.com")
    tok_dono = await _login(client, "dono@example.com")
    conta = (await _criar_conta(client, tok_dono)).json()

    await _register(client, "invasor@example.com")
    tok_invasor = await _login(client, "invasor@example.com")
    response = await client.post(
        f"/api/v1/accounts/{conta['id']}/withdrawals",
        json={"amount": "5.00"},
        headers=await _auth_header(tok_invasor),
    )
    assert response.status_code == 404


async def test_corrida_saque_nao_ultrapassa_saldo(client) -> None:
    """Conta com 2000. Duas retiradas de 1500 em paralelo. Correto: 1 passa, 1 da 409.
    Se houvesse corrida (read-modify-write), ambas passariam e saldo ficaria -1000
    (violaria CheckConstraint). Prova de que UPDATE atomico respeita o saldo."""
    from sqlalchemy import select

    from src.database import async_session
    from src.exceptions import BusinessError
    from src.models.account import Account
    from src.models.user import User
    from src.services import accounts as svc

    async with async_session() as sess:
        user = User(email="corrida2@example.com", password_hash="abc")
        sess.add(user)
        await sess.commit()
        user_id = user.id
    async with async_session() as sess:
        user = await sess.get(User, user_id)
        account = await svc.criar_conta(sess, user)
        account_id = account.id
        await svc.depositar(sess, account_id, Decimal("2000.00"), user)
        await sess.commit()

    async def retirar():
        async with async_session() as sess:
            user = await sess.get(User, user_id)
            try:
                await svc.sacar(sess, account_id, Decimal("1500.00"), user)
                await sess.commit()
                return "ok"
            except BusinessError:
                return "insufficient"

    results = await asyncio.gather(*[retirar() for _ in range(2)])

    assert results.count("ok") == 1
    assert results.count("insufficient") == 1

    async with async_session() as sess:
        acct = await sess.scalar(select(Account).where(Account.id == account_id))
        assert acct.balance == Decimal("500.00")
