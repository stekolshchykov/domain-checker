import asyncio
import hashlib
import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional

import httpx

from src.exceptions import (
    CircuitBreakerOpenError,
    ProviderBlockedError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderTemporarilyUnavailableError,
)


@dataclass(slots=True)
class ProviderRuntimeConfig:
    max_concurrency: int = 2
    min_interval_seconds: float = 0.0
    timeout_seconds: float = 10.0
    retries: int = 2
    cache_ttl_seconds: float = 15.0


@dataclass(slots=True)
class RequestResult:
    provider: str
    url: str
    status_code: int
    text: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    attempts: int
    cache_hit: bool


@dataclass(slots=True)
class _CircuitState:
    consecutive_failures: int = 0
    open_until: float = 0.0


class RequestRunner:
    """Shared HTTP runner with retries, circuit breaker, rate control and cache."""

    def __init__(
        self,
        *,
        global_max_concurrency: int = 25,
        default_timeout_seconds: float = 10.0,
        default_retries: int = 2,
        default_cache_ttl_seconds: float = 15.0,
        backoff_base_seconds: float = 0.35,
        backoff_jitter_seconds: float = 0.25,
        max_rate_limit_retry_after_seconds: float = 8.0,
        circuit_breaker_failure_threshold: int = 4,
        circuit_breaker_open_seconds: float = 30.0,
        user_agent: str = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    ):
        self._global_semaphore = asyncio.Semaphore(max(1, global_max_concurrency))
        self._default_timeout_seconds = max(1.0, default_timeout_seconds)
        self._default_retries = max(1, default_retries)
        self._default_cache_ttl_seconds = max(0.0, default_cache_ttl_seconds)
        self._backoff_base_seconds = max(0.01, backoff_base_seconds)
        self._backoff_jitter_seconds = max(0.0, backoff_jitter_seconds)
        self._max_rate_limit_retry_after_seconds = max(0.0, max_rate_limit_retry_after_seconds)
        self._circuit_breaker_failure_threshold = max(1, circuit_breaker_failure_threshold)
        self._circuit_breaker_open_seconds = max(1.0, circuit_breaker_open_seconds)

        self._provider_configs: Dict[str, ProviderRuntimeConfig] = {}
        self._provider_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._provider_rate_locks: Dict[str, asyncio.Lock] = {}
        self._provider_last_request_at: Dict[str, float] = {}
        self._provider_circuits: Dict[str, _CircuitState] = {}

        self._cache: Dict[str, tuple[float, RequestResult]] = {}
        self._cache_lock = asyncio.Lock()

        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=self._default_timeout_seconds,
            headers={
                "User-Agent": user_agent,
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    def register_provider(self, provider: str, config: Optional[ProviderRuntimeConfig] = None) -> None:
        cfg = config or ProviderRuntimeConfig()
        self._provider_configs[provider] = cfg
        self._provider_semaphores.setdefault(provider, asyncio.Semaphore(max(1, cfg.max_concurrency)))
        self._provider_rate_locks.setdefault(provider, asyncio.Lock())
        self._provider_last_request_at.setdefault(provider, 0.0)
        self._provider_circuits.setdefault(provider, _CircuitState())

    async def close(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        provider: str,
        method: str,
        url: str,
        *,
        data: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout_seconds: Optional[float] = None,
        retries: Optional[int] = None,
        cache_ttl_seconds: Optional[float] = None,
    ) -> RequestResult:
        if provider not in self._provider_configs:
            self.register_provider(provider)

        self._raise_if_circuit_open(provider)

        ttl = self._default_cache_ttl_seconds if cache_ttl_seconds is None else max(0.0, cache_ttl_seconds)
        cache_key = self._cache_key(method, url, data, json_body)
        if ttl > 0:
            cached = await self._cache_get(cache_key)
            if cached is not None:
                return RequestResult(
                    provider=cached.provider,
                    url=cached.url,
                    status_code=cached.status_code,
                    text=cached.text,
                    started_at=cached.started_at,
                    completed_at=cached.completed_at,
                    duration_ms=cached.duration_ms,
                    attempts=cached.attempts,
                    cache_hit=True,
                )

        cfg = self._provider_configs[provider]
        attempts = max(1, retries if retries is not None else cfg.retries if cfg.retries else self._default_retries)
        timeout = timeout_seconds if timeout_seconds is not None else cfg.timeout_seconds or self._default_timeout_seconds

        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            await self._respect_rate_limit(provider, cfg)
            started_at = datetime.now(timezone.utc)
            started_perf = time.monotonic()
            try:
                async with self._global_semaphore, self._provider_semaphores[provider]:
                    response = await self._client.request(
                        method=method,
                        url=url,
                        data=data,
                        json=json_body,
                        headers=headers,
                        timeout=timeout,
                    )

                completed_at = datetime.now(timezone.utc)
                duration_ms = int((time.monotonic() - started_perf) * 1000)
                text = response.text or ""
                status_code = int(response.status_code)

                self._raise_for_provider_response(provider, status_code, text, headers=response.headers)

                self._mark_success(provider)
                result = RequestResult(
                    provider=provider,
                    url=str(response.url),
                    status_code=status_code,
                    text=text,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    attempts=attempt,
                    cache_hit=False,
                )
                if ttl > 0:
                    await self._cache_set(cache_key, result, ttl)
                return result
            except (ProviderBlockedError, ProviderRateLimitedError) as exc:
                self._mark_failure(provider)
                last_error = exc
                if isinstance(exc, ProviderBlockedError) or attempt >= attempts:
                    break
                await asyncio.sleep(self._retry_delay(attempt, retry_after=exc.retry_after))
            except (ProviderTemporarilyUnavailableError, ProviderRequestError) as exc:
                self._mark_failure(provider)
                last_error = exc
                if attempt >= attempts:
                    break
                await asyncio.sleep(self._retry_delay(attempt, retry_after=None))
            except Exception as exc:
                self._mark_failure(provider)
                last_error = ProviderRequestError(provider, str(exc))
                if attempt >= attempts:
                    break
                await asyncio.sleep(self._retry_delay(attempt, retry_after=None))

        if last_error is None:
            raise ProviderRequestError(provider, "request failed without error")
        raise last_error

    def _raise_for_provider_response(
        self,
        provider: str,
        status_code: int,
        text: str,
        *,
        headers: Optional[httpx.Headers] = None,
    ) -> None:
        text_lower = text.lower()
        if status_code == 429 or "too many requests" in text_lower or "rate limit" in text_lower:
            retry_after = self._extract_retry_after_seconds(headers)
            raise ProviderRateLimitedError(
                provider,
                f"rate-limited (http {status_code})",
                retry_after=retry_after,
            )

        if status_code in (401, 403):
            if any(
                marker in text_lower
                for marker in (
                    "captcha",
                    "access denied",
                    "forbidden",
                    "bot",
                    "challenge",
                    "security check",
                    "login required",
                    "sign in",
                )
            ):
                raise ProviderBlockedError(provider, f"blocked (http {status_code})")

        if status_code in (408, 425, 500, 502, 503, 504):
            raise ProviderTemporarilyUnavailableError(provider, f"temporary failure (http {status_code})")

    def _raise_if_circuit_open(self, provider: str) -> None:
        state = self._provider_circuits.setdefault(provider, _CircuitState())
        now = time.monotonic()
        if state.open_until > now:
            remaining = state.open_until - now
            raise CircuitBreakerOpenError(provider, f"circuit open for {remaining:.1f}s")

    def _mark_success(self, provider: str) -> None:
        state = self._provider_circuits.setdefault(provider, _CircuitState())
        state.consecutive_failures = 0
        state.open_until = 0.0

    def _mark_failure(self, provider: str) -> None:
        state = self._provider_circuits.setdefault(provider, _CircuitState())
        state.consecutive_failures += 1
        if state.consecutive_failures >= self._circuit_breaker_failure_threshold:
            state.open_until = time.monotonic() + self._circuit_breaker_open_seconds
            state.consecutive_failures = 0

    async def _respect_rate_limit(self, provider: str, cfg: ProviderRuntimeConfig) -> None:
        min_interval = max(0.0, cfg.min_interval_seconds)
        if min_interval <= 0:
            return

        lock = self._provider_rate_locks[provider]
        async with lock:
            elapsed = time.monotonic() - self._provider_last_request_at[provider]
            wait_for = min_interval - elapsed
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            self._provider_last_request_at[provider] = time.monotonic()

    def _retry_delay(self, attempt: int, retry_after: float | None = None) -> float:
        base = self._backoff_base_seconds * (2 ** max(0, attempt - 1))
        jitter = random.random() * self._backoff_jitter_seconds
        delay = base + jitter

        if retry_after is not None and retry_after > 0:
            capped = min(retry_after, self._max_rate_limit_retry_after_seconds)
            delay = max(delay, capped)

        return delay

    def _cache_key(
        self,
        method: str,
        url: str,
        data: Optional[dict[str, Any]],
        json_body: Optional[dict[str, Any]],
    ) -> str:
        payload_obj = {
            "method": method.upper(),
            "url": url,
            "data": data or {},
            "json": json_body or {},
        }
        payload = json.dumps(payload_obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _extract_retry_after_seconds(self, headers: Optional[httpx.Headers]) -> float | None:
        if not headers:
            return None

        raw = headers.get("Retry-After")
        if not raw:
            return None

        token = raw.strip()
        if not token:
            return None

        try:
            value = float(token)
            if value >= 0:
                return value
        except Exception:
            pass

        try:
            retry_dt = parsedate_to_datetime(token)
            if retry_dt.tzinfo is None:
                retry_dt = retry_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = (retry_dt - now).total_seconds()
            if delta >= 0:
                return delta
        except Exception:
            return None

        return None

    async def _cache_get(self, key: str) -> Optional[RequestResult]:
        now = time.monotonic()
        async with self._cache_lock:
            value = self._cache.get(key)
            if value is None:
                return None
            expires_at, result = value
            if expires_at < now:
                self._cache.pop(key, None)
                return None
            return result

    async def _cache_set(self, key: str, result: RequestResult, ttl: float) -> None:
        expires_at = time.monotonic() + ttl
        async with self._cache_lock:
            self._cache[key] = (expires_at, result)
