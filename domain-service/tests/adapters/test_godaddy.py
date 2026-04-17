from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.adapters.godaddy import GoDaddyAdapter
from src.models import FinalStatus
from src.request_runner import RequestResult


class DummyRunner:
    def __init__(self):
        self.request = AsyncMock()

    def register_provider(self, provider, config=None):
        return None


def _result(url: str, text: str, status: int = 200) -> RequestResult:
    now = datetime.now(timezone.utc)
    return RequestResult(
        provider="godaddy",
        url=url,
        status_code=status,
        text=text,
        started_at=now,
        completed_at=now,
        duration_ms=35,
        attempts=1,
        cache_hit=False,
    )


@pytest.mark.asyncio
async def test_godaddy_api_available_with_price():
    runner = DummyRunner()
    runner.request.return_value = _result(
        "https://www.godaddy.com/domainfind/v1/search/exact?q=example&tld=com",
        '{"ExactMatchDomain":{"IsAvailable":true,"PriceInfo":{"ListPriceDisplay":"$11.99","Currency":"USD"}}}',
    )
    adapter = GoDaddyAdapter(runner)

    result = await adapter.check_domain("example.com")
    assert result.final_status == FinalStatus.STANDARD_PRICE
    assert result.status == "available"
    assert result.registration_price == "$11.99"


@pytest.mark.asyncio
async def test_godaddy_api_taken():
    runner = DummyRunner()
    runner.request.return_value = _result(
        "https://www.godaddy.com/domainfind/v1/search/exact?q=example&tld=com",
        '{"ExactMatchDomain":{"IsAvailable":false,"PriceInfo":{"ListPriceDisplay":"$12.99","Currency":"USD"}}}',
    )
    adapter = GoDaddyAdapter(runner)

    result = await adapter.check_domain("example.com")
    assert result.final_status == FinalStatus.UNAVAILABLE
    assert result.status == "taken"


@pytest.mark.asyncio
async def test_godaddy_fallback_html():
    runner = DummyRunner()
    runner.request.side_effect = [
        _result("https://www.godaddy.com/domainfind/v1/search/exact?q=example&tld=com", "{}"),
        _result(
            "https://www.godaddy.com/domainsearch/find?domainToCheck=example.com",
            "example.com is available now for $9.99",
        ),
    ]
    adapter = GoDaddyAdapter(runner)

    result = await adapter.check_domain("example.com")
    assert result.status == "available"
    assert result.final_status in {FinalStatus.AVAILABLE, FinalStatus.STANDARD_PRICE}


@pytest.mark.asyncio
async def test_godaddy_fallback_error_status_mapping():
    runner = DummyRunner()
    runner.request.side_effect = [RuntimeError("api down"), RuntimeError("rate limited")]
    adapter = GoDaddyAdapter(runner)

    result = await adapter.check_domain("example.com")
    assert result.final_status == FinalStatus.RATE_LIMITED
    assert result.status == "unknown"
