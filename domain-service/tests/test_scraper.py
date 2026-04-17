import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pytest
import pytest_asyncio

from src.models import FinalStatus, PriceOption, ProviderResult
from src.scraper import MultiRegistrarChecker


@dataclass
class StubAdapter:
    name: str
    result: Optional[ProviderResult] = None
    error: Optional[Exception] = None

    async def check_domain(self, domain: str) -> ProviderResult:
        if self.error:
            raise self.error
        assert self.result is not None
        return self.result

    def build_source_url(self, domain: str) -> str:
        return f"https://{self.name}.test/search?domain={domain}"

    def _error_result(self, **kwargs) -> ProviderResult:
        now = datetime.now(timezone.utc)
        return ProviderResult(
            registrar=self.name,
            domain=kwargs["domain"],
            status="unknown",
            final_status=kwargs["final_status"],
            source=self.name,
            source_url=kwargs.get("source_url"),
            checked_at=now,
            detail=kwargs.get("detail"),
            confidence=0.1,
            prices=[],
            debug=None,
        )


@pytest_asyncio.fixture
async def checker():
    c = MultiRegistrarChecker(max_concurrent_domains=4)
    yield c
    await c.stop()


def _provider(
    registrar: str,
    final_status: FinalStatus,
    *,
    confidence: float = 0.8,
    price: str | None = None,
) -> ProviderResult:
    option = PriceOption(
        source=registrar,
        status=final_status,
        price=price,
        currency="USD" if price else None,
        link=f"https://{registrar}.test",
    )
    return ProviderResult(
        registrar=registrar,
        domain="example.com",
        status="available" if final_status in {FinalStatus.AVAILABLE, FinalStatus.STANDARD_PRICE, FinalStatus.DISCOUNTED} else "taken" if final_status in {FinalStatus.UNAVAILABLE, FinalStatus.TRANSFER_ONLY} else "premium" if final_status == FinalStatus.PREMIUM else "unknown",
        final_status=final_status,
        registration_price=price,
        currency="USD" if price else None,
        source=registrar,
        source_url=f"https://{registrar}.test",
        detail=f"{registrar}: {final_status.value}",
        confidence=confidence,
        prices=[option],
        debug=None,
    )


@pytest.mark.asyncio
async def test_aggregate_prefers_available_family(checker):
    checker._adapters = [
        StubAdapter("namecheap", _provider("namecheap", FinalStatus.STANDARD_PRICE, price="$10.00")),
        StubAdapter("godaddy", _provider("godaddy", FinalStatus.UNAVAILABLE)),
        StubAdapter("dynadot", _provider("dynadot", FinalStatus.AVAILABLE, price="$9.00")),
    ]

    result = await checker._check_domain_parallel("example.com")
    assert result.status == "available"
    assert result.final_status in {FinalStatus.AVAILABLE, FinalStatus.STANDARD_PRICE}
    assert result.price == "$9.00"


@pytest.mark.asyncio
async def test_aggregate_conflicting_consensus_is_unknown(checker):
    checker._adapters = [
        StubAdapter("namecheap", _provider("namecheap", FinalStatus.AVAILABLE, confidence=0.7)),
        StubAdapter("godaddy", _provider("godaddy", FinalStatus.UNAVAILABLE, confidence=0.68)),
    ]

    result = await checker._check_domain_parallel("example.com")
    assert result.final_status == FinalStatus.UNKNOWN
    assert result.status == "unknown"
    assert result.note == "ambiguous provider consensus"


@pytest.mark.asyncio
async def test_aggregate_degrades_weak_decisive_to_operational(checker):
    checker._adapters = [
        StubAdapter("one", _provider("one", FinalStatus.PREMIUM, confidence=0.25)),
        StubAdapter("two", _provider("two", FinalStatus.BLOCKED, confidence=0.7)),
        StubAdapter("three", _provider("three", FinalStatus.UNKNOWN, confidence=0.1)),
    ]

    result = await checker._check_domain_parallel("example.com")
    assert result.final_status == FinalStatus.BLOCKED
    assert result.status == "unknown"
    assert result.note == "decisive signal too weak; operational consensus"


