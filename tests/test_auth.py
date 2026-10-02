"""Tests for Inbound API Key Authentication and Security."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_public(async_app_client: AsyncClient):
    """Health endpoint must be public and return healthy status."""
    response = await async_app_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "razorpay-freshdesk-connector"


@pytest.mark.asyncio
async def test_missing_api_key_rejected(async_app_client: AsyncClient):
    """Requests without API key must return 401 Unauthorized."""
    response = await async_app_client.get("/api/v1/tickets")
    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["code"] == "AUTH_HEADER_MISSING"


@pytest.mark.asyncio
async def test_invalid_api_key_rejected(async_app_client: AsyncClient):
    """Requests with incorrect API key must return 401 with INVALID_API_KEY."""
    headers = {"X-API-Key": "wrong_key_12345"}
    response = await async_app_client.get("/api/v1/tickets", headers=headers)
    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["code"] == "INVALID_API_KEY"


@pytest.mark.asyncio
async def test_valid_x_api_key_accepted(async_app_client: AsyncClient, auth_headers: dict):
    """Requests with valid X-API-Key header must succeed."""
    response = await async_app_client.get("/api/v1/tickets", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "data" in payload


@pytest.mark.asyncio
async def test_valid_bearer_token_accepted(async_app_client: AsyncClient, auth_headers: dict):
    """Requests with Authorization: Bearer <key> must also succeed."""
    headers = {"Authorization": f"Bearer {auth_headers['X-API-Key']}"}
    response = await async_app_client.get("/api/v1/tickets", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
