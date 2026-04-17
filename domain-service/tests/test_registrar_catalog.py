from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.adapters import GENERIC_REGISTRAR_SPECS, build_default_adapters
from src.adapters.generic import GenericRegistrarAdapter
from src.models import FinalStatus
from src.request_runner import RequestResult, RequestRunner


class DummyRunner:
    def __init__(self, text: str):
        self._text = text
        self.request = AsyncMock(side_effect=self._request)

    def register_provider(self, provider, config=None):
        return None

    async def _request(self, provider, method, url, **kwargs):
        now = datetime.now(timezone.utc)
        return RequestResult(
            provider=provider,
            url=url,
            status_code=200,
            text=self._text,
            started_at=now,
            completed_at=now,
            duration_ms=25,
            attempts=1,
            cache_hit=False,
        )


def test_catalog_contains_required_50_registrars():
    # 50 requested registrars minus 4 special providers (namecheap, godaddy, cloudflare, letshost optional)
    assert len(GENERIC_REGISTRAR_SPECS) >= 46


@pytest.mark.parametrize("spec", GENERIC_REGISTRAR_SPECS)
@pytest.mark.asyncio
async def test_generic_adapter_available_fixture(spec):
    runner = DummyRunner("example.com is available to register for $9.99")
    adapter = GenericRegistrarAdapter(runner, spec)

    result = await adapter.check_domain("example.com")

    assert result.domain == "example.com"
    assert result.status == "available"
    assert result.final_status in {FinalStatus.AVAILABLE, FinalStatus.STANDARD_PRICE}
    assert result.source_url is not None


@pytest.mark.parametrize("spec", GENERIC_REGISTRAR_SPECS)
@pytest.mark.asyncio
async def test_generic_adapter_unavailable_fixture(spec):
    runner = DummyRunner("example.com is already registered")
    adapter = GenericRegistrarAdapter(runner, spec)

    result = await adapter.check_domain("example.com")

    assert result.status == "taken"
    assert result.final_status == FinalStatus.UNAVAILABLE


def test_build_default_adapters_registers_special_and_generic():
    runner = RequestRunner(global_max_concurrency=2)
    adapters = build_default_adapters(runner)
    names = {a.name for a in adapters}

    assert "namecheap" in names
    assert "godaddy" in names
    assert "cloudflare" in names
    assert "domaincom" in names
    assert "names007" in names

