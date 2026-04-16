from typing import Optional

import httpx

from src.models import DomainCheckResult, PriceOption
from src.adapters.base import RegistrarAdapter


class CloudflareAdapter(RegistrarAdapter):
    name = "cloudflare"

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
            # Cloudflare's public domains page sometimes exposes availability via an internal API
            # Try the zone available endpoint (often requires auth, but worth a shot for some TLDs)
            api_url = f"https://api.cloudflare.com/client/v4/zones/name/available/{domain}"
            resp = await self._client.get(api_url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and "result" in data:
                    result = data["result"]
                    available = result.get("available")
                    price = result.get("price")
                    currency = "USD"
                    price_str = None
                    if isinstance(price, (int, float)):
                        price_str = f"${price:.2f}"

                    if available is True:
                        return DomainCheckResult(
                            domain=domain,
                            status="available",
                            price=price_str,
                            currency=currency,
                            source="cloudflare_api",
                            prices=[PriceOption(source="cloudflare", price=price_str, currency=currency, link=link)],
                        )
                    elif available is False:
                        return DomainCheckResult(
                            domain=domain,
                            status="taken",
                            source="cloudflare_api",
                            prices=[PriceOption(source="cloudflare", price=price_str, currency=currency, link=link)],
                        )

            # Fallback: try the public search page for any JSON hints
            search_url = f"https://domains.cloudflare.com/?domain={domain}"
            search_resp = await self._client.get(search_url)
            text = search_resp.text.lower()
            if '"available":true' in text or '"isavailable":true' in text:
                return DomainCheckResult(
                    domain=domain,
                    status="available",
                    source="cloudflare_page",
                    prices=[PriceOption(source="cloudflare", link=link)],
                )
            if '"available":false' in text or '"isavailable":false' in text:
                return DomainCheckResult(
                    domain=domain,
                    status="taken",
                    source="cloudflare_page",
                    prices=[PriceOption(source="cloudflare", link=link)],
                )

            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source="cloudflare",
                detail="Could not determine availability",
                prices=[],
            )
        except Exception as exc:
            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source="cloudflare",
                detail=str(exc),
                prices=[],
            )

    def _build_link(self, domain: str) -> Optional[str]:
        return f"https://domains.cloudflare.com/?domain={domain}"
