"""Model Context Protocol (MCP) Server for Freshdesk Agent Connector.

This module exposes the Freshdesk merchant primitives as standard MCP tools
that can be plugged into Claude Desktop, Cursor, LangChain, or any MCP-compatible agent.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, Optional

from app.tools.list_tickets import list_tickets_tool
from app.tools.get_ticket import get_ticket_tool
from app.tools.search_tickets import search_tickets_tool

logger = logging.getLogger("freshdesk-mcp-server")

# ==========================================
# MCP Server Implementation
# ==========================================

try:
    from mcp.server.fastmcp import FastMCP
    mcp_app = FastMCP("Freshdesk Merchant Connector")

    @mcp_app.tool(name="freshdesk_list_tickets", description="List support tickets from Freshdesk with pagination and status/priority filters.")
    async def mcp_list_tickets(
        page: int = 1,
        per_page: int = 10,
        status: Optional[int] = None,
        priority: Optional[int] = None,
        email: Optional[str] = None
    ) -> str:
        """List tickets from Freshdesk.
        status: 2=Open, 3=Pending, 4=Resolved, 5=Closed.
        priority: 1=Low, 2=Medium, 3=High, 4=Urgent.
        """
        result = await list_tickets_tool(
            page=page,
            per_page=per_page,
            status=status,
            priority=priority,
            email=email
        )
        return json.dumps(result, indent=2)

    @mcp_app.tool(name="freshdesk_get_ticket", description="Retrieve full ticket details and conversation context by numeric ticket ID.")
    async def mcp_get_ticket(ticket_id: int) -> str:
        """Fetch a specific Freshdesk ticket by ticket_id."""
        result = await get_ticket_tool(ticket_id=ticket_id)
        return json.dumps(result, indent=2)

    @mcp_app.tool(name="freshdesk_search_tickets", description="Search Freshdesk tickets using keywords, payment IDs, email, or query syntax.")
    async def mcp_search_tickets(query: str, page: int = 1) -> str:
        """Search Freshdesk tickets with query string."""
        result = await search_tickets_tool(query=query, page=page)
        return json.dumps(result, indent=2)

    HAS_FASTMCP = True
except Exception as mcp_init_err:
    HAS_FASTMCP = False
    mcp_app = None


# ==========================================
# Tool Manifest (Standard Schema)
# ==========================================

MCP_TOOL_DEFINITIONS = [
    {
        "name": "freshdesk_list_tickets",
        "description": "List Freshdesk support tickets with pagination, status, and priority filtering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page": {"type": "integer", "default": 1, "description": "Page number (1-based)"},
                "per_page": {"type": "integer", "default": 10, "description": "Number of tickets per page (1-100)"},
                "status": {"type": "integer", "enum": [2, 3, 4, 5], "description": "2=Open, 3=Pending, 4=Resolved, 5=Closed"},
                "priority": {"type": "integer", "enum": [1, 2, 3, 4], "description": "1=Low, 2=Medium, 3=High, 4=Urgent"},
                "email": {"type": "string", "description": "Filter by requester customer email"}
            }
        }
    },
    {
        "name": "freshdesk_get_ticket",
        "description": "Get detailed information for a single Freshdesk support ticket by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The unique integer ID of the Freshdesk ticket"}
            },
            "required": ["ticket_id"]
        }
    },
    {
        "name": "freshdesk_search_tickets",
        "description": "Search Freshdesk tickets using keywords, order IDs, payment IDs, or Freshdesk query syntax.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search string or keyword (e.g. 'pay_OK9832abc' or 'status:2')"},
                "page": {"type": "integer", "default": 1, "description": "Page number"}
            },
            "required": ["query"]
        }
    }
]


async def dispatch_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Universal dispatcher for tool calls."""
    if name == "freshdesk_list_tickets":
        return await list_tickets_tool(
            page=arguments.get("page", 1),
            per_page=arguments.get("per_page", 10),
            status=arguments.get("status"),
            priority=arguments.get("priority"),
            email=arguments.get("email")
        )
    elif name == "freshdesk_get_ticket":
        return await get_ticket_tool(
            ticket_id=arguments.get("ticket_id")
        )
    elif name == "freshdesk_search_tickets":
        return await search_tickets_tool(
            query=arguments.get("query", ""),
            page=arguments.get("page", 1)
        )
    else:
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_TOOL",
                "message": f"Tool '{name}' is not recognized by Freshdesk connector."
            }
        }


# ==========================================
# CLI / JSON-RPC Stdio Runner
# ==========================================

async def run_stdio_jsonrpc():
    """Runs a lightweight stdio JSON-RPC loop for Agent CLI integrations."""
    sys.stderr.write("Razorpay Freshdesk MCP Server started (Stdio Mode).\n")
    sys.stderr.flush()

    while True:
        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "tools/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": MCP_TOOL_DEFINITIONS}
                }
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                result_content = await dispatch_tool(tool_name, tool_args)
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": json.dumps(result_content, indent=2)}
                        ]
                    }
                }
            else:
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
            
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        except Exception as err:
            err_res = {
                "jsonrpc": "2.0",
                "id": req.get("id") if 'req' in locals() else None,
                "error": {"code": -32603, "message": str(err)}
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()


def main():
    """Main entrypoint for MCP Server."""
    if HAS_FASTMCP and "--fastmcp" in sys.argv:
        mcp_app.run()
    else:
        asyncio.run(run_stdio_jsonrpc())


if __name__ == "__main__":
    main()
