from __future__ import annotations

import json
from typing import Optional

from src.adapters.base import RegistrarAdapter
from src.availability_parser import KeywordRules, ParserResult, parse_with_keyword_rules
from src.models import FinalStatus, ProviderResult
from src.request_runner import ProviderRuntimeConfig


_GODADDY_RULES = KeywordRules(
    available=("is available", "available now", "add to cart", "buy it now"),
    unavailable=("is taken", "already taken", "not available", "registered"),
    premium=("premium domain", "broker service", "make offer"),
    promo=("save", "first year", "discount"),
)


class GoDaddyAdapter(RegistrarAdapter):
    name = "godaddy"
    display_name = "GoDaddy"
    runtime = ProviderRuntimeConfig(
        max_concurrency=3,
        min_interval_seconds=0.12,
        timeout_seconds=8.0,
        retries=2,
        cache_ttl_seconds=20.0,
    )

    def build_source_url(self, domain: str) -> Optional[str]:
        return f"https://www.godaddy.com/domainsearch/find?domainToCheck={domain}"

    async def check_domain(self, domain: str) -> ProviderResult:
        source_url = self.build_source_url(domain)
        sld, tld = self._split_domain(domain)
        api_url = f"https://www.godaddy.com/domainfind/v1/search/exact?q={sld}&tld={tld}"

        try:
            api_result = await self.runner.request(
                self.name,
                "GET",
                api_url,
                timeout_seconds=self.runtime.timeout_seconds,
                retries=self.runtime.retries,
                cache_ttl_seconds=self.runtime.cache_ttl_seconds,
            )
            parser = self._parse_api_response(api_result.text)
            if parser is not None:
                return self._to_provider_result(
                    domain=domain,
                    parser=parser,
                    request_result=api_result,
                    source_url=source_url,
                    fallback_used=False,
                )
        except Exception:
            pass

        try:
            page_result = await self.runner.request(
                self.name,
                "GET",
                source_url,
                timeout_seconds=self.runtime.timeout_seconds,
                retries=self.runtime.retries,
                cache_ttl_seconds=self.runtime.cache_ttl_seconds,
            )
            parser = parse_with_keyword_rules(page_result.text, domain, _GODADDY_RULES)
            return self._to_provider_result(
                domain=domain,
                parser=parser,
                request_result=page_result,
                source_url=source_url,
                fallback_used=True,
            )
        except Exception as exc:
            error_lower = str(exc).lower()
            if "rate" in error_lower:
                status = FinalStatus.RATE_LIMITED
            elif "blocked" in error_lower:
                status = FinalStatus.BLOCKED
            elif "temporary" in error_lower:
                status = FinalStatus.TEMPORARILY_UNAVAILABLE
            else:
                status = FinalStatus.UNKNOWN
            return self._error_result(
                domain=domain,
                final_status=status,
                detail=str(exc),
                source_url=source_url,
                request_url=source_url,
                fallback_used=True,
            )

    def _parse_api_response(self, body: str) -> ParserResult | None:
        try:
            payload = json.loads(body)
        except Exception:
            return None

        exact = payload.get("ExactMatchDomain") or {}
        is_available = exact.get("IsAvailable")
        price_info = exact.get("PriceInfo") or exact.get("Price")

        price = None
        currency = "USD"
        if isinstance(price_info, dict):
            price = price_info.get("ListPriceDisplay")
            currency = price_info.get("Currency") or "USD"
        elif isinstance(price_info, (int, float)):
            price = f"${float(price_info):.2f}"
            currency = "USD"

        if is_available is True:
            final_status = FinalStatus.STANDARD_PRICE if price else FinalStatus.AVAILABLE
            return ParserResult(
                final_status=final_status,
                registration_price=price,
                currency=currency,
                note="godaddy api",
                confidence=0.95,
            )
        if is_available is False:
            return ParserResult(
                final_status=FinalStatus.UNAVAILABLE,
                registration_price=price,
                currency=currency,
                premium=bool(price and "," in price),
                note="godaddy api",
                confidence=0.95,
            )

        return None

    def _split_domain(self, domain: str) -> tuple[str, str]:
        if "." not in domain:
            return domain, ""
        sld, tld = domain.rsplit(".", 1)
        return sld, tld
