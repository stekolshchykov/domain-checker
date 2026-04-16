import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.adapters.godaddy import GoDaddyAdapter
from src.models import DomainCheckResult


@pytest.fixture
def adapter():
    return GoDaddyAdapter()


# --- API success paths ---

@pytest.mark.asyncio
async def test_godaddy_api_available_with_price(adapter):
    adapter._client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {
            "ExactMatchDomain": {
                "IsAvailable": True,
                "PriceInfo": {"ListPriceDisplay": "$11.99", "Currency": "USD"},
            }
        },
    ))
    result = await adapter.check_domain("example.com")
    assert result.domain == "example.com"
    assert result.status == "available"
    assert result.price == "$11.99"
    assert result.currency == "USD"
    assert result.source == "godaddy_api"
    assert len(result.prices) == 1
    assert result.prices[0].source == "godaddy"
    assert result.prices[0].link is not None


@pytest.mark.asyncio
async def test_godaddy_api_available_with_numeric_price(adapter):
    adapter._client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {
            "ExactMatchDomain": {
                "IsAvailable": True,
                "Price": 11.99,
            }
        },
    ))
    result = await adapter.check_domain("example.com")
    assert result.status == "available"
    assert result.price == "$11.99"
    assert result.currency == "USD"


@pytest.mark.asyncio
async def test_godaddy_api_taken(adapter):
    adapter._client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {
            "ExactMatchDomain": {
                "IsAvailable": False,
                "PriceInfo": {"ListPriceDisplay": "$11.99", "Currency": "USD"},
            }
        },
    ))
    result = await adapter.check_domain("example.com")
    assert result.status == "taken"
    assert result.source == "godaddy_api"
    assert result.prices[0].price == "$11.99"


@pytest.mark.asyncio
async def test_godaddy_api_is_available_none_falls_back_to_html(adapter):
    # First call (API) returns 200 but IsAvailable is None
    # Second call (HTML fallback) should be triggered
    api_resp = MagicMock(status_code=200, json=lambda: {"ExactMatchDomain": {"IsAvailable": None}})
    html_resp = MagicMock(text='<script>"isavailable":true</script>')
    adapter._client.get = AsyncMock(side_effect=[api_resp, html_resp])

    result = await adapter.check_domain("example.com")
    assert result.status == "available"
    assert result.source == "godaddy_page"


# --- Fallback HTML paths ---

@pytest.mark.asyncio
async def test_godaddy_html_available(adapter):
    adapter._client.get = AsyncMock(return_value=MagicMock(
        status_code=404,  # force fallback
        text='<html></html>',
    ))
    # Actually the code first checks status_code == 200 for API; if not 200 it proceeds to HTML fallback.
    # So we need to mock the second get call for HTML.
    api_resp = MagicMock(status_code=500, text="error")
    html_resp = MagicMock(text='<script>"available":true</script>')
    adapter._client.get = AsyncMock(side_effect=[api_resp, html_resp])

    result = await adapter.check_domain("example.com")
    assert result.status == "available"
    assert result.source == "godaddy_page"
    assert len(result.prices) == 1
    assert result.prices[0].link is not None


@pytest.mark.asyncio
async def test_godaddy_html_taken(adapter):
    api_resp = MagicMock(status_code=403, text="blocked")
    html_resp = MagicMock(text='<script>"isavailable":false</script>')
    adapter._client.get = AsyncMock(side_effect=[api_resp, html_resp])

    result = await adapter.check_domain("example.com")
    assert result.status == "taken"
    assert result.source == "godaddy_page"


@pytest.mark.asyncio
async def test_godaddy_html_no_signals_returns_unknown(adapter):
    api_resp = MagicMock(status_code=503, text="error")
    html_resp = MagicMock(text='<html><body>Search for your domain</body></html>')
    adapter._client.get = AsyncMock(side_effect=[api_resp, html_resp])

    result = await adapter.check_domain("example.com")
    assert result.status == "unknown"
    assert result.source == "godaddy"
    assert result.detail == "Could not determine availability"
    assert result.prices == []


# --- Edge cases ---

@pytest.mark.asyncio
async def test_godaddy_invalid_domain_format(adapter):
    result = await adapter.check_domain("nodot")
    assert result.status == "unknown"
    assert result.detail == "Invalid domain format"
    assert result.source == "godaddy"
    assert result.prices == []


@pytest.mark.asyncio
async def test_godaddy_exception_returns_unknown(adapter):
    adapter._client.get = AsyncMock(side_effect=Exception("Connection refused"))
    result = await adapter.check_domain("example.com")
    assert result.status == "unknown"
    assert "Connection refused" in result.detail
    assert result.source == "godaddy"


@pytest.mark.asyncio
async def test_godaddy_api_returns_200_no_exact_match(adapter):
    adapter._client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {"ExactMatchDomain": None},
    ))
    # The code checks exact = data.get("ExactMatchDomain") or {}, so it becomes {}
    # is_available = exact.get("IsAvailable") -> None, so it falls through to HTML fallback
    # But our mock only has one return value. Let's use side_effect properly.


@pytest.mark.asyncio
async def test_godaddy_api_200_empty_exact_then_html_unknown(adapter):
    api_resp = MagicMock(status_code=200, json=lambda: {"ExactMatchDomain": None})
    html_resp = MagicMock(text='<html>nothing here</html>')
    adapter._client.get = AsyncMock(side_effect=[api_resp, html_resp])

    result = await adapter.check_domain("example.com")
    assert result.status == "unknown"
