import re as _re
from typing import Optional

import httpx

from src.models import DomainCheckResult, PriceOption
from src.adapters.base import RegistrarAdapter


class LetsHostAdapter(RegistrarAdapter):
    name = "letshost"

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=8.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Content-Type": "application/x-www-form-urlencoded",
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
                    source="letshost",
                    detail="Invalid domain format",
                    prices=[],
                )
            sld, tld = parts

            # WHMCS domain checker endpoint
            url = "https://billing.letshost.ie/domainchecker.php"
            data = {
                "domain": sld,
                f"tld[]": f".{tld}",
            }
            resp = await self._client.post(url, data=data)
            text = resp.text
            text_lower = text.lower()

            # Strong taken signals first
            taken_signals = [
                "not available",
                "unavailable",
                "already registered",
                "domain is not available",
            ]
            if any(s in text_lower for s in taken_signals):
                return DomainCheckResult(
                    domain=domain,
                    status="taken",
                    source="letshost",
                    prices=[PriceOption(source="letshost", link=link)],
                )

            # Strong available signals
            available_signals = [
                "domain is available",
                "congratulations",
                "available to register",
            ]
            if any(s in text_lower for s in available_signals):
                price = None
                currency = "EUR"
                price_match = _re.search(r'€\s*([0-9]+(?:\.[0-9]{2})?)', text)
                if not price_match:
                    price_match = _re.search(r'\$\s*([0-9]+(?:\.[0-9]{2})?)', text)
                    if price_match:
                        currency = "USD"
                if price_match:
                    price = f"{'€' if currency == 'EUR' else '$'}{price_match.group(1)}"

                return DomainCheckResult(
                    domain=domain,
                    status="available",
                    price=price,
                    currency=currency,
                    source="letshost",
                    prices=[PriceOption(source="letshost", price=price, currency=currency, link=link)],
                )

            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source="letshost",
                detail="Could not determine availability from response",
                prices=[],
            )
        except Exception as exc:
            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source="letshost",
                detail=str(exc),
                prices=[],
            )

    def _build_link(self, domain: str) -> Optional[str]:
        return f"https://billing.letshost.ie/cart.php?a=add&domain=register&query={domain}"
