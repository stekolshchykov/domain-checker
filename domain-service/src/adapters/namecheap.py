import asyncio
import time
from typing import Optional

import httpx
from playwright.async_api import Page, Browser

from src.config import settings
from src.models import DomainCheckResult, PriceOption
from src.adapters.base import RegistrarAdapter


class NamecheapAdapter(RegistrarAdapter):
    name = "namecheap"

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._client = httpx.AsyncClient(timeout=10.0)

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.firefox.launch(
            headless=settings.playwright_headless,
        )
        self._last_request_at = 0.0

    async def stop(self) -> None:
        await self._client.aclose()
        if self._page:
            await self._page.close()
            self._page = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def _ensure_page(self) -> Page:
        if self._page is None or self._page.is_closed():
            context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
            )
            self._page = await context.new_page()
        return self._page

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        delay = settings.rate_limit_seconds - elapsed
        if delay > 0:
            await asyncio.sleep(delay)
        self._last_request_at = time.monotonic()

    async def check_domain(self, domain: str) -> DomainCheckResult:
        async with self._lock:
            page = await self._ensure_page()
            await self._throttle()
            return await self._check_single(page, domain.strip().lower())

    def _build_link(self, domain: str) -> Optional[str]:
        return f"https://www.namecheap.com/domains/registration/results/?domain={domain}"

    async def _check_single(self, page: Page, domain: str) -> DomainCheckResult:
        url = f"https://www.namecheap.com/domains/registration/results/?domain={domain}"
        link = self._build_link(domain)
        try:
            await page.goto(url, wait_until="networkidle", timeout=settings.page_timeout_ms)
            await asyncio.sleep(2)

            # Try to close cookie dialog if present
            try:
                close_btn = page.locator('button:has-text("Close")').first
                if await close_btn.is_visible(timeout=2000):
                    await close_btn.click()
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            return await self._parse_page(page, domain, link)
        except Exception as exc:
            fallback = await self._aftermarket_fallback(domain, link)
            if fallback:
                return fallback
            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source="unknown",
                detail=str(exc),
                prices=[],
            )

    async def _parse_page(self, page: Page, domain: str, link: str) -> DomainCheckResult:
        heading_locator = page.locator('article h2').filter(has_text=domain).first

        if await heading_locator.count() == 0:
            fallback = await self._aftermarket_fallback(domain, link)
            if fallback:
                return fallback
            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source="unknown",
                detail="Domain card not found on page",
                prices=[],
            )

        article = heading_locator.locator("xpath=../../..")
        article_text = (await article.inner_text()).lower()
        article_words = set(article_text.split())
        buttons = await article.locator("button").all_inner_texts()
        buttons_lower = [b.lower() for b in buttons]

        is_premium = "premium" in article_words
        is_taken = (
            "taken" in article_words
            or "registered" in article_words
            or "make offer" in buttons_lower
        )

        price = None
        currency = None
        strong_texts = await article.locator("strong").all_inner_texts()
        for text in strong_texts:
            text = text.strip()
            if any(sym in text for sym in ["€", "$", "£"]):
                price = text
                if "€" in text:
                    currency = "EUR"
                elif "$" in text:
                    currency = "USD"
                elif "£" in text:
                    currency = "GBP"
                break

        if is_taken:
            return DomainCheckResult(
                domain=domain,
                status="taken",
                source="namecheap_page",
                prices=[PriceOption(source="namecheap", price=price, currency=currency, link=link)],
            )

        status = "premium" if is_premium else "available"
        return DomainCheckResult(
            domain=domain,
            status=status,
            price=price,
            currency=currency,
            source="namecheap_page",
            prices=[PriceOption(source="namecheap", price=price, currency=currency, link=link)],
        )

    async def _aftermarket_fallback(self, domain: str, link: str) -> Optional[DomainCheckResult]:
        try:
            url = f"https://aftermarket.namecheapapi.com/domain/status?domain={domain}"
            resp = await self._client.get(url)
            data = resp.json()
            if data.get("type") == "ok" and data.get("data"):
                item = data["data"][0]
                status = item.get("status")
                price = None
                currency = None
                price_str = None
                if item.get("price"):
                    price_str = f"${item['price'] / 100:.2f}"
                    price = price_str
                    currency = "USD"

                if status == "notfound":
                    return DomainCheckResult(
                        domain=domain,
                        status="available",
                        source="aftermarket_api",
                        prices=[PriceOption(source="namecheap", price=price, currency=currency, link=link)],
                    )
                elif status in ("active", "sold", "pending"):
                    return DomainCheckResult(
                        domain=domain,
                        status="taken",
                        price=price_str,
                        currency=currency,
                        source="aftermarket_api",
                        prices=[PriceOption(source="namecheap", price=price, currency=currency, link=link)],
                    )
        except Exception:
            pass
        return None

    def is_ready(self) -> bool:
        return self._browser is not None and self._browser.is_connected()
