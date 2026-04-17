import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.exceptions import (
    CircuitBreakerOpenError,
    ProviderRateLimitedError,
    ProviderTemporarilyUnavailableError,
)
from src.request_runner import ProviderRuntimeConfig, RequestRunner


def _response(
    status_code: int,
    text: str = "ok",
    url: str = "https://example.test",
    headers: dict | None = None,
):
    return SimpleNamespace(status_code=status_code, text=text, url=url, headers=headers or {})


@pytest.mark.asyncio
async def test_runner_retries_then_succeeds():
    runner = RequestRunner(
        global_max_concurrency=5,
        default_retries=3,
        backoff_base_seconds=0.001,
        backoff_jitter_seconds=0.0,
    )
    runner.register_provider("test", ProviderRuntimeConfig(retries=3, min_interval_seconds=0.0))

    runner._client.request = AsyncMock(
        side_effect=[
            _response(503, "temporary down"),
            _response(200, "ok"),
        ]
    )

    result = await runner.request("test", "GET", "https://example.test")
    assert result.status_code == 200
    assert result.attempts == 2

    await runner.close()


@pytest.mark.asyncio
async def test_runner_cache_hit_skips_second_http_call():
    runner = RequestRunner(global_max_concurrency=5, default_cache_ttl_seconds=60)
    runner.register_provider("test", ProviderRuntimeConfig(cache_ttl_seconds=60))
    runner._client.request = AsyncMock(return_value=_response(200, "cached"))

    first = await runner.request("test", "GET", "https://cache.test")
    second = await runner.request("test", "GET", "https://cache.test")

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert runner._client.request.await_count == 1

    await runner.close()


@pytest.mark.asyncio
async def test_runner_rate_limit_interval():
    runner = RequestRunner(global_max_concurrency=5, default_retries=1)
    runner.register_provider("slow", ProviderRuntimeConfig(min_interval_seconds=0.05, retries=1))
    runner._client.request = AsyncMock(return_value=_response(200, "ok"))

    start = time.monotonic()
    await runner.request("slow", "GET", "https://slow.test/1", cache_ttl_seconds=0)
    await runner.request("slow", "GET", "https://slow.test/2", cache_ttl_seconds=0)
    elapsed = time.monotonic() - start

    assert elapsed >= 0.045
    await runner.close()


@pytest.mark.asyncio
async def test_runner_rate_limited_retries_then_succeeds():
    runner = RequestRunner(
        global_max_concurrency=5,
        default_retries=2,
        backoff_base_seconds=0.001,
        backoff_jitter_seconds=0.0,
    )
    runner.register_provider("burst", ProviderRuntimeConfig(retries=2, min_interval_seconds=0.0))
    runner._client.request = AsyncMock(
        side_effect=[
            _response(429, "too many requests", headers={"Retry-After": "0"}),
            _response(200, "ok"),
        ]
    )

    result = await runner.request("burst", "GET", "https://burst.test", cache_ttl_seconds=0)
    assert result.status_code == 200
    assert result.attempts == 2
    assert runner._client.request.await_count == 2

    await runner.close()


@pytest.mark.asyncio
async def test_runner_circuit_breaker_opens_after_repeated_failures():
    runner = RequestRunner(
        global_max_concurrency=5,
        default_retries=1,
        circuit_breaker_failure_threshold=2,
        circuit_breaker_open_seconds=5,
        backoff_base_seconds=0.001,
        backoff_jitter_seconds=0.0,
    )
    runner.register_provider("fragile", ProviderRuntimeConfig(retries=1))
    runner._client.request = AsyncMock(return_value=_response(503, "temporary"))

    with pytest.raises(ProviderTemporarilyUnavailableError):
        await runner.request("fragile", "GET", "https://fragile.test/1", cache_ttl_seconds=0)
    with pytest.raises(ProviderTemporarilyUnavailableError):
        await runner.request("fragile", "GET", "https://fragile.test/2", cache_ttl_seconds=0)
    with pytest.raises(CircuitBreakerOpenError):
        await runner.request("fragile", "GET", "https://fragile.test/3", cache_ttl_seconds=0)

    await runner.close()


@pytest.mark.asyncio
async def test_runner_per_provider_concurrency_limit():
    runner = RequestRunner(global_max_concurrency=10, default_retries=1)
    runner.register_provider("limited", ProviderRuntimeConfig(max_concurrency=1, retries=1))

    order = []

    async def slow_request(*args, **kwargs):
        order.append("start")
        await asyncio.sleep(0.03)
        order.append("end")
        return _response(200, "ok", kwargs.get("url", "https://limited.test"))

    runner._client.request = AsyncMock(side_effect=slow_request)

    await asyncio.gather(
        runner.request("limited", "GET", "https://limited.test/1", cache_ttl_seconds=0),
        runner.request("limited", "GET", "https://limited.test/2", cache_ttl_seconds=0),
    )

    # With max_concurrency=1 we should complete first request before second ends.
    assert order == ["start", "end", "start", "end"]

    await runner.close()


def test_runner_cache_key_canonicalizes_payload_order():
    runner = RequestRunner()
    key_a = runner._cache_key(
        "POST",
        "https://example.test",
        data={"b": "2", "a": "1"},
        json_body=None,
    )
    key_b = runner._cache_key(
        "POST",
        "https://example.test",
        data={"a": "1", "b": "2"},
        json_body=None,
    )
    assert key_a == key_b


@pytest.mark.asyncio
async def test_runner_rate_limited_raises_when_retries_exhausted():
    runner = RequestRunner(
        global_max_concurrency=5,
        default_retries=1,
        backoff_base_seconds=0.001,
        backoff_jitter_seconds=0.0,
    )
    runner.register_provider("burst", ProviderRuntimeConfig(retries=1))
    runner._client.request = AsyncMock(return_value=_response(429, "too many requests"))

    with pytest.raises(ProviderRateLimitedError):
        await runner.request("burst", "GET", "https://burst.test", cache_ttl_seconds=0)

    await runner.close()
