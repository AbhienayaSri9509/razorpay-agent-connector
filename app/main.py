"""FastAPI Application for Razorpay Freshdesk Agent Connector."""

import logging
from typing import Optional
from fastapi import FastAPI, Depends, Query, Path, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.api_key import verify_api_key
from app.config import get_settings
from app.client.freshdesk_client import (
    get_freshdesk_client,
    FreshdeskError,
    FreshdeskAuthError,
    FreshdeskNotFoundError,
    FreshdeskRateLimitError,
    FreshdeskServerError
)
from app.models import APIResponse, ErrorDetail, TicketStatus, TicketPriority
from app.tools.list_tickets import list_tickets_tool
from app.tools.get_ticket import get_ticket_tool
from app.tools.search_tickets import search_tickets_tool

# Setup Logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("razorpay-connector")

app = FastAPI(
    title="Razorpay Merchant Connector: Freshdesk",
    description="Production-grade AI Agent connector bridging Razorpay support bots to merchant Freshdesk workspaces.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# Global Exception Handlers
# ==========================================

@app.exception_handler(FreshdeskAuthError)
async def auth_exception_handler(request, exc: FreshdeskAuthError):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=APIResponse(
            success=False,
            message="Freshdesk upstream authentication failed",
            data=ErrorDetail(code="UPSTREAM_AUTH_ERROR", message=exc.message).model_dump()
        ).model_dump()
    )

@app.exception_handler(FreshdeskNotFoundError)
async def not_found_exception_handler(request, exc: FreshdeskNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=APIResponse(
            success=False,
            message="Requested ticket was not found",
            data=ErrorDetail(code="TICKET_NOT_FOUND", message=exc.message).model_dump()
        ).model_dump()
    )

@app.exception_handler(FreshdeskRateLimitError)
async def rate_limit_exception_handler(request, exc: FreshdeskRateLimitError):
    headers = {}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers=headers,
        content=APIResponse(
            success=False,
            message="Rate limit exceeded",
            data=ErrorDetail(code="RATE_LIMIT_EXCEEDED", message=exc.message, details={"retry_after": exc.retry_after}).model_dump()
        ).model_dump()
    )

@app.exception_handler(FreshdeskServerError)
async def server_exception_handler(request, exc: FreshdeskServerError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=APIResponse(
            success=False,
            message="Upstream Freshdesk server error",
            data=ErrorDetail(code="UPSTREAM_SERVER_ERROR", message=exc.message).model_dump()
        ).model_dump()
    )


# ==========================================
# Health & Status Endpoints (Public)
# ==========================================

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint indicating connector operational status."""
    fd_client = get_freshdesk_client()
    return {
        "status": "healthy",
        "service": "razorpay-freshdesk-connector",
        "mock_mode": settings.FRESHDESK_MOCK_MODE,
        "environment": settings.ENVIRONMENT,
        "rate_limit": fd_client.last_rate_limit_info.model_dump()
    }


# ==========================================
# Protected Agent Tool REST Endpoints
# ==========================================

@app.get("/api/v1/tickets", response_model=APIResponse, tags=["Tickets"], dependencies=[Depends(verify_api_key)])
async def list_tickets(
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=10, ge=1, le=100, description="Items per page"),
    status: Optional[int] = Query(default=None, description="Ticket status (2=Open, 3=Pending, 4=Resolved, 5=Closed)"),
    priority: Optional[int] = Query(default=None, description="Ticket priority (1=Low, 2=Med, 3=High, 4=Urgent)"),
    email: Optional[str] = Query(default=None, description="Customer email filter"),
    order_by: str = Query(default="created_at", description="Field to sort by"),
    order_type: str = Query(default="desc", description="Sort order: 'asc' or 'desc'")
):
    """
    Exposes `freshdesk_list_tickets` tool as a REST endpoint.
    Requires inbound `X-API-Key` authentication.
    """
    result = await list_tickets_tool(
        page=page,
        per_page=per_page,
        status=status,
        priority=priority,
        email=email,
        order_by=order_by,
        order_type=order_type
    )
    return APIResponse(
        success=result["success"],
        data=result
    )


@app.get("/api/v1/tickets/search", response_model=APIResponse, tags=["Tickets"], dependencies=[Depends(verify_api_key)])
async def search_tickets(
    query: str = Query(..., min_length=1, description="Search query or keywords"),
    page: int = Query(default=1, ge=1, description="Page number")
):
    """
    Exposes `freshdesk_search_tickets` tool as a REST endpoint.
    Requires inbound `X-API-Key` authentication.
    """
    result = await search_tickets_tool(query=query, page=page)
    return APIResponse(
        success=result.get("success", False),
        data=result
    )


@app.get("/api/v1/tickets/{ticket_id}", response_model=APIResponse, tags=["Tickets"], dependencies=[Depends(verify_api_key)])
async def get_ticket(
    ticket_id: int = Path(..., ge=1, description="Numeric ticket ID")
):
    """
    Exposes `freshdesk_get_ticket` tool as a REST endpoint.
    Requires inbound `X-API-Key` authentication.
    """
    result = await get_ticket_tool(ticket_id=ticket_id)
    if not result.get("success"):
        error_code = result.get("error", {}).get("code")
        if error_code == "TICKET_NOT_FOUND":
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=APIResponse(
                    success=False,
                    message=f"Ticket #{ticket_id} not found",
                    data=result.get("error")
                ).model_dump()
            )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=APIResponse(
                success=False,
                message="Failed to retrieve ticket",
                data=result.get("error")
            ).model_dump()
        )
    return APIResponse(
        success=True,
        data=result
    )
