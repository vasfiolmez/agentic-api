import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_empty_task():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/execute",
            json={"task": ""}
        )
        assert response.status_code == 400
        assert "boş" in response.json()["detail"]


@pytest.mark.asyncio
async def test_peer_agent_out_of_scope():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/execute",
            json={
                "task": "Pizza tarifi verir misin?",
                "agent_type": "peer_agent"
            }
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["response_type"] == "out_of_scope"


@pytest.mark.asyncio
async def test_peer_agent_direct_answer():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/execute",
            json={
                "task": "Elektrikli araç sektöründeki güncel trendler nelerdir?",
                "agent_type": "peer_agent"
            }
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["response_type"] == "direct_answer"