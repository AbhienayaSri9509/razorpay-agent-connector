# System Architecture: Razorpay Freshdesk Agent Connector

## Overview
The **Razorpay Freshdesk Agent Connector** is a secure, fault-tolerant integration gateway that allows AI Agents (e.g. Razorpay Support Co-Pilot, Dispute Resolution Agents) to interact safely with a merchant's Freshdesk workspace.

It bridges the Model Context Protocol (MCP) tool-calling standard and standard REST APIs with proactive rate limiting, retries, and comprehensive error handling.

---

## Architectural Diagram

```
+-------------------------------------------------------------+
|                       AI Agent Layer                        |
|   (Razorpay Merchant Bot, Claude, Cursor, LangChain)        |
+------------------------------+------------------------------+
                               |
            +------------------+------------------+
            | (MCP JSON-RPC)                      | (REST HTTP)
            v                                     v
+-----------------------+             +-----------------------+
|      mcp/server.py    |             |      app/main.py      |
|   MCP Tool Provider   |             |   FastAPI REST Layer  |
+-----------+-----------+             +-----------+-----------+
            |                                     |
            |       +---------------------+       |
            +-----> | app/auth/api_key.py | <-----+ (X-API-Key / Bearer)
                    +----------+----------+
                               |
                    +----------v----------+
                    |     app/tools/      |
                    |  - list_tickets     |
                    |  - get_ticket       |
                    |  - search_tickets   |
                    +----------+----------+
                               |
                    +----------v----------+
                    | app/client/freshdesk|
                    |  - Token Bucket     |
                    |  - Backoff & Retry  |
                    |  - Mock Data Engine |
                    +----------+----------+
                               |
            +------------------+------------------+
            | (Mock Mode = true)                  | (Mock Mode = false)
            v                                     v
    [ In-Memory Datastore ]              [ Live Freshdesk API ]
    (Synthetic Merchant Data)           (https://{domain}/api/v2)
```

---

## Key Architectural Principles

### 1. Dual Interface: MCP & REST
- **MCP Server (`mcp/server.py`)**: Exposes tool schemas (`freshdesk_list_tickets`, `freshdesk_get_ticket`, `freshdesk_search_tickets`) over stdio JSON-RPC for native LLM function execution.
- **REST Gateway (`app/main.py`)**: Exposes equivalent endpoints protected by API key authentication for microservice architectures.

### 2. Resilience Engine
- **Proactive Token Bucket Rate Limiter**: Ensures outgoing API calls do not exceed configured limits (e.g. 50 requests/min), preventing 429 throttling at the merchant's Freshdesk tier.
- **Exponential Backoff with Full Jitter**: If upstream returns `HTTP 429 Too Many Requests` or `HTTP 5xx Server Error`, the client automatically retries up to `MAX_RETRIES` times with exponential delay or respects the upstream `Retry-After` header.

### 3. Dual Mode Operation
- **Live Mode**: Connects directly to Freshdesk v2 REST APIs using merchant credentials and Basic Auth.
- **Mock/Demo Mode**: Built-in realistic merchant support dataset containing payment disputes, webhook errors, and refund queries for local development, CI/CD, and demonstrations without live API credentials.

### 4. Security & Isolation
- Constant-time secret comparison (`secrets.compare_digest`) prevents timing side-channel attacks on inbound API keys.
- Sanitized error formatting prevents leaking stack traces or sensitive authentication headers to the agent or caller.
