"""API Key validation and authentication dependency for FastAPI and tool endpoints."""

import secrets
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.config import get_settings

api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    header_key: Optional[str] = Security(api_key_header_scheme),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> str:
    """
    Validates that incoming requests contain a valid connector API key.
    Supports either 'X-API-Key: <key>' header or 'Authorization: Bearer <key>'.
    Uses secrets.compare_digest to prevent timing attacks.
    """
    settings = get_settings()
    expected_key = settings.CONNECTOR_API_KEY

    # Check X-API-Key header first, then Bearer token
    provided_key = header_key or (bearer_creds.credentials if bearer_creds else None)

    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_HEADER_MISSING",
                "message": "Missing API Key. Provide 'X-API-Key' header or 'Authorization: Bearer <key>'."
            },
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Constant time comparison
    if not secrets.compare_digest(provided_key.strip(), expected_key.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_API_KEY",
                "message": "Invalid API Key provided. Access denied."
            },
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return provided_key
