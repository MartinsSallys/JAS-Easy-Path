import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

HTTP_OK = 200


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == HTTP_OK
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness_check(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == HTTP_OK