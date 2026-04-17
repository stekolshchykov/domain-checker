from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.adapters.namecheap import NamecheapAdapter
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
        provider="namecheap",
        url=url,
        status_code=status,
        text=text,
        started_at=now,
        completed_at=now,
        duration_ms=40,
        attempts=1,
        cache_hit=False,
    )


@pytest.mark.asyncio
async def test_namecheap_page_available_with_price():
    runner = DummyRunner()
    runner.request.return_value = _result(
        "https://www.namecheap.com/domains/registration/results/?domain=example.com",
        "example.com is available to register for $10.98",
    )
    adapter = NamecheapAdapter(runner)

    result = await adapter.check_domain("example.com")

    assert result.final_status in {FinalStatus.STANDARD_PRICE, FinalStatus.AVAILABLE}
    assert result.status == "available"
    assert result.registration_price == "$10.98"


@pytest.mark.asyncio
async def test_namecheap_fallback_aftermarket_notfound():
    runner = DummyRunner()
    runner.request.side_effect = [
        _result("https://www.namecheap.com/domains/registration/results/?domain=example.com", "no signals"),
        _result(
            "https://aftermarket.namecheapapi.com/domain/status?domain=example.com",
            '{"type":"ok","data":[{"status":"notfound","price":998}]}',
        ),
    ]
    adapter = NamecheapAdapter(runner)

    result = await adapter.check_domain("example.com")

    assert result.status == "unknown"
    assert result.final_status == FinalStatus.UNKNOWN
    assert result.registration_price == "$9.98"


@pytest.mark.asyncio
async def test_namecheap_fallback_aftermarket_taken():
    runner = DummyRunner()
    runner.request.side_effect = [
        RuntimeError("timeout"),
        _result(
            "https://aftermarket.namecheapapi.com/domain/status?domain=example.com",
            '{"type":"ok","data":[{"status":"active","price":50000}]}',
        ),
    ]
    adapter = NamecheapAdapter(runner)

    result = await adapter.check_domain("example.com")

    assert result.status == "taken"
    assert result.final_status == FinalStatus.UNAVAILABLE
    assert result.registration_price == "$500.00"


@pytest.mark.asyncio
async def test_namecheap_parser_failed_when_all_paths_fail():
    runner = DummyRunner()
    runner.request.side_effect = [RuntimeError("network"), RuntimeError("aftermarket down")]
    adapter = NamecheapAdapter(runner)

    result = await adapter.check_domain("example.com")

    assert result.final_status == FinalStatus.PARSING_FAILED
    assert result.status == "unknown"
