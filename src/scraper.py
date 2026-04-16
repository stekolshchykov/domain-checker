import asyncio
import time
from typing import List, Optional

import httpx
from playwright.async_api import async_playwright, Page, Browser

from src.config import settings
from src.models import DomainCheckResult


class RateLimitedScraper:
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._client = httpx.AsyncClient(timeout=10.0)

    async def start(self) -> None:
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

    async def check_domains(self, domains: List[str]) -> List[DomainCheckResult]:
        async with self._lock:
            results = []
            page = await self._ensure_page()
            for domain in domains:
                await self._throttle()
                result = await self._check_single(page, domain.strip().lower())
                results.append(result)
            return results

    async def _check_single(self, page: Page, domain: str) -> DomainCheckResult:
        url = f"https://www.namecheap.com/domains/registration/results/?domain={domain}"
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

            return await self._parse_page(page, domain)
        except Exception as exc:
            fallback = await self._aftermarket_fallback(domain)
            if fallback:
                return fallback
            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source="unknown",
                detail=str(exc),
            )

    async def _parse_page(self, page: Page, domain: str) -> DomainCheckResult:
        heading_locator = page.locator('article h2').filter(has_text=domain).first

        if await heading_locator.count() == 0:
            fallback = await self._aftermarket_fallback(domain)
            if fallback:
                return fallback
            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source="unknown",
                detail="Domain card not found on page",
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

        if is_taken:
            return DomainCheckResult(domain=domain, status="taken", source="namecheap_page")

        # Extract price
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

        if is_premium:
            return DomainCheckResult(
                domain=domain,
                status="premium",
                price=price,
                currency=currency,
                source="namecheap_page",
            )

        return DomainCheckResult(
            domain=domain,
            status="available",
            price=price,
            currency=currency,
            source="namecheap_page",
        )

    async def _aftermarket_fallback(self, domain: str) -> Optional[DomainCheckResult]:
        try:
            url = f"https://aftermarket.namecheapapi.com/domain/status?domain={domain}"
            resp = await self._client.get(url)
            data = resp.json()
            if data.get("type") == "ok" and data.get("data"):
                item = data["data"][0]
                status = item.get("status")
                if status == "notfound":
                    return DomainCheckResult(
                        domain=domain,
                        status="available",
                        source="aftermarket_api",
                    )
                elif status in ("active", "sold", "pending"):
                    price = item.get("price")
                    price_str = None
                    if price:
                        price_str = f"${price / 100:.2f}"
                    return DomainCheckResult(
                        domain=domain,
                        status="taken",
                        price=price_str,
                        currency="USD" if price_str else None,
                        source="aftermarket_api",
                    )
        except Exception:
            pass
        return None

    def is_ready(self) -> bool:
        return self._browser is not None and self._browser.is_connected()
