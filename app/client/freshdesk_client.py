"""Production-grade Async Freshdesk Client with Mock Support, Retries, and Rate Limiting."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.config import Settings, get_settings
from app.models import (
    Ticket,
    TicketListFilter,
    TicketListResponse,
    TicketPriority,
    TicketSearchFilter,
    TicketStatus,
    TicketSource,
    RateLimitInfo,
)
from app.rate_limit import BackoffStrategy, TokenBucketRateLimiter

logger = logging.getLogger(__name__)


# ==========================================
# Custom Exception Hierarchy
# ==========================================

class FreshdeskError(Exception):
    """Base exception for all Freshdesk client errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class FreshdeskAuthError(FreshdeskError):
    """Raised on HTTP 401 / 403 authentication failures."""
    pass


class FreshdeskNotFoundError(FreshdeskError):
    """Raised when a ticket or resource is not found (HTTP 404)."""
    pass


class FreshdeskRateLimitError(FreshdeskError):
    """Raised when Freshdesk API rate limit is exceeded (HTTP 429) after retry budget."""
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = retry_after


class FreshdeskServerError(FreshdeskError):
    """Raised on HTTP 5xx Freshdesk server errors."""
    pass


# ==========================================
# Mock Data Engine for Testing & Demos
# ==========================================

MOCK_TICKETS_DATABASE: List[Dict[str, Any]] = [
    {
        "id": 1001,
        "subject": "Payment failed for Order #RZP-84920 - Card Charged Twice",
        "description_text": "Customer was charged twice for payment id pay_OK9832abc. Order shows pending in merchant portal. Please check capture status.",
        "description": "<p>Customer was charged twice for payment id <b>pay_OK9832abc</b>. Order shows pending in merchant portal.</p>",
        "status": TicketStatus.OPEN,
        "priority": TicketPriority.HIGH,
        "source": TicketSource.PORTAL,
        "requester_id": 501,
        "responder_id": 12,
        "email": "customer.care@quickretail.in",
        "created_at": "2026-09-30T10:15:00Z",
        "updated_at": "2026-09-30T11:00:00Z",
        "tags": ["payment_failure", "refund", "razorpay_pg"],
        "custom_fields": {"cf_order_id": "ORD-84920", "cf_rzp_payment_id": "pay_OK9832abc", "cf_amount_inr": 4999.0}
    },
    {
        "id": 1002,
        "subject": "Webhook signature verification error on payment.captured",
        "description_text": "Merchant reports webhook HMAC SHA256 validation failure on endpoint /api/v1/razorpay-webhook since 09:00 AM.",
        "description": "<p>Merchant reports webhook signature validation failure on endpoint <code>/api/v1/razorpay-webhook</code>.</p>",
        "status": TicketStatus.OPEN,
        "priority": TicketPriority.URGENT,
        "source": TicketSource.EMAIL,
        "requester_id": 502,
        "responder_id": 14,
        "email": "dev-ops@fashionkart.com",
        "created_at": "2026-10-01T08:30:00Z",
        "updated_at": "2026-10-01T09:15:00Z",
        "tags": ["webhooks", "api_integration", "urgent_merchant"],
        "custom_fields": {"cf_merchant_id": "mid_990182", "cf_webhook_event": "payment.captured"}
    },
    {
        "id": 1003,
        "subject": "Auto-refund inquiry for canceled order #ORD-7712",
        "description_text": "Customer canceled order before dispatch. Need status of refund rfnd_ZZ871239.",
        "description": "<p>Customer canceled order before dispatch. Need status of refund <b>rfnd_ZZ871239</b>.</p>",
        "status": TicketStatus.PENDING,
        "priority": TicketPriority.MEDIUM,
        "source": TicketSource.CHAT,
        "requester_id": 503,
        "responder_id": 12,
        "email": "shoppersupport@trendz.org",
        "created_at": "2026-10-01T14:20:00Z",
        "updated_at": "2026-10-01T15:00:00Z",
        "tags": ["refund", "order_cancellation"],
        "custom_fields": {"cf_order_id": "ORD-7712", "cf_refund_id": "rfnd_ZZ871239"}
    },
    {
        "id": 1004,
        "subject": "Settlement delay for batch 2026-09-28",
        "description_text": "Merchant settlement for batch BATCH-44102 has not been credited to nodal account.",
        "description": "<p>Merchant settlement for batch <b>BATCH-44102</b> has not been credited to nodal account.</p>",
        "status": TicketStatus.RESOLVED,
        "priority": TicketPriority.MEDIUM,
        "source": TicketSource.PORTAL,
        "requester_id": 504,
        "responder_id": 15,
        "email": "finance@megastore.in",
        "created_at": "2026-09-28T16:00:00Z",
        "updated_at": "2026-09-29T18:00:00Z",
        "tags": ["settlements", "nodal_transfer"],
        "custom_fields": {"cf_settlement_id": "setl_9918231"}
    },
    {
        "id": 1005,
        "subject": "Smart Routing rule update for UPI Intent transactions",
        "description_text": "Requesting prioritization of HDFC and ICICI payment handles during festive sale hours.",
        "description": "<p>Requesting prioritization of HDFC and ICICI payment handles during festive sale hours.</p>",
        "status": TicketStatus.CLOSED,
        "priority": TicketPriority.LOW,
        "source": TicketSource.EMAIL,
        "requester_id": 505,
        "responder_id": 18,
        "email": "tech-lead@foodfly.io",
        "created_at": "2026-09-25T11:00:00Z",
        "updated_at": "2026-09-26T12:30:00Z",
        "tags": ["smart_routing", "upi_intent"],
        "custom_fields": {"cf_merchant_id": "mid_441200"}
    }
]


