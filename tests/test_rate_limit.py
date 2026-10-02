"""Tests for Token Bucket Rate Limiter and Exponential Backoff Strategy."""

import asyncio
import pytest
from app.rate_limit import TokenBucketRateLimiter, BackoffStrategy


@pytest.mark.asyncio
async def test_token_bucket_initial_tokens():
    """Limiter should grant initial tokens without waiting."""
    limiter = TokenBucketRateLimiter(rate_limit_per_minute=60)
    # Capacity = 60, rate = 1 token/sec
    for _ in range(5):
        wait_time = await limiter.acquire()
        assert wait_time == 0.0


@pytest.mark.asyncio
async def test_token_bucket_exhaustion():
    """Limiter should return positive wait time when capacity is exhausted."""
    limiter = TokenBucketRateLimiter(rate_limit_per_minute=2)
    # Acquire available 2 tokens
    w1 = await limiter.acquire()
    w2 = await limiter.acquire()
    assert w1 == 0.0
    assert w2 == 0.0

    # 3rd acquire must throttle
    w3 = await limiter.acquire()
    assert w3 > 0.0


def test_backoff_strategy_exponential_growth():
    """Backoff should increase exponentially with attempt index."""
    strategy = BackoffStrategy(base_delay=1.0, max_delay=30.0, jitter=False)
    assert strategy.get_delay(0) == 1.0
    assert strategy.get_delay(1) == 2.0
    assert strategy.get_delay(2) == 4.0
    assert strategy.get_delay(3) == 8.0


def test_backoff_strategy_max_delay_cap():
    """Backoff should not exceed max_delay."""
    strategy = BackoffStrategy(base_delay=1.0, max_delay=10.0, jitter=False)
    assert strategy.get_delay(10) == 10.0


def test_backoff_strategy_retry_after_header():
    """Backoff should prioritize server Retry-After header."""
    strategy = BackoffStrategy(base_delay=1.0, max_delay=30.0, jitter=False)
    delay = strategy.get_delay(0, retry_after_header="7")
    assert delay == 7.0


def test_backoff_strategy_with_jitter():
    """With jitter enabled, delay should fall between 0.1 and max possible delay."""
    strategy = BackoffStrategy(base_delay=2.0, max_delay=20.0, jitter=True)
    delay = strategy.get_delay(1)  # base * 2^1 = 4.0
    assert 0.1 <= delay <= 4.0
