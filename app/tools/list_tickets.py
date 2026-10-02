"""Agent Tool Primitive: freshdesk_list_tickets."""

import logging
from typing import Optional, Dict, Any
from app.client.freshdesk_client import get_freshdesk_client, FreshdeskClient
from app.models import TicketListFilter, TicketStatus, TicketPriority, TicketListResponse

logger = logging.getLogger(__name__)


async def list_tickets_tool(
    page: int = 1,
    per_page: int = 10,
    status: Optional[int] = None,
    priority: Optional[int] = None,
    email: Optional[str] = None,
    order_by: str = "created_at",
    order_type: str = "desc",
    client: Optional[FreshdeskClient] = None
) -> Dict[str, Any]:
    """
    Primitive: list_tickets
    Exposed Tool: freshdesk_list_tickets

    Retrieves a paginated list of Freshdesk support tickets for a merchant.
    Allows filtering by status (2=Open, 3=Pending, 4=Resolved, 5=Closed),
    priority (1=Low, 2=Medium, 3=High, 4=Urgent), or requester email.

    Args:
        page: Page number for pagination (starts at 1).
        per_page: Number of tickets per page (1 to 100, default 10).
        status: Status code filter.
        priority: Priority code filter.
        email: Requester email filter.
        order_by: Field name to sort by ('created_at', 'updated_at').
        order_type: Direction ('asc' or 'desc').
        client: Optional FreshdeskClient dependency.

    Returns:
        Structured JSON dictionary containing tickets array, pagination metrics, and rate limit info.
    """
    fd_client = client or get_freshdesk_client()

    filter_params = TicketListFilter(
        page=max(1, page),
        per_page=min(100, max(1, per_page)),
        status=TicketStatus(status) if status is not None else None,
        priority=TicketPriority(priority) if priority is not None else None,
        email=email.strip() if email else None,
        order_by=order_by,
        order_type=order_type
    )

    response: TicketListResponse = await fd_client.list_tickets(filter_params)

    return {
        "success": True,
        "page": response.page,
        "per_page": response.per_page,
        "total_returned": len(response.tickets),
        "has_more": response.has_more,
        "tickets": [t.model_dump() for t in response.tickets],
        "rate_limit": fd_client.last_rate_limit_info.model_dump()
    }
