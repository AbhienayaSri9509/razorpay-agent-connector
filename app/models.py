"""Domain models, enums, request schemas, and response formats."""

from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TicketStatus(IntEnum):
    """Freshdesk Ticket Status values."""
    OPEN = 2
    PENDING = 3
    RESOLVED = 4
    CLOSED = 5


class TicketPriority(IntEnum):
    """Freshdesk Ticket Priority values."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class TicketSource(IntEnum):
    """Freshdesk Ticket Source channels."""
    EMAIL = 1
    PORTAL = 2
    PHONE = 3
    CHAT = 7
    MFeedback = 9
    OUTBOUND_EMAIL = 10


class Ticket(BaseModel):
    """Freshdesk Ticket representation."""
    id: int = Field(..., description="Unique Freshdesk ticket identifier")
    subject: str = Field(..., description="Subject line of the support ticket")
    description_text: Optional[str] = Field(None, description="Plain text body content")
    description: Optional[str] = Field(None, description="HTML body content")
    status: TicketStatus = Field(default=TicketStatus.OPEN, description="Ticket status code")
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, description="Priority level")
    source: Optional[TicketSource] = Field(default=TicketSource.PORTAL, description="Channel source")
    requester_id: Optional[int] = Field(None, description="User ID of the customer who raised the ticket")
    responder_id: Optional[int] = Field(None, description="Agent ID assigned to the ticket")
    email: Optional[str] = Field(None, description="Email address of the requester")
    created_at: Optional[datetime] = Field(None, description="Timestamp when ticket was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when ticket was last modified")
    tags: List[str] = Field(default_factory=list, description="Associated tags")
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Merchant custom metadata (e.g. order_id, rzp_payment_id)")

    model_config = {"use_enum_values": False}


class TicketListFilter(BaseModel):
    """Query parameters for filtering tickets list."""
    page: int = Field(default=1, ge=1, description="Page number for pagination")
    per_page: int = Field(default=10, ge=1, le=100, description="Number of tickets per page (max 100)")
    status: Optional[TicketStatus] = Field(None, description="Filter by status")
    priority: Optional[TicketPriority] = Field(None, description="Filter by priority")
    email: Optional[str] = Field(None, description="Filter by requester email")
    order_by: Optional[str] = Field("created_at", description="Field to sort by (created_at, updated_at, due_by)")
    order_type: Optional[str] = Field("desc", description="Sort order: 'asc' or 'desc'")


class TicketSearchFilter(BaseModel):
    """Parameters for searching Freshdesk tickets."""
    query: str = Field(..., min_length=1, description="Freshdesk search query syntax (e.g. 'status:2 AND priority:3' or keyword)")
    page: int = Field(default=1, ge=1, description="Page number")


class TicketListResponse(BaseModel):
    """Standardized response for ticket listing."""
    total: int = Field(..., description="Number of tickets in current page")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    tickets: List[Ticket] = Field(default_factory=list, description="List of tickets")
    has_more: bool = Field(default=False, description="Whether more tickets are available")


class RateLimitInfo(BaseModel):
    """Rate limit status details."""
    remaining: int = Field(..., description="Remaining requests in window")
    total_limit: int = Field(..., description="Total rate limit allowance")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retrying")


class APIResponse(BaseModel):
    """Uniform wrapper for connector responses."""
    success: bool = True
    data: Any = None
    message: Optional[str] = None
    rate_limit: Optional[RateLimitInfo] = None


class ErrorDetail(BaseModel):
    """Structured error payload."""
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error explanation")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional context or validation details")
