import asyncio
import logging
import math
import time
from collections import defaultdict
from typing import List

from src.adapters import build_default_adapters
from src.adapters.base import RegistrarAdapter
from src.config import settings
from src.models import (
    DomainCheckResult,
    FinalStatus,
    PriceOption,
    ProviderResult,
    final_status_to_legacy,
)
from src.request_runner import RequestRunner

logger = logging.getLogger("domain_checker.scraper")


_AVAILABILITY_STATUSES = {
    FinalStatus.AVAILABLE,
    FinalStatus.STANDARD_PRICE,
    FinalStatus.DISCOUNTED,
    FinalStatus.PREMIUM,
}
_UNAVAILABLE_STATUSES = {
    FinalStatus.UNAVAILABLE,
    FinalStatus.TRANSFER_ONLY,
}
_DECISIVE_STATUSES = _AVAILABILITY_STATUSES | _UNAVAILABLE_STATUSES | {FinalStatus.UNSUPPORTED_TLD}
_OPERATIONAL_STATUSES = {
    FinalStatus.BLOCKED,
    FinalStatus.RATE_LIMITED,
    FinalStatus.TEMPORARILY_UNAVAILABLE,
    FinalStatus.PARSING_FAILED,
    FinalStatus.UNKNOWN,
}
_STATUS_QUALITY = {
    FinalStatus.AVAILABLE: 1.0,
    FinalStatus.STANDARD_PRICE: 1.0,
    FinalStatus.DISCOUNTED: 1.0,
    FinalStatus.PREMIUM: 0.98,
    FinalStatus.UNAVAILABLE: 1.0,
    FinalStatus.TRANSFER_ONLY: 0.92,
    FinalStatus.UNSUPPORTED_TLD: 0.88,
    FinalStatus.BLOCKED: 0.3,
    FinalStatus.RATE_LIMITED: 0.3,
    FinalStatus.TEMPORARILY_UNAVAILABLE: 0.28,
    FinalStatus.PARSING_FAILED: 0.2,
    FinalStatus.UNKNOWN: 0.25,
}


