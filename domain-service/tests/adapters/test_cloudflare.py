from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.adapters.cloudflare import CloudflareAdapter
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
        provider="cloudflare",
        url=url,
        status_code=status,
        text=text,
        started_at=now,
        completed_at=now,
        duration_ms=33,
        attempts=1,
        cache_hit=False,
    )


@pytest.mark.asyncio
async def test_cloudflare_api_available_with_price():
    runner = DummyRunner()
    runner.request.return_value = _result(
        "https://api.cloudflare.com/client/v4/zones/name/available/example.com",
        '{"success":true,"result":{"available":true,"price":9.15}}',
    )
    adapter = CloudflareAdapter(runner)

    result = await adapter.check_domain("example.com")
    assert result.status == "available"
    assert result.final_status == FinalStatus.STANDARD_PRICE
    assert result.registration_price == "$9.15"


@pytest.mark.asyncio
async def test_cloudflare_page_login_is_blocked():
    runner = DummyRunner()
    runner.request.side_effect = [
        _result("https://api.cloudflare.com/client/v4/zones/name/available/example.com", '{"success":false}'),
        _result("https://dash.cloudflare.com/domains/register?domain=example.com", "Sign in to continue"),
    ]
    adapter = CloudflareAdapter(runner)

    result = await adapter.check_domain("example.com")
    assert result.final_status == FinalStatus.BLOCKED
    assert result.status == "unknown"


@pytest.mark.asyncio
async def test_cloudflare_unavailable():
    runner = DummyRunner()
    runner.request.return_value = _result(
        "https://api.cloudflare.com/client/v4/zones/name/available/example.com",
        '{"success":true,"result":{"available":false}}',
    )
    adapter = CloudflareAdapter(runner)

    result = await adapter.check_domain("example.com")
    assert result.final_status == FinalStatus.UNAVAILABLE
    assert result.status == "taken"
