"""Agent Tool Primitive: freshdesk_get_ticket."""

import logging
from typing import Optional, Dict, Any
from app.client.freshdesk_client import get_freshdesk_client, FreshdeskClient, FreshdeskNotFoundError
from app.models import Ticket

logger = logging.getLogger(__name__)


async def get_ticket_tool(
    ticket_id: int,
    client: Optional[FreshdeskClient] = None
) -> Dict[str, Any]:
    """
    Primitive: get_ticket(ticket_id)
    Exposed Tool: freshdesk_get_ticket

    Retrieves detailed information for a specific Freshdesk support ticket by its numeric ID.

    Args:
        ticket_id: The unique integer ID of the Freshdesk ticket.
        client: Optional FreshdeskClient dependency.

    Returns:
        Structured JSON dictionary with complete ticket metadata, body description, custom fields, and tags.
    """
    if not isinstance(ticket_id, int) or ticket_id <= 0:
        return {
            "success": False,
            "error": {
                "code": "INVALID_ARGUMENT",
                "message": f"ticket_id must be a positive integer, received: {ticket_id}"
            }
        }

    fd_client = client or get_freshdesk_client()

    try:
        ticket: Ticket = await fd_client.get_ticket(ticket_id)
        return {
            "success": True,
            "ticket": ticket.model_dump(),
            "rate_limit": fd_client.last_rate_limit_info.model_dump()
        }
    except FreshdeskNotFoundError as not_found:
        return {
            "success": False,
            "error": {
                "code": "TICKET_NOT_FOUND",
                "message": str(not_found.message)
            },
            "rate_limit": fd_client.last_rate_limit_info.model_dump()
        }
    except Exception as exc:
        logger.error(f"Error fetching ticket #{ticket_id}: {exc}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "FETCH_FAILED",
                "message": f"Failed to retrieve ticket #{ticket_id}: {str(exc)}"
            },
            "rate_limit": fd_client.last_rate_limit_info.model_dump()
        }
