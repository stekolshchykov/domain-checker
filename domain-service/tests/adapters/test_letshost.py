from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.adapters.letshost import LetsHostAdapter
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
        provider="letshost",
        url=url,
        status_code=status,
        text=text,
        started_at=now,
        completed_at=now,
        duration_ms=29,
        attempts=1,
        cache_hit=False,
    )


@pytest.mark.asyncio
async def test_letshost_available_with_price():
    runner = DummyRunner()
    runner.request.return_value = _result(
        "https://billing.letshost.ie/domainchecker.php",
        "Congratulations, example.com is available to register for €9.99",
    )
    adapter = LetsHostAdapter(runner)

    result = await adapter.check_domain("example.com")
    assert result.status == "available"
    assert result.final_status in {FinalStatus.AVAILABLE, FinalStatus.STANDARD_PRICE}
    assert result.registration_price == "€9.99"


@pytest.mark.asyncio
async def test_letshost_taken_signal():
    runner = DummyRunner()
    runner.request.return_value = _result(
        "https://billing.letshost.ie/domainchecker.php",
        "example.com is already registered",
    )
    adapter = LetsHostAdapter(runner)

    result = await adapter.check_domain("example.com")
    assert result.status == "taken"
    assert result.final_status == FinalStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_letshost_rate_limited_error():
    runner = DummyRunner()
    runner.request.side_effect = RuntimeError("rate limited")
    adapter = LetsHostAdapter(runner)

    result = await adapter.check_domain("example.com")
    assert result.final_status == FinalStatus.RATE_LIMITED
