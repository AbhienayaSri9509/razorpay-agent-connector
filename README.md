# Razorpay Agent Connector: Freshdesk Merchant Gateway

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![MCP](https://img.shields.io/badge/MCP-Protocol-purple.svg)](https://modelcontextprotocol.io/)
[![Tests](https://img.shields.io/badge/Tests-Pytest%20Passing-brightgreen.svg)]()

> A robust, production-grade private merchant connector bridging **AI Agents** (via Model Context Protocol - MCP) and **Razorpay Support Workflows** (via FastAPI REST) to merchant Freshdesk workspaces.

---

## 🌟 Key Features

- **MCP-Native & REST Dual Interface**: Exposes agent tools (`freshdesk_list_tickets`, `freshdesk_get_ticket`, `freshdesk_search_tickets`) over standard Model Context Protocol (stdio/FastMCP) and authenticated REST endpoints.
- **Inbound Security**: Multi-scheme authentication supporting `X-API-Key` headers and `Bearer` tokens with constant-time cryptographic verification to prevent timing attacks.
- **Proactive Rate Limiting**: Built-in **Token Bucket Rate Limiter** to prevent hitting merchant API tier limits.
- **Resilience & Fault Tolerance**: Exponential backoff with full jitter and automatic `Retry-After` header parsing for upstream HTTP 429 and 5xx errors.
- **Zero-Dependency Mock/Demo Mode**: Ships with synthetic merchant support tickets (payment failures, webhook signature errors, auto-refund inquiries) for instant local testing without live Freshdesk credentials.
- **Strict Guardrails**: Read-only safety constraints preventing unauthorized data mutations or credential leakage.

---

## 📂 Repository Structure

```
razorpay-agent-connector/
│
├── README.md                          # Main project guide and documentation
├── requirements.txt                   # Dependency specifications
├── .env.example                       # Environment template
│
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI application entrypoint
│   ├── config.py                      # Pydantic Settings management
│   ├── models.py                      # Domain schemas, enums & response wrappers
│   ├── rate_limit.py                  # Token Bucket & Exponential Backoff engine
│   ├── auth/
│   │   ├── __init__.py
│   │   └── api_key.py                 # Inbound API key verification dependency
│   ├── client/
│   │   ├── __init__.py
│   │   └── freshdesk_client.py        # Async Freshdesk client + Mock Dataset
│   └── tools/
│       ├── __init__.py
│       ├── list_tickets.py            # freshdesk_list_tickets primitive
│       ├── get_ticket.py              # freshdesk_get_ticket primitive
│       └── search_tickets.py          # freshdesk_search_tickets primitive
│
├── mcp/
│   ├── __init__.py
│   └── server.py                      # Model Context Protocol (MCP) server
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Pytest fixtures & async test client
│   ├── test_auth.py                   # Authentication unit tests
│   ├── test_tickets.py                # Tools and REST endpoint tests
│   └── test_rate_limit.py             # Rate limiter & backoff unit tests
│
├── docs/
│   ├── architecture.md                # Detailed system architecture & design
│   └── agent-capabilities.md          # Tool contracts, capabilities & guardrails
│
└── demo/
    └── screenshots/                   # Demo assets
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- `pip` / `virtualenv`

### 2. Setup Environment

```bash
# Clone or navigate to the repository
cd razorpay-agent-connector

# Create and activate virtual environment
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy example configuration
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `FRESHDESK_DOMAIN` | Merchant Freshdesk domain | `demo-merchant.freshdesk.com` |
| `FRESHDESK_API_KEY` | Freshdesk API Key | `mock_api_key` |
| `CONNECTOR_API_KEY` | Inbound secret key for agents | `rzp_agent_secret_key_987654321` |
| `FRESHDESK_MOCK_MODE` | Enable synthetic demo data (`true`/`false`) | `true` |
| `RATE_LIMIT_PER_MINUTE` | Outbound request throttle limit | `50` |
| `MAX_RETRIES` | Retry attempts on 429/5xx | `3` |

---

## 🏃 Running the Application

### Option A: Start REST API Gateway (FastAPI)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Interactive API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: `GET http://localhost:8000/health`

#### Example REST API Calls

```bash
# 1. List Open Tickets (Status 2)
curl -X GET "http://localhost:8000/api/v1/tickets?status=2&per_page=5" \
     -H "X-API-Key: rzp_agent_secret_key_987654321"

# 2. Get Ticket by ID
curl -X GET "http://localhost:8000/api/v1/tickets/1001" \
     -H "X-API-Key: rzp_agent_secret_key_987654321"

# 3. Search Tickets by Payment ID or Keyword
curl -X GET "http://localhost:8000/api/v1/tickets/search?query=pay_OK9832abc" \
     -H "X-API-Key: rzp_agent_secret_key_987654321"
```

---

### Option B: Start Model Context Protocol (MCP) Server

To use this connector directly with AI agents (e.g., Claude Desktop, Cursor, LangChain):

```bash
python -m mcp.server
```

#### Claude Desktop Configuration (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "freshdesk-connector": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "env": {
        "FRESHDESK_MOCK_MODE": "true",
        "CONNECTOR_API_KEY": "rzp_agent_secret_key_987654321"
      }
    }
  }
}
```

---

## 🧪 Running Automated Tests

Run the complete test suite with coverage:

```bash
pytest tests/ -v
```

---

## 🛡️ Agent Capabilities & Guardrails

| Capability | Supported? | Description |
|---|---|---|
| **List Tickets** | ✅ Yes | Filter by status (Open/Pending/Resolved), priority, customer email |
| **Get Ticket Context** | ✅ Yes | Read full description, custom fields (`cf_order_id`, `cf_rzp_payment_id`) |
| **Search Tickets** | ✅ Yes | Query by payment ID, refund ID, keywords |
| **Ticket Mutation** | ❌ No | Prevented by design (connector is read-only) |
| **Financial Actions** | ❌ No | Agent cannot initiate refunds or capture payments via this tool |

---

## 📄 Documentation Links
- [System Architecture](docs/architecture.md)
- [Agent Capabilities & Tool Contracts](docs/agent-capabilities.md)
