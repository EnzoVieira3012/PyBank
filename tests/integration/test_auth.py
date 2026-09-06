import pytest

pytestmark = pytest.mark.asyncio


async def _register(client, email: str = "auth@example.com", password: str = "senha-forte-123"):
    return await client.post("/api/v1/auth/register", json={"email": email, "password": password})


async def _login(client, email: str = "auth@example.com", password: str = "senha-forte-123"):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def test_register_returns_201_with_user(client) -> None:
    response = await _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "auth@example.com"
    assert "password" not in body
    assert "id" in body


async def test_register_duplicate_email_409(client) -> None:
    await _register(client)
    response = await _register(client)
    assert response.status_code == 409
    assert response.json()["detail"] == "email already registered"


async def test_register_short_password_422(client) -> None:
    response = await _register(client, password="curta")
    assert response.status_code == 422


async def test_login_returns_token_pair(client) -> None:
    await _register(client)
    response = await _login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_wrong_password_401(client) -> None:
    await _register(client)
    response = await _login(client, password="senha-errada-1")
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


async def test_login_unknown_email_401_same_message(client) -> None:
    response = await _login(client, email="ninguem@example.com")
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


async def test_me_without_token_401(client) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 401


async def test_me_with_invalid_token_401(client) -> None:
    response = await client.get(
        "/api/v1/me", headers={"Authorization": "Bearer token-invalido-abc"}
    )
    assert response.status_code == 401


async def test_me_with_access_token_200(client) -> None:
    await _register(client)
    tokens = (await _login(client)).json()
    response = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "auth@example.com"


async def test_refresh_rotation_revokes_old_token(client) -> None:
    await _register(client)
    tokens = (await _login(client)).json()
    old_refresh = tokens["refresh_token"]

    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200
    new_tokens = rotated.json()
    assert new_tokens["refresh_token"] != old_refresh

    # Reuso do token antigo (ja rotacionado) -> 401
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401

    # Token novo ainda vale
    again = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert again.status_code == 200


async def test_refresh_with_garbage_token_401(client) -> None:
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "lixo"})
    assert response.status_code == 401


async def test_logout_revokes_refresh_token(client) -> None:
    await _register(client)
    tokens = (await _login(client)).json()

    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 204

    # Refresh apos logout -> 401
    refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401
