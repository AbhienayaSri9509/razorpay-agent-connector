"""Agent Tool Primitive: freshdesk_search_tickets."""

import logging
from typing import Optional, Dict, Any
from app.client.freshdesk_client import get_freshdesk_client, FreshdeskClient
from app.models import TicketSearchFilter, TicketListResponse

logger = logging.getLogger(__name__)


async def search_tickets_tool(
    query: str,
    page: int = 1,
    client: Optional[FreshdeskClient] = None
) -> Dict[str, Any]:
    """
    Primitive: search_tickets(query)
    Exposed Tool: freshdesk_search_tickets

    Searches support tickets using Freshdesk query syntax, ticket tags, customer email, or keywords.
    Examples of valid search queries:
      - "payment failed"
      - "status:2 AND priority:3"
      - "tag:refund"
      - "pay_OK9832abc"

    Args:
        query: Search query string or keyword.
        page: Page number for pagination (starts at 1).
        client: Optional FreshdeskClient dependency.

    Returns:
        Structured JSON dictionary containing matched tickets, search metrics, and rate limit info.
    """
    if not query or not query.strip():
        return {
            "success": False,
            "error": {
                "code": "INVALID_ARGUMENT",
                "message": "Search query cannot be empty."
            }
        }

    fd_client = client or get_freshdesk_client()

    search_filter = TicketSearchFilter(
        query=query.strip(),
        page=max(1, page)
    )

    try:
        response: TicketListResponse = await fd_client.search_tickets(search_filter)
        return {
            "success": True,
            "query": query,
            "page": response.page,
            "total_matches": response.total,
            "tickets": [t.model_dump() for t in response.tickets],
            "rate_limit": fd_client.last_rate_limit_info.model_dump()
        }
    except Exception as exc:
        logger.error(f"Error executing ticket search for query '{query}': {exc}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "SEARCH_FAILED",
                "message": f"Search failed for query '{query}': {str(exc)}"
            },
            "rate_limit": fd_client.last_rate_limit_info.model_dump()
        }
