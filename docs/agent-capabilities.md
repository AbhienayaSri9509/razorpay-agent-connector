# Agent Capabilities & Operational Boundaries

This document defines the interface, capabilities, safety guardrails, and operational boundaries for AI agents utilizing the Freshdesk connector.

---

## Tool Contracts

### 1. `freshdesk_list_tickets`
- **Description**: Lists tickets with pagination, status filtering, priority filtering, and requester email.
- **Parameters**:
  - `page` *(integer, optional, default: 1)*: Page number.
  - `per_page` *(integer, optional, default: 10, max: 100)*: Items per page.
  - `status` *(integer, optional)*: `2` (Open), `3` (Pending), `4` (Resolved), `5` (Closed).
  - `priority` *(integer, optional)*: `1` (Low), `2` (Medium), `3` (High), `4` (Urgent).
  - `email` *(string, optional)*: Filter tickets by customer email.
- **Output**: JSON containing `tickets` array, `page`, `per_page`, `has_more`, and `rate_limit`.

---

### 2. `freshdesk_get_ticket`
- **Description**: Fetches detailed ticket context, description, custom fields (e.g. order IDs, payment IDs), and tags by numeric ticket ID.
- **Parameters**:
  - `ticket_id` *(integer, required)*: The numeric ticket identifier.
- **Output**: JSON containing full `ticket` object with custom fields and metadata.

---

### 3. `freshdesk_search_tickets`
- **Description**: Queries tickets using keywords, payment IDs (e.g., `pay_OK9832abc`), order IDs, or Freshdesk filter expressions.
- **Parameters**:
  - `query` *(string, required)*: Query string or keyword.
  - `page` *(integer, optional, default: 1)*: Page number.
- **Output**: JSON containing matched `tickets` and search metrics.

---

## What the Agent CAN Do
- Query merchant tickets by status, priority, or customer identity.
- Retrieve full context of a customer grievance (e.g., failed payment, missing webhook, delayed settlement).
- Correlate Razorpay transaction IDs (`pay_*`, `rfnd_*`) present in ticket descriptions or custom fields.
- Monitor rate limit consumption through response metadata.
- Perform targeted searches for recurring merchant issues.

---

## What the Agent CANNOT Do (Guardrails)
- **NO Destructive Operations (Read-Only)**: The connector strictly does not expose ticket deletion, ticket modification, or user deletion tools to prevent unintended agent actions.
- **NO Financial Movement**: The connector cannot trigger direct refunds, bank transfers, or card charges inside Freshdesk.
- **NO Credential Extraction**: Freshdesk API keys and master secrets are never returned in tool outputs or error payloads.
- **NO Rate Limit Bypass**: The agent cannot bypass the token-bucket rate limiter; queries exceeding quotas will be throttled.

---

## Prompt Engineering & Agent Persona Example

### Recommended System Prompt Injection for Agents
```markdown
You are an autonomous Razorpay Merchant Support Co-Pilot.
You have access to the merchant's Freshdesk workspace via the following tools:
1. `freshdesk_list_tickets`: Retrieve recent tickets or filter by urgency/status.
2. `freshdesk_get_ticket`: Inspect full ticket details when investigating a specific issue.
3. `freshdesk_search_tickets`: Search by payment IDs (pay_xxx), refund IDs (rfnd_xxx), or customer email.

Guardrails:
- Always confirm the ticket ID and customer context before giving advice.
- If a ticket references a payment ID, verify its status against Razorpay transaction logs.
- Never claim to have resolved or closed a ticket without merchant agent human sign-off.
```
