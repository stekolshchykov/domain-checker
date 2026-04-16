import pytest
from unittest.mock import AsyncMock, MagicMock

from src.adapters.letshost import LetsHostAdapter


@pytest.fixture
def adapter():
    return LetsHostAdapter()


# --- Taken signals ---

@pytest.mark.asyncio
@pytest.mark.parametrize("html_snippet", [
    "Sorry, example.com is not available",
    "example.com is unavailable",
    "example.com is already registered",
    "The domain is not available for registration",
])
async def test_letshost_taken_signals(adapter, html_snippet):
    adapter._client.post = AsyncMock(return_value=MagicMock(text=html_snippet))
    result = await adapter.check_domain("example.com")
    assert result.domain == "example.com"
    assert result.status == "taken"
    assert result.source == "letshost"
    assert len(result.prices) == 1
    assert result.prices[0].source == "letshost"
    assert result.prices[0].link is not None


# --- Available signals with price ---

@pytest.mark.asyncio
async def test_letshost_available_with_eur_price(adapter):
    html = "Congratulations! example.com is available to register for €9.99 per year"
    adapter._client.post = AsyncMock(return_value=MagicMock(text=html))
    result = await adapter.check_domain("example.com")
    assert result.status == "available"
    assert result.price == "€9.99"
    assert result.currency == "EUR"
    assert result.source == "letshost"


@pytest.mark.asyncio
async def test_letshost_available_with_usd_price(adapter):
    html = "Congratulations! example.com is available to register for $12.50 per year"
    adapter._client.post = AsyncMock(return_value=MagicMock(text=html))
    result = await adapter.check_domain("example.com")
    assert result.status == "available"
    assert result.price == "$12.50"
    assert result.currency == "USD"
    assert result.source == "letshost"


@pytest.mark.asyncio
async def test_letshost_available_without_price(adapter):
    html = "Domain is available!"
    adapter._client.post = AsyncMock(return_value=MagicMock(text=html))
    result = await adapter.check_domain("example.com")
    assert result.status == "available"
    assert result.price is None


# --- Unknown / no clear signal ---

@pytest.mark.asyncio
async def test_letshost_no_signals_returns_unknown(adapter):
    html = "<html><body><h1>Welcome to LetsHost</h1></body></html>"
    adapter._client.post = AsyncMock(return_value=MagicMock(text=html))
    result = await adapter.check_domain("example.com")
    assert result.status == "unknown"
    assert result.source == "letshost"
    assert "Could not determine availability" in result.detail
    assert result.prices == []


@pytest.mark.asyncio
async def test_letshost_blocked_or_login_page_returns_unknown(adapter):
    # WHMCS sometimes returns a login page with generic "Sorry" which should NOT trigger taken anymore
    html = "<html><body><p>Sorry, you must login to continue</p></body></html>"
    adapter._client.post = AsyncMock(return_value=MagicMock(text=html))
    result = await adapter.check_domain("example.com")
    # After our fix, "sorry" is not in taken_signals, so it should be unknown
    assert result.status == "unknown"


# --- Edge cases ---

@pytest.mark.asyncio
async def test_letshost_invalid_domain_format(adapter):
    result = await adapter.check_domain("nodot")
    assert result.status == "unknown"
    assert result.detail == "Invalid domain format"
    assert result.source == "letshost"
    assert result.prices == []


@pytest.mark.asyncio
async def test_letshost_exception_returns_unknown(adapter):
    adapter._client.post = AsyncMock(side_effect=Exception("Connection timeout"))
    result = await adapter.check_domain("example.com")
    assert result.status == "unknown"
    assert "Connection timeout" in result.detail
    assert result.source == "letshost"
    assert result.prices == []


@pytest.mark.asyncio
async def test_letshost_empty_response_returns_unknown(adapter):
    adapter._client.post = AsyncMock(return_value=MagicMock(text=""))
    result = await adapter.check_domain("example.com")
    assert result.status == "unknown"
    assert result.prices == []