@pytest.mark.asyncio
async def test_aggregate_mixed_operational_without_decisive_returns_unknown(checker):
    checker._adapters = [
        StubAdapter("one", _provider("one", FinalStatus.BLOCKED, confidence=0.35)),
        StubAdapter("two", _provider("two", FinalStatus.PARSING_FAILED, confidence=0.35)),
        StubAdapter("three", _provider("three", FinalStatus.UNKNOWN, confidence=0.3)),
    ]

    result = await checker._check_domain_parallel("example.com")
    assert result.final_status == FinalStatus.UNKNOWN
    assert result.status == "unknown"
    assert result.note == "operational signals mixed"


@pytest.mark.asyncio
async def test_aggregate_uses_provider_reliability_weight(checker):
    checker._provider_reliability["reliable"] = 1.0
    checker._provider_reliability["noisy"] = 0.2
    checker._adapters = [
        StubAdapter("reliable", _provider("reliable", FinalStatus.AVAILABLE, confidence=0.45)),
        StubAdapter("noisy", _provider("noisy", FinalStatus.UNAVAILABLE, confidence=0.8)),
    ]

    result = await checker._check_domain_parallel("example.com")
    assert result.final_status == FinalStatus.AVAILABLE
    assert result.status == "available"


@pytest.mark.asyncio
async def test_provider_reliability_degrades_on_parsing_failed(checker):
    checker._provider_reliability["flaky"] = 1.0
    updated = await checker._record_provider_outcome("flaky", FinalStatus.PARSING_FAILED)
    assert updated < 1.0
    assert checker._provider_reliability["flaky"] == updated


@pytest.mark.asyncio
async def test_aggregate_unavailable_maps_to_taken(checker):
    checker._adapters = [
        StubAdapter("namecheap", _provider("namecheap", FinalStatus.UNAVAILABLE)),
        StubAdapter("godaddy", _provider("godaddy", FinalStatus.UNAVAILABLE)),
    ]

    result = await checker._check_domain_parallel("example.com")
    assert result.final_status == FinalStatus.UNAVAILABLE
    assert result.status == "taken"


@pytest.mark.asyncio
async def test_aggregate_dedupes_prices_and_keeps_provider_results(checker):
    p = _provider("namecheap", FinalStatus.STANDARD_PRICE, price="$10.00")
    p.prices.append(
        PriceOption(source="namecheap", status=FinalStatus.STANDARD_PRICE, price="$10.00", link="https://namecheap.test")
    )
    checker._adapters = [
        StubAdapter("namecheap", p),
        StubAdapter("godaddy", _provider("godaddy", FinalStatus.STANDARD_PRICE, price="$12.00")),
    ]

    result = await checker._check_domain_parallel("example.com")
    assert len(result.prices) == 2
    assert len(result.provider_results) == 2


@pytest.mark.asyncio
async def test_run_adapter_exception_returns_unknown_provider_result(checker):
    adapter = StubAdapter("broken", error=RuntimeError("boom"))
    result = await checker._run_adapter(adapter, "example.com")
    assert result.final_status == FinalStatus.UNKNOWN
    assert "boom" in (result.detail or "")


@pytest.mark.asyncio
async def test_check_domains_processes_multiple_domains(checker):
    checker._adapters = [
        StubAdapter("namecheap", _provider("namecheap", FinalStatus.AVAILABLE, price="$8.00")),
    ]
    results = await checker.check_domains(["a-example.com", "b-example.com", "c-example.com"])
    assert len(results) == 3
    assert all(r.status == "available" for r in results)


@pytest.mark.asyncio
async def test_domain_semaphore_limits_parallel_domain_runs(monkeypatch):
    checker = MultiRegistrarChecker(max_concurrent_domains=1)

    class SlowAdapter(StubAdapter):
        async def check_domain(self, domain: str) -> ProviderResult:
            await asyncio.sleep(0.05)
            return _provider(self.name, FinalStatus.AVAILABLE, price="$10.00")

    checker._adapters = [SlowAdapter("slow")]

    start = asyncio.get_event_loop().time()
    await checker.check_domains(["one.com", "two.com"])
    elapsed = asyncio.get_event_loop().time() - start
    await checker.stop()

    assert elapsed >= 0.09
