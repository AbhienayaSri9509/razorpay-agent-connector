"""Configuration management using Pydantic Settings."""

import os
from functools import lru_cache
from typing import Optional
from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    USE_PYDANTIC_SETTINGS_V2 = True
except ImportError:
    from pydantic import BaseSettings
    USE_PYDANTIC_SETTINGS_V2 = False


if USE_PYDANTIC_SETTINGS_V2:
    class Settings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore"
        )

        # Freshdesk Configuration
        FRESHDESK_DOMAIN: str = Field(default="demo-merchant.freshdesk.com", description="Freshdesk merchant domain")
        FRESHDESK_API_KEY: str = Field(default="mock_api_key", description="Freshdesk API key")
        
        # Inbound Connector Security
        CONNECTOR_API_KEY: str = Field(default="rzp_agent_secret_key_987654321", description="Inbound API Key for Agents")
        
        # Mock Mode
        FRESHDESK_MOCK_MODE: bool = Field(default=True, description="Enable mock data for testing/demo without live credentials")
        
        # Network & Resilience
        ENVIRONMENT: str = Field(default="development", description="Runtime environment")
        LOG_LEVEL: str = Field(default="INFO", description="Logging level")
        REQUEST_TIMEOUT_SECONDS: float = Field(default=10.0, description="HTTP client timeout in seconds")
        MAX_RETRIES: int = Field(default=3, description="Max retry attempts on 429/5xx")
        RATE_LIMIT_PER_MINUTE: int = Field(default=50, description="Client-side rate limit per minute")

        @property
        def freshdesk_base_url(self) -> str:
            domain = self.FRESHDESK_DOMAIN.strip().rstrip("/")
            if not domain.startswith("http://") and not domain.startswith("https://"):
                return f"https://{domain}/api/v2"
            return f"{domain}/api/v2"
else:
    class Settings(BaseSettings):  # type: ignore
        FRESHDESK_DOMAIN: str = "demo-merchant.freshdesk.com"
        FRESHDESK_API_KEY: str = "mock_api_key"
        CONNECTOR_API_KEY: str = "rzp_agent_secret_key_987654321"
        FRESHDESK_MOCK_MODE: bool = True
        ENVIRONMENT: str = "development"
        LOG_LEVEL: str = "INFO"
        REQUEST_TIMEOUT_SECONDS: float = 10.0
        MAX_RETRIES: int = 3
        RATE_LIMIT_PER_MINUTE: int = 50

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"

        @property
        def freshdesk_base_url(self) -> str:
            domain = self.FRESHDESK_DOMAIN.strip().rstrip("/")
            if not domain.startswith("http://") and not domain.startswith("https://"):
                return f"https://{domain}/api/v2"
            return f"{domain}/api/v2"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
