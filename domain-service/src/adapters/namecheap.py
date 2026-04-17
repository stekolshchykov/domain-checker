from __future__ import annotations

import json
from typing import Optional

from src.adapters.base import RegistrarAdapter
from src.availability_parser import KeywordRules, ParserResult, parse_with_keyword_rules
from src.models import FinalStatus, ProviderResult
from src.request_runner import ProviderRuntimeConfig


_NAMECHEAP_RULES = KeywordRules(
    available=("is available", "add to cart", "buy now", "available to register"),
    unavailable=("is taken", "registered", "already registered", "domain is unavailable"),
    premium=("premium", "make offer", "aftermarket"),
    promo=("first year", "special offer", "save"),
)


class NamecheapAdapter(RegistrarAdapter):
    name = "namecheap"
    display_name = "Namecheap"
    runtime = ProviderRuntimeConfig(
        max_concurrency=3,
        min_interval_seconds=0.1,
        timeout_seconds=10.0,
        retries=2,
        cache_ttl_seconds=20.0,
    )

    def build_source_url(self, domain: str) -> Optional[str]:
        return f"https://www.namecheap.com/domains/registration/results/?domain={domain}"

    async def check_domain(self, domain: str) -> ProviderResult:
        source_url = self.build_source_url(domain)
        parser_error: Optional[str] = None

        try:
            page_result = await self.runner.request(
                self.name,
                "GET",
                source_url,
                timeout_seconds=self.runtime.timeout_seconds,
                retries=self.runtime.retries,
                cache_ttl_seconds=self.runtime.cache_ttl_seconds,
            )
            parser = parse_with_keyword_rules(page_result.text, domain, _NAMECHEAP_RULES)
            if parser.final_status not in (FinalStatus.PARSING_FAILED, FinalStatus.UNKNOWN):
                return self._to_provider_result(
                    domain=domain,
                    parser=parser,
                    request_result=page_result,
                    source_url=source_url,
                    fallback_used=False,
                )
            parser_error = parser.note
        except Exception as exc:
            parser_error = str(exc)

        fallback = await self._aftermarket_fallback(domain, source_url)
        if fallback is not None:
            return fallback

        return self._error_result(
            domain=domain,
            final_status=FinalStatus.PARSING_FAILED,
            detail=parser_error or "Namecheap parser failed",
            source_url=source_url,
            request_url=source_url,
            fallback_used=True,
        )

    async def _aftermarket_fallback(self, domain: str, source_url: str) -> ProviderResult | None:
        api_url = f"https://aftermarket.namecheapapi.com/domain/status?domain={domain}"
        try:
            response = await self.runner.request(
                self.name,
                "GET",
                api_url,
                timeout_seconds=8.0,
                retries=2,
                cache_ttl_seconds=15.0,
            )
            payload = json.loads(response.text)
            data = payload.get("data") or []
            if payload.get("type") != "ok" or not data:
                return None

            item = data[0]
            status = str(item.get("status", "")).lower()
            cents = item.get("price")
            price = None
            if isinstance(cents, (int, float)):
                price = f"${float(cents) / 100:.2f}"

            if status == "notfound":
                parser = ParserResult(
                    final_status=FinalStatus.UNKNOWN,
                    registration_price=price,
                    currency="USD" if price else None,
                    note="aftermarket fallback: no listing (not availability proof)",
                    confidence=0.25,
                )
                return self._to_provider_result(
                    domain=domain,
                    parser=parser,
                    request_result=response,
                    source_url=source_url,
                    fallback_used=True,
                )

            if status in ("active", "sold", "pending"):
                parser = ParserResult(
                    final_status=FinalStatus.UNAVAILABLE,
                    registration_price=price,
                    currency="USD" if price else None,
                    premium=bool(price),
                    note=f"aftermarket fallback: {status}",
                    confidence=0.84,
                )
                return self._to_provider_result(
                    domain=domain,
                    parser=parser,
                    request_result=response,
                    source_url=source_url,
                    fallback_used=True,
                )
            return None
        except Exception:
            return None

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def is_ready(self) -> bool:
        return True
