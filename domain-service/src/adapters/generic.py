from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote_plus

from src.adapters.base import RegistrarAdapter
from src.availability_parser import KeywordRules, parse_with_keyword_rules
from src.models import FinalStatus, ProviderResult
from src.request_runner import ProviderRuntimeConfig


@dataclass(slots=True)
class RegistrarSpec:
    name: str
    display_name: str
    search_url_template: str
    method: str = "GET"
    payload_template: Optional[dict[str, str]] = None
    headers: Optional[dict[str, str]] = None
    runtime: ProviderRuntimeConfig = field(default_factory=ProviderRuntimeConfig)
    rules: Optional[KeywordRules] = None


class GenericRegistrarAdapter(RegistrarAdapter):
    def __init__(self, runner, spec: RegistrarSpec):
        self.spec = spec
        self.name = spec.name
        self.display_name = spec.display_name
        self.runtime = spec.runtime
        super().__init__(runner)

    def build_source_url(self, domain: str) -> Optional[str]:
        return self._build_url(domain)

    async def check_domain(self, domain: str) -> ProviderResult:
        source_url = self._build_url(domain)
        payload = self._build_payload(domain)

        try:
            request_result = await self.runner.request(
                self.name,
                self.spec.method,
                source_url,
                data=payload,
                headers=self.spec.headers,
                timeout_seconds=self.runtime.timeout_seconds,
                retries=self.runtime.retries,
                cache_ttl_seconds=self.runtime.cache_ttl_seconds,
            )
        except Exception as exc:
            error_lower = str(exc).lower()
            if "circuit open" in error_lower:
                status = FinalStatus.TEMPORARILY_UNAVAILABLE
            elif "rate-limit" in error_lower or "rate limited" in error_lower:
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
            )

        parser = parse_with_keyword_rules(request_result.text, domain, self.spec.rules)
        return self._to_provider_result(
            domain=domain,
            parser=parser,
            request_result=request_result,
            source_url=source_url,
            fallback_used=False,
        )

    def _build_url(self, domain: str) -> str:
        encoded = quote_plus(domain)
        sld, tld = self._split_domain(domain)
        tld_no_dot = tld.lstrip(".")

        url = self.spec.search_url_template
        replacements = {
            "[YOURDOMAIN]": encoded,
            "{domain}": encoded,
            "{raw_domain}": domain,
            "{sld}": quote_plus(sld),
            "{tld}": quote_plus(tld_no_dot),
            "{tld_with_dot}": quote_plus(tld),
        }
        for token, value in replacements.items():
            url = url.replace(token, value)
        return url

    def _build_payload(self, domain: str) -> Optional[dict[str, str]]:
        if not self.spec.payload_template:
            return None

        encoded = quote_plus(domain)
        sld, tld = self._split_domain(domain)
        values = {
            "domain": domain,
            "encoded_domain": encoded,
            "sld": sld,
            "tld": tld,
            "tld_with_dot": tld if tld.startswith(".") else f".{tld}",
        }

        payload: dict[str, str] = {}
        for key, template_value in self.spec.payload_template.items():
            value = template_value
            for token, token_value in values.items():
                value = value.replace(f"{{{token}}}", token_value)
            payload[key] = value
        return payload

    def _split_domain(self, domain: str) -> tuple[str, str]:
        if "." not in domain:
            return domain, ""
        sld, tld = domain.rsplit(".", 1)
        return sld, f".{tld}"
