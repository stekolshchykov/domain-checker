import pytest
from unittest.mock import AsyncMock, MagicMock

from src.adapters.cloudflare import CloudflareAdapter


@pytest.fixture
def adapter():
    return CloudflareAdapter()


# --- API success paths ---

@pytest.mark.asyncio
async def test_cloudflare_api_available_with_price(adapter):
    adapter._client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {
            "success": True,
            "result": {"available": True, "price": 9.15},
        },
    ))
    result = await adapter.check_domain("example.com")
    assert result.domain == "example.com"
    assert result.status == "available"
    assert result.price == "$9.15"
    assert result.currency == "USD"
    assert result.source == "cloudflare_api"
    assert len(result.prices) == 1
    assert result.prices[0].source == "cloudflare"
    assert result.prices[0].link is not None


@pytest.mark.asyncio
async def test_cloudflare_api_taken(adapter):
    adapter._client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {
            "success": True,
            "result": {"available": False},
        },
    ))
    result = await adapter.check_domain("example.com")
    assert result.status == "taken"
    assert result.source == "cloudflare_api"
    assert result.prices[0].source == "cloudflare"


@pytest.mark.asyncio
async def test_cloudflare_api_200_no_result(adapter):
    adapter._client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {"success": True},
    ))
    # Falls through to HTML fallback, which also yields nothing
    html_resp = MagicMock(text='<html></html>')
    adapter._client.get = AsyncMock(side_effect=[
        MagicMock(status_code=200, json=lambda: {"success": True}),
        html_resp,
    ])
    result = await adapter.check_domain("example.com")
    assert result.status == "unknown"


# --- Fallback HTML paths ---

@pytest.mark.asyncio
async def test_cloudflare_html_available(adapter):
    adapter._client.get = AsyncMock(side_effect=[
        MagicMock(status_code=403, text="Forbidden"),
        MagicMock(text='<script>"available":true</script>'),
    ])
    result = await adapter.check_domain("example.com")
    assert result.status == "available"
    assert result.source == "cloudflare_page"


@pytest.mark.asyncio
async def test_cloudflare_html_taken(adapter):
    adapter._client.get = AsyncMock(side_effect=[
        MagicMock(status_code=500, text="Error"),
        MagicMock(text='<script>"isavailable":false</script>'),
    ])
    result = await adapter.check_domain("example.com")
    assert result.status == "taken"
    assert result.source == "cloudflare_page"


@pytest.mark.asyncio
async def test_cloudflare_html_no_signals_returns_unknown(adapter):
    adapter._client.get = AsyncMock(side_effect=[
        MagicMock(status_code=503, text="Service Unavailable"),
        MagicMock(text='<html><body>Cloudflare Registrar</body></html>'),
    ])
    result = await adapter.check_domain("example.com")
    assert result.status == "unknown"
    assert result.source == "cloudflare"
    assert result.detail == "Could not determine availability"
    assert result.prices == []


# --- Edge cases ---

@pytest.mark.asyncio
async def test_cloudflare_exception_returns_unknown(adapter):
    adapter._client.get = AsyncMock(side_effect=Exception("SSL handshake failed"))
    result = await adapter.check_domain("example.com")
    assert result.status == "unknown"
    assert "SSL handshake failed" in result.detail
    assert result.source == "cloudflare"
    assert result.prices == []