class MultiRegistrarChecker:
    """Parallel, fault-tolerant domain checker across many registrars."""

    def __init__(self, max_concurrent_domains: int | None = None):
        self._domain_semaphore = asyncio.Semaphore(
            max(1, max_concurrent_domains or settings.max_concurrent_domains)
        )
        self._runner = RequestRunner(
            global_max_concurrency=settings.max_concurrent_requests,
            default_timeout_seconds=settings.request_timeout_seconds,
            default_retries=settings.request_retry_attempts,
            default_cache_ttl_seconds=settings.request_cache_ttl_seconds,
            backoff_base_seconds=settings.request_retry_base_seconds,
            backoff_jitter_seconds=settings.request_retry_jitter_seconds,
            circuit_breaker_failure_threshold=settings.circuit_breaker_failure_threshold,
            circuit_breaker_open_seconds=settings.circuit_breaker_open_seconds,
        )
        self._adapters: List[RegistrarAdapter] = build_default_adapters(self._runner)
        self._provider_reliability_alpha = min(1.0, max(0.01, settings.provider_reliability_alpha))
        self._provider_reliability_floor = min(1.0, max(0.05, settings.provider_reliability_floor))
        self._provider_reliability: dict[str, float] = {adapter.name: 1.0 for adapter in self._adapters}
        self._provider_reliability_lock = asyncio.Lock()

    async def start(self) -> None:
        for adapter in self._adapters:
            start = getattr(adapter, "start", None)
            if callable(start):
                maybe_awaitable = start()
                if asyncio.iscoroutine(maybe_awaitable):
                    await maybe_awaitable

    async def stop(self) -> None:
        for adapter in self._adapters:
            stop = getattr(adapter, "stop", None)
            if callable(stop):
                maybe_awaitable = stop()
                if asyncio.iscoroutine(maybe_awaitable):
                    await maybe_awaitable
        await self._runner.close()

    async def check_domains(self, domains: List[str]) -> List[DomainCheckResult]:
        tasks = [self._check_domain_with_limit(d.strip().lower()) for d in domains]
        return list(await asyncio.gather(*tasks))

    async def _check_domain_with_limit(self, domain: str) -> DomainCheckResult:
        async with self._domain_semaphore:
            return await self._check_domain_parallel(domain)

    async def _check_domain_parallel(self, domain: str) -> DomainCheckResult:
        provider_tasks = [self._run_adapter(adapter, domain) for adapter in self._adapters]
        provider_results = list(await asyncio.gather(*provider_tasks))
        return self._aggregate(domain, provider_results)

    async def _run_adapter(self, adapter: RegistrarAdapter, domain: str) -> ProviderResult:
        started = time.monotonic()
        logger.info("registrar_started registrar=%s domain=%s", adapter.name, domain)
        try:
            result = await adapter.check_domain(domain)
            reliability = await self._record_provider_outcome(adapter.name, result.final_status)
            if result.debug is not None:
                result.debug.provider_reliability = round(reliability, 3)
            logger.info(
                "registrar_completed registrar=%s domain=%s status=%s final_status=%s duration_ms=%d provider_reliability=%.3f",
                adapter.name,
                domain,
                result.status,
                result.final_status.value,
                int((time.monotonic() - started) * 1000),
                reliability,
            )
            return result
        except Exception as exc:
            reliability = await self._record_provider_outcome(adapter.name, FinalStatus.UNKNOWN)
            logger.warning(
                "registrar_failed registrar=%s domain=%s error=%s duration_ms=%d provider_reliability=%.3f",
                adapter.name,
                domain,
                str(exc),
                int((time.monotonic() - started) * 1000),
                reliability,
            )
            error_result = adapter._error_result(
                domain=domain,
                final_status=FinalStatus.UNKNOWN,
                detail=str(exc),
                source_url=adapter.build_source_url(domain),
                request_url=adapter.build_source_url(domain),
            )
            if error_result.debug is not None:
                error_result.debug.provider_reliability = round(reliability, 3)
            return error_result

    def _aggregate(self, domain: str, provider_results: List[ProviderResult]) -> DomainCheckResult:
        weighted_scores: dict[FinalStatus, float] = defaultdict(float)
        for result in provider_results:
            confidence = result.confidence if result.confidence is not None else 0.3
            provider_weight = self._provider_weight(result.registrar)
            weighted_scores[result.final_status] += max(0.05, confidence) * provider_weight

        availability_score = sum(weighted_scores[s] for s in _AVAILABILITY_STATUSES)
        unavailable_score = sum(weighted_scores[s] for s in _UNAVAILABLE_STATUSES)
        total_weight = sum(weighted_scores.values())
        operational_weight = sum(weighted_scores[s] for s in _OPERATIONAL_STATUSES)

        if availability_score > 0 and unavailable_score > 0:
            delta_ratio = abs(availability_score - unavailable_score) / max(availability_score, unavailable_score)
            if delta_ratio < 0.35:
                final_status = FinalStatus.UNKNOWN
                note = "ambiguous provider consensus"
            else:
                final_status = (
                    max(_AVAILABILITY_STATUSES, key=lambda s: weighted_scores[s])
                    if availability_score > unavailable_score
                    else max(_UNAVAILABLE_STATUSES, key=lambda s: weighted_scores[s])
                )
                note = None
        elif availability_score > 0:
            final_status = max(_AVAILABILITY_STATUSES, key=lambda s: weighted_scores[s])
            note = None
        elif unavailable_score > 0:
            final_status = max(_UNAVAILABLE_STATUSES, key=lambda s: weighted_scores[s])
            note = None
        else:
            final_status, note = self._operational_consensus(weighted_scores)

        if total_weight > 0 and final_status in _DECISIVE_STATUSES:
            decisive_support_ratio = weighted_scores.get(final_status, 0.0) / total_weight
            if decisive_support_ratio < 0.28 and operational_weight >= weighted_scores.get(final_status, 0.0):
                top_operational, op_note = self._operational_consensus(weighted_scores)
                final_status = top_operational
                weak_note = "decisive signal too weak"
                if op_note:
                    note = f"{weak_note}; {op_note}"
                else:
                    note = weak_note

        best_price = self._pick_best_price(provider_results, final_status)
        registration_price = best_price.price if best_price else None
        renewal_price = best_price.renewal_price if best_price else None
        currency = best_price.currency if best_price else None
        source_url = best_price.link if best_price else None

        premium = any(r.premium for r in provider_results)
        promo = any(r.promo for r in provider_results)

        detail_messages: list[str] = []
        for item in provider_results:
            if item.detail and item.detail not in detail_messages:
                detail_messages.append(f"{item.registrar}: {item.detail}")

        confidence_total = sum(weighted_scores.values())
        confidence = None
        if confidence_total > 0:
            confidence = round(weighted_scores.get(final_status, 0.0) / confidence_total, 3)

        status = final_status_to_legacy(final_status, premium)
        prices = self._dedupe_prices(provider_results)

        return DomainCheckResult(
            domain=domain,
            status=status,
            final_status=final_status,
            registrar="aggregated",
            price=registration_price,
            registration_price=registration_price,
            renewal_price=renewal_price,
            currency=currency,
            premium=premium,
            promo=promo,
            source="aggregated",
            source_url=source_url,
            detail="; ".join(detail_messages) if detail_messages else None,
            note=note,
            confidence=confidence,
            prices=prices,
            provider_results=provider_results,
        )

    def _pick_best_price(
        self,
        provider_results: List[ProviderResult],
        final_status: FinalStatus,
    ) -> PriceOption | None:
        price_options = self._dedupe_prices(provider_results)
        if not price_options:
            return None

        if final_status in _AVAILABILITY_STATUSES:
            available_options = [p for p in price_options if p.status in _AVAILABILITY_STATUSES]
            if available_options:
                return min(available_options, key=self._price_sort_key)

        return min(price_options, key=self._price_sort_key)

    def _dedupe_prices(self, provider_results: List[ProviderResult]) -> List[PriceOption]:
        seen = set()
        merged: list[PriceOption] = []
        for item in provider_results:
            for po in item.prices:
                key = (po.source, po.price, po.renewal_price, po.link)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(po)
        return merged

    def _price_sort_key(self, option: PriceOption) -> tuple[int, float]:
        if not option.price:
            return (1, math.inf)
        numeric = "".join(ch for ch in option.price if ch.isdigit() or ch == ".")
        try:
            return (0, float(numeric))
        except Exception:
            return (0, math.inf)

    def _operational_consensus(self, weighted_scores: dict[FinalStatus, float]) -> tuple[FinalStatus, str | None]:
        top_operational = max(_OPERATIONAL_STATUSES, key=lambda s: weighted_scores.get(s, 0.0))
        top_score = weighted_scores.get(top_operational, 0.0)
        operational_total = sum(weighted_scores[s] for s in _OPERATIONAL_STATUSES)
        if top_score <= 0 or operational_total <= 0:
            return FinalStatus.UNKNOWN, None

        dominance = top_score / operational_total
        if dominance >= 0.8:
            return top_operational, "operational consensus"

        return FinalStatus.UNKNOWN, "operational signals mixed"

    async def _record_provider_outcome(self, provider: str, status: FinalStatus) -> float:
        sample = _STATUS_QUALITY.get(status, 0.25)
        async with self._provider_reliability_lock:
            previous = self._provider_reliability.get(provider, 1.0)
            updated = previous * (1.0 - self._provider_reliability_alpha) + sample * self._provider_reliability_alpha
            updated = min(1.0, max(self._provider_reliability_floor, updated))
            self._provider_reliability[provider] = updated
            return updated

    def _provider_weight(self, provider: str) -> float:
        reliability = self._provider_reliability.get(provider, 1.0)
        return min(1.0, max(self._provider_reliability_floor, reliability))

    def is_ready(self) -> bool:
        return True
