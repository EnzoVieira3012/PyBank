import pytest

from src.main import app

pytestmark = pytest.mark.asyncio


async def test_health_returns_ok(client) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_headers_present(client) -> None:
    response = await client.get("/health")
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"


async def test_app_metadata() -> None:
    assert app.title == "PyBank API"
    assert app.version == "1.0.0"
