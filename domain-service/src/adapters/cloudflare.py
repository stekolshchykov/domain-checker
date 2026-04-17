from __future__ import annotations

import json
from typing import Optional

from src.adapters.base import RegistrarAdapter
from src.availability_parser import KeywordRules, ParserResult, parse_with_keyword_rules
from src.models import FinalStatus, ProviderResult
from src.request_runner import ProviderRuntimeConfig


_CLOUDFLARE_RULES = KeywordRules(
    available=("available", "can be registered"),
    unavailable=("unavailable", "already registered", "taken"),
    blocked=("log in", "sign in", "dash.cloudflare.com/login", "access denied", "captcha"),
)


class CloudflareAdapter(RegistrarAdapter):
    name = "cloudflare"
    display_name = "Cloudflare Registrar"
    runtime = ProviderRuntimeConfig(
        max_concurrency=2,
        min_interval_seconds=0.2,
        timeout_seconds=8.0,
        retries=2,
        cache_ttl_seconds=20.0,
    )

    def build_source_url(self, domain: str) -> Optional[str]:
        return f"https://dash.cloudflare.com/domains/register?domain={domain}"

    async def check_domain(self, domain: str) -> ProviderResult:
        source_url = self.build_source_url(domain)
        api_url = f"https://api.cloudflare.com/client/v4/zones/name/available/{domain}"

        try:
            api_result = await self.runner.request(
                self.name,
                "GET",
                api_url,
                timeout_seconds=self.runtime.timeout_seconds,
                retries=1,
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
                retries=1,
                cache_ttl_seconds=5.0,
            )
            parser = parse_with_keyword_rules(page_result.text, domain, _CLOUDFLARE_RULES)
            return self._to_provider_result(
                domain=domain,
                parser=parser,
                request_result=page_result,
                source_url=source_url,
                fallback_used=True,
            )
        except Exception as exc:
            # Cloudflare registrar flow is account-walled for most users.
            return self._error_result(
                domain=domain,
                final_status=FinalStatus.BLOCKED,
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

        if not isinstance(payload, dict):
            return None

        if payload.get("success") is not True:
            return None

        result = payload.get("result") or {}
        available = result.get("available")
        price = result.get("price")

        price_str = None
        if isinstance(price, (int, float)):
            price_str = f"${float(price):.2f}"

        if available is True:
            return ParserResult(
                final_status=FinalStatus.STANDARD_PRICE if price_str else FinalStatus.AVAILABLE,
                registration_price=price_str,
                currency="USD" if price_str else None,
                note="cloudflare api",
                confidence=0.9,
            )

        if available is False:
            return ParserResult(
                final_status=FinalStatus.UNAVAILABLE,
                registration_price=price_str,
                currency="USD" if price_str else None,
                note="cloudflare api",
                confidence=0.9,
            )

        return None
