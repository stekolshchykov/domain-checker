import pytest
from unittest.mock import AsyncMock, MagicMock

from src.scraper import MultiRegistrarChecker
from src.models import DomainCheckResult, PriceOption


@pytest.fixture
def checker():
    checker = MultiRegistrarChecker()
    # Replace real adapters with controllable mocks
    checker._namecheap = MagicMock()
    checker._namecheap.name = "namecheap"
    checker._adapters = [
        checker._namecheap,
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    for i, name in enumerate(["namecheap", "godaddy", "letshost", "cloudflare"]):
        checker._adapters[i].name = name
    return checker


# --- start / stop ---

@pytest.mark.asyncio
async def test_checker_start_starts_namecheap(checker):
    checker._namecheap.start = AsyncMock()
    await checker.start()
    checker._namecheap.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_checker_stop_stops_namecheap_and_others(checker):
    checker._namecheap.stop = AsyncMock()
    checker._namecheap._client = MagicMock()
    checker._namecheap._client.aclose = AsyncMock()

    for adapter in checker._adapters[1:]:
        adapter._client = MagicMock()
        adapter._client.aclose = AsyncMock()

    await checker.stop()
    checker._namecheap.stop.assert_awaited_once()
    for adapter in checker._adapters[1:]:
        adapter._client.aclose.assert_awaited_once()


# --- status aggregation with Namecheap authoritative ---

@pytest.mark.asyncio
async def test_aggregate_uses_namecheap_status_available_over_godaddy_taken(checker):
    checker._namecheap.check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="available", source="namecheap_page", prices=[]
    ))
    checker._adapters[1].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="taken", source="godaddy_api", prices=[]
    ))
    checker._adapters[2].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="unknown", source="letshost", prices=[]
    ))
    checker._adapters[3].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="taken", source="cloudflare_api", prices=[]
    ))

    result = await checker._check_domain_parallel("example.com")
    assert result.status == "available"
    assert result.source == "aggregated"


@pytest.mark.asyncio
async def test_aggregate_uses_namecheap_status_premium(checker):
    checker._namecheap.check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="premium", price="$1,000", currency="USD", source="namecheap_page", prices=[]
    ))
    for adapter in checker._adapters[1:]:
        adapter.check_domain = AsyncMock(return_value=DomainCheckResult(
            domain="example.com", status="taken", source="other", prices=[]
        ))

    result = await checker._check_domain_parallel("example.com")
    assert result.status == "premium"
    assert result.price == "$1,000"


@pytest.mark.asyncio
async def test_aggregate_uses_namecheap_status_taken(checker):
    checker._namecheap.check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="taken", source="namecheap_page", prices=[]
    ))
    for adapter in checker._adapters[1:]:
        adapter.check_domain = AsyncMock(return_value=DomainCheckResult(
            domain="example.com", status="available", source="other", prices=[]
        ))

    result = await checker._check_domain_parallel("example.com")
    assert result.status == "taken"


@pytest.mark.asyncio
async def test_aggregate_fallback_when_namecheap_unknown(checker):
    checker._namecheap.check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="unknown", source="namecheap_page", prices=[]
    ))
    checker._adapters[1].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="taken", source="godaddy_api", prices=[]
    ))
    checker._adapters[2].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="available", source="letshost", prices=[]
    ))
    checker._adapters[3].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="unknown", source="cloudflare_api", prices=[]
    ))

    result = await checker._check_domain_parallel("example.com")
    # Fallback logic: taken > premium > available > unknown
    assert result.status == "taken"


def test_aggregate_fallback_when_namecheap_missing():
    checker = MultiRegistrarChecker()
    # Simulate no namecheap by setting it to None
    checker._namecheap = None
    result = checker._aggregate_results(
        "example.com",
        [
            DomainCheckResult(domain="example.com", status="available", source="godaddy_api", prices=[]),
            DomainCheckResult(domain="example.com", status="unknown", source="letshost", prices=[]),
            DomainCheckResult(domain="example.com", status="unknown", source="cloudflare_api", prices=[]),
        ],
        [],
    )
    assert result.status == "available"


# --- price aggregation ---

