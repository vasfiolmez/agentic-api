import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    """API health endpoint test"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_empty_task():
    """Empty task validation test"""
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
    """Non-business request should return out_of_scope"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/execute",
            json={"task": "Can you give me a pizza recipe?"}
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["response_type"] == "out_of_scope"


@pytest.mark.asyncio
async def test_peer_agent_direct_answer():
    """Business knowledge question should return direct_answer"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/execute",
            json={"task": "What are the latest trends in the electric vehicle market?"}
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["response_type"] == "direct_answer"


@pytest.mark.asyncio
async def test_peer_agent_redirect():
    """Business problem should redirect to discovery agent"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/execute",
            json={"task": "Our sales have been declining for 3 months"}
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["response_type"] == "redirect"
        assert result["redirected_to"] == "discovery_agent"


@pytest.mark.asyncio
async def test_code_agent():
    """Code generation request should return code response"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/execute",
            json={"task": "Write a Python function to calculate fibonacci numbers"}
        )
        assert response.status_code == 200
        assert response.json()["agent_type"] == "code_agent"
        result = response.json()["result"]
        assert result["response_type"] == "code"