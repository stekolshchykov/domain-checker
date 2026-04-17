from __future__ import annotations

from typing import Optional

from src.adapters.base import RegistrarAdapter
from src.availability_parser import KeywordRules, parse_with_keyword_rules
from src.models import FinalStatus, ProviderResult
from src.request_runner import ProviderRuntimeConfig


_LETSHOST_RULES = KeywordRules(
    available=("domain is available", "congratulations", "available to register"),
    unavailable=("already registered", "domain is not available", "not available", "unavailable"),
    blocked=("must login", "access denied", "captcha"),
)


class LetsHostAdapter(RegistrarAdapter):
    name = "letshost"
    display_name = "LetsHost"
    runtime = ProviderRuntimeConfig(
        max_concurrency=2,
        min_interval_seconds=0.25,
        timeout_seconds=8.0,
        retries=2,
        cache_ttl_seconds=20.0,
    )

    def build_source_url(self, domain: str) -> Optional[str]:
        return f"https://billing.letshost.ie/cart.php?a=add&domain=register&query={domain}"

    async def check_domain(self, domain: str) -> ProviderResult:
        source_url = self.build_source_url(domain)
        endpoint = "https://billing.letshost.ie/domainchecker.php"
        sld, tld = self._split_domain(domain)

        payload = {
            "domain": sld,
            "tld[]": tld,
        }

        try:
            request_result = await self.runner.request(
                self.name,
                "POST",
                endpoint,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout_seconds=self.runtime.timeout_seconds,
                retries=self.runtime.retries,
                cache_ttl_seconds=self.runtime.cache_ttl_seconds,
            )
            parser = parse_with_keyword_rules(request_result.text, domain, _LETSHOST_RULES)
            return self._to_provider_result(
                domain=domain,
                parser=parser,
                request_result=request_result,
                source_url=source_url,
                fallback_used=False,
            )
        except Exception as exc:
            error = str(exc).lower()
            if "rate" in error:
                status = FinalStatus.RATE_LIMITED
            elif "blocked" in error:
                status = FinalStatus.BLOCKED
            elif "temporary" in error:
                status = FinalStatus.TEMPORARILY_UNAVAILABLE
            else:
                status = FinalStatus.UNKNOWN
            return self._error_result(
                domain=domain,
                final_status=status,
                detail=str(exc),
                source_url=source_url,
                request_url=endpoint,
            )

    def _split_domain(self, domain: str) -> tuple[str, str]:
        if "." not in domain:
            return domain, ""
        sld, tld = domain.rsplit(".", 1)
        return sld, f".{tld}"
