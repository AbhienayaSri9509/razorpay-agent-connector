"""Rate limiting and exponential backoff engine."""

import asyncio
import logging
import random
import time
from typing import Optional

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Thread-safe and async-safe Token Bucket Rate Limiter."""

    def __init__(self, rate_limit_per_minute: int = 50):
        self.capacity = max(1, rate_limit_per_minute)
        self.tokens = float(self.capacity)
        self.fill_rate = self.capacity / 60.0  # tokens per second
        self.last_updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        """Acquires a token. If bucket is empty, returns required wait time in seconds."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_updated
            self.last_updated = now

            # Replenish tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + (elapsed * self.fill_rate))

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0

            # Compute required wait time to get 1 token
            deficit = 1.0 - self.tokens
            wait_time = deficit / self.fill_rate
            return wait_time

    async def wait_for_token(self) -> None:
        """Waits asynchronously until a token is available."""
        wait_time = await self.acquire()
        if wait_time > 0:
            logger.warning(f"Client-side rate limit reached. Throttling for {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
            # Re-acquire after sleeping
            await self.acquire()

    def get_remaining_tokens(self) -> int:
        """Returns approximate available tokens."""
        now = time.monotonic()
        elapsed = now - self.last_updated
        current_tokens = min(self.capacity, self.tokens + (elapsed * self.fill_rate))
        return int(current_tokens)


class BackoffStrategy:
    """Computes exponential backoff with full jitter for retries."""

    def __init__(self, base_delay: float = 0.5, max_delay: float = 10.0, jitter: bool = True):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def get_delay(self, attempt: int, retry_after_header: Optional[str] = None) -> float:
        """Calculates sleep duration for a given attempt index (0-indexed)."""
        if retry_after_header:
            try:
                header_val = float(retry_after_header)
                if header_val > 0:
                    logger.info(f"Using server-provided Retry-After header: {header_val}s")
                    return min(header_val, self.max_delay)
            except (ValueError, TypeError):
                pass

        # Exponential calculation: base * 2^attempt
        delay = min(self.max_delay, self.base_delay * (2 ** attempt))

        if self.jitter:
            # Full jitter: random between 0 and calculated delay
            delay = random.uniform(0.1, delay)

        return delay
