import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.adapters.namecheap import NamecheapAdapter
from src.models import DomainCheckResult


@pytest.fixture
def adapter():
    return NamecheapAdapter()


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.is_closed.return_value = False
    return page


class ChainableLocator:
    """Synchronous Playwright locator mock supporting chain operations."""

    def __init__(self, count_val=0, inner_text_val="", button_texts=None, strong_texts=None):
        self._count = count_val
        self._inner_text = inner_text_val
        self._button_texts = button_texts
        self._strong_texts = strong_texts

    async def count(self):
        return self._count

    async def inner_text(self):
        return self._inner_text

    async def all_inner_texts(self):
        if self._button_texts is not None:
            return self._button_texts
        if self._strong_texts is not None:
            return self._strong_texts
        return []

    @property
    def first(self):
        return self

    def filter(self, **kwargs):
        return self

    def locator(self, selector):
        if selector == "button":
            return ChainableLocator(button_texts=self._button_texts)
        if selector == "strong":
            return ChainableLocator(strong_texts=self._strong_texts)
        return ChainableLocator()

    def __getattr__(self, name):
        if name in ("first",):
            return self
        return self


def build_page_mock(article_text="", buttons=None, strong_texts=None, heading_count=1):
    page = MagicMock()
    page.is_closed.return_value = False

    article_locator = ChainableLocator(
        inner_text_val=article_text,
        button_texts=buttons if buttons is not None else [],
        strong_texts=strong_texts if strong_texts is not None else [],
    )

    heading = ChainableLocator(
        count_val=heading_count,
        inner_text_val=article_text,
        button_texts=buttons if buttons is not None else [],
        strong_texts=strong_texts if strong_texts is not None else [],
    )
    heading.locator = lambda sel: article_locator

    def locator_side_effect(selector, **kwargs):
        if selector == 'article h2':
            return heading
        return ChainableLocator()

    page.locator = MagicMock(side_effect=locator_side_effect)
    return page


# --- Tests for _parse_page ---

@pytest.mark.asyncio
async def test_namecheap_parse_available_with_price(adapter):
    page = build_page_mock(
        article_text="example.com is available\n$9.98",
        buttons=["Add to cart"],
        strong_texts=["$9.98"],
        heading_count=1,
    )
    result = await adapter._parse_page(page, "example.com", "https://link")
    assert result.domain == "example.com"
    assert result.status == "available"
    assert result.price == "$9.98"
    assert result.currency == "USD"
    assert result.source == "namecheap_page"
    assert len(result.prices) == 1
    assert result.prices[0].source == "namecheap"
    assert result.prices[0].price == "$9.98"
    assert result.prices[0].link == "https://link"


@pytest.mark.asyncio
async def test_namecheap_parse_available_without_price(adapter):
    page = build_page_mock(
        article_text="example.com is available",
        buttons=["Add to cart"],
        strong_texts=[],
        heading_count=1,
    )
    result = await adapter._parse_page(page, "example.com", "https://link")
    assert result.status == "available"
    assert result.price is None
    assert result.currency is None


@pytest.mark.asyncio
async def test_namecheap_parse_premium_with_price(adapter):
    page = build_page_mock(
        article_text="example.com\npremium\n$2,488.00",
        buttons=["Add to cart"],
        strong_texts=["$2,488.00"],
        heading_count=1,
    )
    result = await adapter._parse_page(page, "example.com", "https://link")
    assert result.status == "premium"
    assert result.price == "$2,488.00"
    assert result.currency == "USD"


@pytest.mark.asyncio
async def test_namecheap_parse_taken_registered(adapter):
    page = build_page_mock(
        article_text="example.com\nregistered\nTaken",
        buttons=["Whois"],
        strong_texts=[],
        heading_count=1,
    )
    result = await adapter._parse_page(page, "example.com", "https://link")
    assert result.status == "taken"
    assert result.source == "namecheap_page"


@pytest.mark.asyncio
async def test_namecheap_parse_taken_make_offer_button(adapter):
    page = build_page_mock(
        article_text="example.com\nmake offer",
        buttons=["Make offer"],
        strong_texts=["$1,000"],
        heading_count=1,
    )
    result = await adapter._parse_page(page, "example.com", "https://link")
    assert result.status == "taken"
    assert result.prices[0].price == "$1,000"
    assert result.prices[0].currency == "USD"


@pytest.mark.asyncio
async def test_namecheap_parse_no_heading_fallback_to_aftermarket(adapter):
    page = build_page_mock(heading_count=0)

    with patch.object(adapter, "_aftermarket_fallback", new=AsyncMock(return_value=DomainCheckResult(
        domain="example.com",
        status="available",
        source="aftermarket_api",
        prices=[],
    ))) as mock_fallback:
        result = await adapter._parse_page(page, "example.com", "https://link")
        mock_fallback.assert_awaited_once_with("example.com", "https://link")
        assert result.status == "available"
        assert result.source == "aftermarket_api"