# ==========================================
# Freshdesk Async Client
# ==========================================

class FreshdeskClient:
    """Production Freshdesk API client with Mock Mode, automatic retries, and rate limiting."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.freshdesk_base_url
        self.api_key = self.settings.FRESHDESK_API_KEY
        self.mock_mode = self.settings.FRESHDESK_MOCK_MODE
        self.timeout = self.settings.REQUEST_TIMEOUT_SECONDS
        self.max_retries = self.settings.MAX_RETRIES

        self.rate_limiter = TokenBucketRateLimiter(self.settings.RATE_LIMIT_PER_MINUTE)
        self.backoff_strategy = BackoffStrategy()

        # Last observed rate limit metadata
        self.last_rate_limit_info = RateLimitInfo(
            remaining=self.settings.RATE_LIMIT_PER_MINUTE,
            total_limit=self.settings.RATE_LIMIT_PER_MINUTE,
            retry_after=None
        )

    def _get_auth(self) -> Tuple[str, str]:
        """Freshdesk uses Basic Auth: API_KEY as username, 'X' or dummy password."""
        return (self.api_key, "X")

    def _update_rate_limit_info(self, headers: httpx.Headers) -> None:
        """Parses standard Freshdesk rate-limit headers."""
        remaining = headers.get("X-RateLimit-Remaining")
        total = headers.get("X-RateLimit-Total")
        retry_after = headers.get("Retry-After")

        self.last_rate_limit_info = RateLimitInfo(
            remaining=int(remaining) if remaining and remaining.isdigit() else self.rate_limiter.get_remaining_tokens(),
            total_limit=int(total) if total and total.isdigit() else self.settings.RATE_LIMIT_PER_MINUTE,
            retry_after=int(retry_after) if retry_after and retry_after.isdigit() else None
        )

    async def _execute_http_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Executes an HTTP request with proactive throttling and exponential retry handling."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        auth = self._get_auth()

        for attempt in range(self.max_retries + 1):
            # Proactive client-side rate limit wait
            await self.rate_limiter.wait_for_token()

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        auth=auth,
                        params=params,
                        json=json_data,
                        headers={"Content-Type": "application/json", "Accept": "application/json"}
                    )

                self._update_rate_limit_info(response.headers)

                # Success
                if 200 <= response.status_code < 300:
                    return response

                # Rate Limit (429)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if attempt < self.max_retries:
                        delay = self.backoff_strategy.get_delay(attempt, retry_after)
                        logger.warning(f"Rate limited by Freshdesk (429). Retrying attempt {attempt + 1}/{self.max_retries} in {delay:.2f}s")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise FreshdeskRateLimitError(
                            message="Freshdesk API rate limit exceeded and maximum retries exhausted.",
                            retry_after=int(retry_after) if retry_after and retry_after.isdigit() else None,
                            details={"status_code": 429, "body": response.text}
                        )

                # Server Errors (5xx)
                if 500 <= response.status_code <= 599:
                    if attempt < self.max_retries:
                        delay = self.backoff_strategy.get_delay(attempt)
                        logger.warning(f"Freshdesk server error ({response.status_code}). Retrying in {delay:.2f}s")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise FreshdeskServerError(
                            f"Freshdesk server error ({response.status_code}): {response.text}",
                            status_code=response.status_code
                        )

                # Authentication Errors (401, 403)
                if response.status_code in (401, 403):
                    raise FreshdeskAuthError(
                        f"Freshdesk authentication failed ({response.status_code}). Verify FRESHDESK_API_KEY and FRESHDESK_DOMAIN.",
                        status_code=response.status_code
                    )

                # Not Found (404)
                if response.status_code == 404:
                    raise FreshdeskNotFoundError(
                        f"Resource not found at {endpoint} (HTTP 404).",
                        status_code=404
                    )

                # Other 4xx Client Errors
                raise FreshdeskError(
                    f"Freshdesk request error ({response.status_code}): {response.text}",
                    status_code=response.status_code
                )

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
                if attempt < self.max_retries:
                    delay = self.backoff_strategy.get_delay(attempt)
                    logger.warning(f"Network error ({net_err}). Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                    continue
                raise FreshdeskServerError(f"Freshdesk connection failed after {self.max_retries} retries: {str(net_err)}")

        raise FreshdeskServerError("Request failed after max retries")

    # ==========================================
    # Public API Methods
    # ==========================================

    async def list_tickets(self, filters: TicketListFilter) -> TicketListResponse:
        """Retrieves a paginated list of tickets according to filters."""
        if self.mock_mode:
            return self._mock_list_tickets(filters)

        params: Dict[str, Any] = {
            "page": filters.page,
            "per_page": filters.per_page,
            "order_by": filters.order_by,
            "order_type": filters.order_type,
        }
        if filters.email:
            params["email"] = filters.email

        response = await self._execute_http_request("GET", "tickets", params=params)
        raw_tickets = response.json()

        # In-memory secondary filtering if needed
        tickets = [Ticket(**t) for t in raw_tickets]
        if filters.status:
            tickets = [t for t in tickets if t.status == filters.status]
        if filters.priority:
            tickets = [t for t in tickets if t.priority == filters.priority]

        return TicketListResponse(
            total=len(tickets),
            page=filters.page,
            per_page=filters.per_page,
            tickets=tickets,
            has_more=len(raw_tickets) == filters.per_page
        )

    async def get_ticket(self, ticket_id: int) -> Ticket:
        """Retrieves a single ticket by its integer ID."""
        if ticket_id <= 0:
            raise FreshdeskError("Ticket ID must be a positive integer", status_code=400)

        if self.mock_mode:
            return self._mock_get_ticket(ticket_id)

        response = await self._execute_http_request("GET", f"tickets/{ticket_id}")
        raw_ticket = response.json()
        return Ticket(**raw_ticket)

    async def search_tickets(self, search_params: TicketSearchFilter) -> TicketListResponse:
        """Searches tickets using Freshdesk search query syntax or keywords."""
        if self.mock_mode:
            return self._mock_search_tickets(search_params)

        params = {
            "query": f'"{search_params.query}"',
            "page": search_params.page
        }
        response = await self._execute_http_request("GET", "search/tickets", params=params)
        data = response.json()
        raw_results = data.get("results", [])
        tickets = [Ticket(**t) for t in raw_results]

        return TicketListResponse(
            total=data.get("total", len(tickets)),
            page=search_params.page,
            per_page=30,  # Freshdesk search fixed page size
            tickets=tickets,
            has_more=len(tickets) == 30
        )

    # ==========================================
    # Mock Data Dispatchers
    # ==========================================

    def _mock_list_tickets(self, filters: TicketListFilter) -> TicketListResponse:
        """Simulates Freshdesk list_tickets with sorting and filtering."""
        results = [dict(t) for t in MOCK_TICKETS_DATABASE]

        # Apply filters
        if filters.status is not None:
            results = [t for t in results if t["status"] == filters.status]
        if filters.priority is not None:
            results = [t for t in results if t["priority"] == filters.priority]
        if filters.email:
            results = [t for t in results if filters.email.lower() in t.get("email", "").lower()]

        # Apply pagination
        start_idx = (filters.page - 1) * filters.per_page
        end_idx = start_idx + filters.per_page
        paginated = results[start_idx:end_idx]

        tickets = [Ticket(**t) for t in paginated]
        return TicketListResponse(
            total=len(results),
            page=filters.page,
            per_page=filters.per_page,
            tickets=tickets,
            has_more=end_idx < len(results)
        )

    def _mock_get_ticket(self, ticket_id: int) -> Ticket:
        """Simulates Freshdesk get_ticket by ID."""
        for item in MOCK_TICKETS_DATABASE:
            if item["id"] == ticket_id:
                return Ticket(**item)
        raise FreshdeskNotFoundError(f"Ticket with ID {ticket_id} was not found in Freshdesk.", status_code=404)

    def _mock_search_tickets(self, search_params: TicketSearchFilter) -> TicketListResponse:
        """Simulates Freshdesk search by query keywords or simple field matches."""
        query_str = search_params.query.lower().strip().strip('"')
        matched = []

        # Simple field parse (e.g. status:2 or tag:refund or free text)
        for item in MOCK_TICKETS_DATABASE:
            subject = item.get("subject", "").lower()
            desc = item.get("description_text", "").lower()
            email = item.get("email", "").lower()
            tags = [t.lower() for t in item.get("tags", [])]
            custom = str(item.get("custom_fields", {})).lower()

            # Status query: status:2 or status:open
            if "status:" in query_str:
                status_part = query_str.split("status:")[1].split()[0]
                try:
                    target_status = int(status_part)
                    if item["status"] == target_status:
                        matched.append(item)
                        continue
                except ValueError:
                    pass

            # Priority query: priority:3
            if "priority:" in query_str:
                prio_part = query_str.split("priority:")[1].split()[0]
                try:
                    target_prio = int(prio_part)
                    if item["priority"] == target_prio:
                        matched.append(item)
                        continue
                except ValueError:
                    pass

            # Free text / keyword search
            if (query_str in subject or 
                query_str in desc or 
                query_str in email or 
                any(query_str in t for t in tags) or
                query_str in custom):
                matched.append(item)

        tickets = [Ticket(**t) for t in matched]
        return TicketListResponse(
            total=len(matched),
            page=search_params.page,
            per_page=30,
            tickets=tickets,
            has_more=False
        )


# Singleton getter
_freshdesk_client_instance: Optional[FreshdeskClient] = None

def get_freshdesk_client() -> FreshdeskClient:
    """Returns singleton FreshdeskClient instance."""
    global _freshdesk_client_instance
    if _freshdesk_client_instance is None:
        _freshdesk_client_instance = FreshdeskClient()
    return _freshdesk_client_instance
