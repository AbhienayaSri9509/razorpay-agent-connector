"""Pytest configuration, async fixtures, and mock test harnesses."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import Settings, get_settings
from app.client.freshdesk_client import FreshdeskClient

TEST_API_KEY = "rzp_agent_secret_key_987654321"


@pytest.fixture
def test_settings() -> Settings:
    """Fixture providing known test configuration."""
    return Settings(
        FRESHDESK_DOMAIN="test-merchant.freshdesk.com",
        FRESHDESK_API_KEY="test_fd_key",
        CONNECTOR_API_KEY=TEST_API_KEY,
        FRESHDESK_MOCK_MODE=True,
        ENVIRONMENT="test",
        REQUEST_TIMEOUT_SECONDS=5.0,
        MAX_RETRIES=2,
        RATE_LIMIT_PER_MINUTE=60
    )


@pytest.fixture
def auth_headers() -> dict:
    """Valid auth headers fixture."""
    return {"X-API-Key": TEST_API_KEY}


@pytest.fixture
def mock_client(test_settings: Settings) -> FreshdeskClient:
    """FreshdeskClient in mock mode."""
    return FreshdeskClient(settings=test_settings)


@pytest_asyncio.fixture
async def async_app_client():
    """Async HTTP test client for FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