@pytest.mark.asyncio
async def test_namecheap_parse_no_heading_and_no_fallback_returns_unknown(adapter):
    page = build_page_mock(heading_count=0)
    with patch.object(adapter, "_aftermarket_fallback", new=AsyncMock(return_value=None)):
        result = await adapter._parse_page(page, "example.com", "https://link")
        assert result.status == "unknown"
        assert result.detail == "Domain card not found on page"


# --- Tests for _aftermarket_fallback ---

@pytest.mark.asyncio
async def test_namecheap_aftermarket_notfound_returns_available(adapter):
    mock_response = MagicMock()
    mock_response.json.return_value = {"type": "ok", "data": [{"status": "notfound", "price": 998}]}
    adapter._client.get = AsyncMock(return_value=mock_response)

    result = await adapter._aftermarket_fallback("example.com", "https://link")
    assert result.status == "available"
    # _aftermarket_fallback puts the price inside prices[], not the top-level price field
    assert result.prices[0].price == "$9.98"
    assert result.prices[0].currency == "USD"
    assert result.source == "aftermarket_api"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["active", "sold", "pending"])
async def test_namecheap_aftermarket_taken_statuses(adapter, status):
    mock_response = MagicMock()
    mock_response.json.return_value = {"type": "ok", "data": [{"status": status, "price": 50000}]}
    adapter._client.get = AsyncMock(return_value=mock_response)

    result = await adapter._aftermarket_fallback("example.com", "https://link")
    assert result.status == "taken"
    assert result.prices[0].price == "$500.00"
    assert result.source == "aftermarket_api"


@pytest.mark.asyncio
async def test_namecheap_aftermarket_no_data_returns_none(adapter):
    mock_response = MagicMock()
    mock_response.json.return_value = {"type": "ok", "data": []}
    adapter._client.get = AsyncMock(return_value=mock_response)

    result = await adapter._aftermarket_fallback("example.com", "https://link")
    assert result is None


@pytest.mark.asyncio
async def test_namecheap_aftermarket_exception_returns_none(adapter):
    adapter._client.get = AsyncMock(side_effect=Exception("network error"))
    result = await adapter._aftermarket_fallback("example.com", "https://link")
    assert result is None


# --- Tests for _check_single (page.goto path) ---

@pytest.mark.asyncio
async def test_namecheap_check_single_exception_triggers_fallback(adapter, mock_page):
    mock_page.goto.side_effect = Exception("timeout")
    with patch.object(adapter, "_aftermarket_fallback", new=AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="taken", source="aftermarket_api", prices=[]
    ))) as mock_fallback:
        result = await adapter._check_single(mock_page, "example.com")
        assert result.status == "taken"
        assert result.source == "aftermarket_api"
        mock_fallback.assert_awaited_once()


@pytest.mark.asyncio
async def test_namecheap_check_single_exception_no_fallback_returns_unknown(adapter, mock_page):
    mock_page.goto.side_effect = Exception("timeout")
    with patch.object(adapter, "_aftermarket_fallback", new=AsyncMock(return_value=None)):
        result = await adapter._check_single(mock_page, "example.com")
        assert result.status == "unknown"
        assert "timeout" in result.detail


@pytest.mark.asyncio
async def test_namecheap_check_single_closes_cookie_dialog(adapter):
    page = MagicMock()
    page.is_closed.return_value = False
    page.goto = AsyncMock(return_value=None)

    close_btn = AsyncMock()
    close_btn.is_visible.return_value = True

    def locator_side_effect(selector, **kwargs):
        if selector == 'article h2':
            return build_page_mock(
                article_text="example.com is available", buttons=["Add to cart"], strong_texts=[], heading_count=1
            ).locator(selector)
        if selector == 'button:has-text("Close")':
            mock_loc = MagicMock()
            mock_loc.first = close_btn
            return mock_loc
        return ChainableLocator()

    page.locator = MagicMock(side_effect=locator_side_effect)

    with patch.object(adapter, "_parse_page", new=AsyncMock(return_value=DomainCheckResult(
        domain="example.com", status="available", source="namecheap_page", prices=[]
    ))) as mock_parse:
        result = await adapter._check_single(page, "example.com")
        close_btn.click.assert_awaited_once()
        mock_parse.assert_awaited_once()


# --- Tests for start / stop / is_ready ---

@pytest.mark.asyncio
async def test_namecheap_start_and_stop():
    adapter = NamecheapAdapter()
    with patch("playwright.async_api.async_playwright") as mock_pw_factory:
        mock_pw = AsyncMock()
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        mock_browser.close = AsyncMock()
        mock_pw.firefox.launch.return_value = mock_browser

        mock_instance = MagicMock()
        mock_instance.start = AsyncMock(return_value=mock_pw)
        mock_pw_factory.return_value = mock_instance

        await adapter.start()
        assert adapter.is_ready() is True

        await adapter.stop()
        assert adapter._browser is None
        assert adapter._page is None
        mock_browser.close.assert_awaited_once()


def test_namecheap_is_ready_before_start():
    adapter = NamecheapAdapter()
    assert adapter.is_ready() is False