@pytest.mark.asyncio
async def test_aggregate_collects_all_prices(checker):
    checker._namecheap.check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com",
        status="available",
        source="namecheap_page",
        price="$8.98",
        currency="USD",
        prices=[PriceOption(source="namecheap", price="$8.98", currency="USD", link="nc")],
    ))
    checker._adapters[1].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com",
        status="taken",
        source="godaddy_api",
        price="$11.99",
        currency="USD",
        prices=[PriceOption(source="godaddy", price="$11.99", currency="USD", link="gd")],
    ))
    checker._adapters[2].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com",
        status="unknown",
        source="letshost",
        prices=[PriceOption(source="letshost", price="€9.99", currency="EUR", link="lh")],
    ))
    checker._adapters[3].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com",
        status="taken",
        source="cloudflare_api",
        price="$9.15",
        currency="USD",
        prices=[PriceOption(source="cloudflare", price="$9.15", currency="USD", link="cf")],
    ))

    result = await checker._check_domain_parallel("example.com")
    sources = {p.source: p for p in result.prices}
    assert "namecheap" in sources
    assert "godaddy" in sources
    assert "letshost" in sources
    assert "cloudflare" in sources
    assert sources["letshost"].currency == "EUR"


def test_aggregate_deduplicates_prices_by_source_and_price(checker):
    result = checker._aggregate_results(
        "example.com",
        [
            DomainCheckResult(
                domain="example.com",
                status="available",
                source="namecheap_page",
                prices=[
                    PriceOption(source="namecheap", price="$8.98", link="a"),
                    PriceOption(source="namecheap", price="$8.98", link="b"),  # duplicate
                ],
            ),
        ],
        [],
    )
    assert len(result.prices) == 1


@pytest.mark.asyncio
async def test_aggregate_best_price_for_namecheap_status(checker):
    checker._namecheap.check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com",
        status="available",
        source="namecheap_page",
        price="$8.98",
        prices=[PriceOption(source="namecheap", price="$8.98")],
    ))
    checker._adapters[1].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com",
        status="taken",
        source="godaddy_api",
        price="$11.99",
        prices=[PriceOption(source="godaddy", price="$11.99")],
    ))
    checker._adapters[2].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com",
        status="unknown",
        source="letshost",
        prices=[],
    ))
    checker._adapters[3].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com",
        status="available",
        source="cloudflare_api",
        price="$9.15",
        prices=[PriceOption(source="cloudflare", price="$9.15")],
    ))

    result = await checker._check_domain_parallel("example.com")
    # Namecheap says available, so best price should come from an available result
    assert result.price == "$8.98"


# --- exception handling in parallel ---

@pytest.mark.asyncio
async def test_aggregate_one_adapter_fails_others_succeed(checker):
    checker._namecheap.check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="available", source="namecheap_page", prices=[]
    ))
    checker._adapters[1].check_domain = AsyncMock(side_effect=Exception("godaddy down"))
    checker._adapters[2].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="unknown", source="letshost", prices=[]
    ))
    checker._adapters[3].check_domain = AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="unknown", source="cloudflare_api", prices=[]
    ))

    result = await checker._check_domain_parallel("example.com")
    assert result.status == "available"
    assert "godaddy down" in result.detail


@pytest.mark.asyncio
async def test_aggregate_all_adapters_fail_returns_unknown(checker):
    for adapter in checker._adapters:
        adapter.check_domain = AsyncMock(side_effect=Exception("network error"))

    result = await checker._check_domain_parallel("example.com")
    assert result.status == "unknown"
    # _run_adapter wraps exceptions into DomainCheckResult objects,
    # so the aggregate detail contains the error messages from each adapter.
    assert "network error" in result.detail
    # The aggregator infers purchase links even for adapters that failed,
    # so prices may contain links from each registrar.


# --- legacy single-price inference ---

@pytest.mark.asyncio
async def test_aggregate_infers_link_for_legacy_single_price(checker):
    result = checker._aggregate_results(
        "example.com",
        [
            DomainCheckResult(
                domain="example.com",
                status="available",
                source="godaddy_api",
                price="$11.99",
                prices=[],
            ),
        ],
        [],
    )
    assert len(result.prices) == 1
    assert result.prices[0].source == "godaddy"
    assert result.prices[0].link is not None
    assert "godaddy" in result.prices[0].link


# --- is_ready ---

def test_checker_is_ready_delegates_to_namecheap(checker):
    checker._namecheap.is_ready.return_value = True
    assert checker.is_ready() is True
    checker._namecheap.is_ready.return_value = False
    assert checker.is_ready() is False


def test_checker_is_ready_without_namecheap():
    checker = MultiRegistrarChecker()
    checker._namecheap = None
    checker._adapters = []
    assert checker.is_ready() is True
