"""Unit tests for Ticket tools, REST endpoints, and MCP tool dispatch."""

import pytest
from httpx import AsyncClient

from app.tools.list_tickets import list_tickets_tool
from app.tools.get_ticket import get_ticket_tool
from app.tools.search_tickets import search_tickets_tool
from app.models import TicketStatus, TicketPriority
from mcp.server import dispatch_tool


# ==========================================
# Tool Primitives Direct Unit Tests
# ==========================================

@pytest.mark.asyncio
async def test_list_tickets_tool_defaults(mock_client):
    """Test list_tickets_tool returns tickets with pagination info."""
    result = await list_tickets_tool(client=mock_client)
    assert result["success"] is True
    assert result["page"] == 1
    assert result["per_page"] == 10
    assert result["total_returned"] >= 5
    assert len(result["tickets"]) >= 5


@pytest.mark.asyncio
async def test_list_tickets_tool_filter_status(mock_client):
    """Test filtering tickets by status (e.g. Open=2)."""
    result = await list_tickets_tool(status=TicketStatus.OPEN, client=mock_client)
    assert result["success"] is True
    for ticket in result["tickets"]:
        assert ticket["status"] == TicketStatus.OPEN


@pytest.mark.asyncio
async def test_list_tickets_tool_filter_priority(mock_client):
    """Test filtering tickets by priority (e.g. Urgent=4)."""
    result = await list_tickets_tool(priority=TicketPriority.URGENT, client=mock_client)
    assert result["success"] is True
    assert len(result["tickets"]) == 1
    assert result["tickets"][0]["id"] == 1002


@pytest.mark.asyncio
async def test_list_tickets_tool_pagination(mock_client):
    """Test pagination bounds with per_page=2."""
    page1 = await list_tickets_tool(page=1, per_page=2, client=mock_client)
    assert len(page1["tickets"]) == 2
    assert page1["has_more"] is True

    page2 = await list_tickets_tool(page=2, per_page=2, client=mock_client)
    assert len(page2["tickets"]) == 2
    # Distinct items across pages
    assert page1["tickets"][0]["id"] != page2["tickets"][0]["id"]


@pytest.mark.asyncio
async def test_get_ticket_tool_success(mock_client):
    """Test fetching an existing ticket by ID."""
    result = await get_ticket_tool(ticket_id=1001, client=mock_client)
    assert result["success"] is True
    ticket = result["ticket"]
    assert ticket["id"] == 1001
    assert "pay_OK9832abc" in ticket["description_text"]
    assert ticket["custom_fields"]["cf_rzp_payment_id"] == "pay_OK9832abc"


@pytest.mark.asyncio
async def test_get_ticket_tool_not_found(mock_client):
    """Test fetching a non-existent ticket returns structured error."""
    result = await get_ticket_tool(ticket_id=99999, client=mock_client)
    assert result["success"] is False
    assert result["error"]["code"] == "TICKET_NOT_FOUND"


@pytest.mark.asyncio
async def test_search_tickets_tool_keyword(mock_client):
    """Test searching tickets by keyword 'webhook'."""
    result = await search_tickets_tool(query="webhook", client=mock_client)
    assert result["success"] is True
    assert result["total_matches"] >= 1
    assert any("webhook" in t["subject"].lower() for t in result["tickets"])


@pytest.mark.asyncio
async def test_search_tickets_tool_empty(mock_client):
    """Test search with empty query returns validation error."""
    result = await search_tickets_tool(query="  ", client=mock_client)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


# ==========================================
# REST API Endpoint Tests
# ==========================================

@pytest.mark.asyncio
async def test_api_list_tickets(async_app_client: AsyncClient, auth_headers: dict):
    """Test GET /api/v1/tickets endpoint with auth."""
    response = await async_app_client.get("/api/v1/tickets?page=1&per_page=5", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["tickets"]) >= 5


@pytest.mark.asyncio
async def test_api_get_ticket_found(async_app_client: AsyncClient, auth_headers: dict):
    """Test GET /api/v1/tickets/{id} endpoint with existing ticket."""
    response = await async_app_client.get("/api/v1/tickets/1001", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["ticket"]["id"] == 1001


@pytest.mark.asyncio
async def test_api_get_ticket_not_found(async_app_client: AsyncClient, auth_headers: dict):
    """Test GET /api/v1/tickets/{id} endpoint with missing ticket -> 404."""
    response = await async_app_client.get("/api/v1/tickets/99999", headers=auth_headers)
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["data"]["code"] == "TICKET_NOT_FOUND"


@pytest.mark.asyncio
async def test_api_search_tickets(async_app_client: AsyncClient, auth_headers: dict):
    """Test GET /api/v1/tickets/search endpoint with query."""
    response = await async_app_client.get("/api/v1/tickets/search?query=refund", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["total_matches"] >= 1


# ==========================================
# MCP Dispatcher Tests
# ==========================================

@pytest.mark.asyncio
async def test_mcp_dispatcher_list():
    """Test MCP tool dispatcher for freshdesk_list_tickets."""
    res = await dispatch_tool("freshdesk_list_tickets", {"page": 1, "per_page": 2})
    assert res["success"] is True
    assert len(res["tickets"]) == 2


@pytest.mark.asyncio
async def test_mcp_dispatcher_get():
    """Test MCP tool dispatcher for freshdesk_get_ticket."""
    res = await dispatch_tool("freshdesk_get_ticket", {"ticket_id": 1002})
    assert res["success"] is True
    assert res["ticket"]["id"] == 1002


@pytest.mark.asyncio
async def test_mcp_dispatcher_unknown():
    """Test MCP tool dispatcher with unrecognized tool name."""
    res = await dispatch_tool("unknown_tool", {})
    assert res["success"] is False
    assert res["error"]["code"] == "UNKNOWN_TOOL"
