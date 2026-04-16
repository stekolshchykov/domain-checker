import asyncio
import json
from typing import Optional

import httpx

from src.models import DomainCheckResult, PriceOption
from src.adapters.base import RegistrarAdapter


class GoDaddyAdapter(RegistrarAdapter):
    name = "godaddy"

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=8.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
        )

    async def check_domain(self, domain: str) -> DomainCheckResult:
        link = self._build_link(domain)
        try:
            parts = domain.rsplit(".", 1)
            if len(parts) != 2:
                return DomainCheckResult(
                    domain=domain,
                    status="unknown",
                    source="godaddy",
                    detail="Invalid domain format",
                    prices=[],
                )
            sld, tld = parts
            api_url = f"https://www.godaddy.com/domainfind/v1/search/exact?q={sld}&tld={tld}"
            fallback_url = (
                f"https://www.godaddy.com/en/domainsearch/find"
                f"?checkAvail=1&domainToCheck={domain}"
            )

            # Run API and fallback requests in parallel for speed
            api_task = self._client.get(api_url)
            fallback_task = self._client.get(fallback_url)
            api_resp, fallback_resp = await asyncio.gather(api_task, fallback_task)

            if api_resp.status_code == 200:
                data = api_resp.json()
                exact = data.get("ExactMatchDomain") or {}
                is_available = exact.get("IsAvailable")
                price_info = exact.get("Price") or exact.get("PriceInfo")
                price = None
                currency = "USD"
                if isinstance(price_info, (int, float)):
                    price = f"${price_info:.2f}"
                elif isinstance(price_info, dict):
                    price = price_info.get("ListPriceDisplay")
                    currency = price_info.get("Currency", "USD")

                if is_available is True:
                    return DomainCheckResult(
                        domain=domain,
                        status="available",
                        price=price,
                        currency=currency,
                        source="godaddy_api",
                        prices=[PriceOption(source="godaddy", price=price, currency=currency, link=link)],
                    )
                elif is_available is False:
                    return DomainCheckResult(
                        domain=domain,
                        status="taken",
                        source="godaddy_api",
                        prices=[PriceOption(source="godaddy", price=price, currency=currency, link=link)],
                    )

            text = fallback_resp.text.lower()
            if '"isavailable":true' in text or '"available":true' in text:
                return DomainCheckResult(
                    domain=domain,
                    status="available",
                    source="godaddy_page",
                    prices=[PriceOption(source="godaddy", link=link)],
                )
            if '"isavailable":false' in text or '"available":false' in text:
                return DomainCheckResult(
                    domain=domain,
                    status="taken",
                    source="godaddy_page",
                    prices=[PriceOption(source="godaddy", link=link)],
                )

            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source="godaddy",
                detail="Could not determine availability",
                prices=[],
            )
        except Exception as exc:
            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source="godaddy",
                detail=str(exc),
                prices=[],
            )

    def _build_link(self, domain: str) -> Optional[str]:
        return f"https://www.godaddy.com/en/domainsearch/find?domainToCheck={domain}"
