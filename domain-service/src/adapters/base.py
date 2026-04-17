from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.availability_parser import ParserResult
from src.models import (
    FinalStatus,
    PriceOption,
    ProviderDebugInfo,
    ProviderResult,
    final_status_to_legacy,
)
from src.request_runner import ProviderRuntimeConfig, RequestResult, RequestRunner


@dataclass(slots=True)
class AdapterRequestMeta:
    request_url: str
    source_url: str
    fallback_used: bool = False


class RegistrarAdapter(ABC):
    name: str = "unknown"
    display_name: str = "Unknown"
    runtime: ProviderRuntimeConfig = ProviderRuntimeConfig()

    def __init__(self, runner: RequestRunner):
        self.runner = runner
        self.runner.register_provider(self.name, self.runtime)

    @abstractmethod
    async def check_domain(self, domain: str) -> ProviderResult:
        """Check one domain and return normalized provider-level result."""

    def build_source_url(self, domain: str) -> Optional[str]:
        return None

    def _to_provider_result(
        self,
        *,
        domain: str,
        parser: ParserResult,
        request_result: RequestResult,
        source_url: Optional[str],
        fallback_used: bool,
        detail: Optional[str] = None,
        parser_error: Optional[str] = None,
    ) -> ProviderResult:
        status = final_status_to_legacy(parser.final_status, parser.premium)
        checked_at = datetime.now(timezone.utc)

        option = PriceOption(
            source=self.name,
            status=parser.final_status,
            price=parser.registration_price,
            renewal_price=parser.renewal_price,
            currency=parser.currency,
            link=source_url,
            premium=parser.premium,
            promo=parser.promo,
            note=parser.note,
            confidence=parser.confidence,
        )

        debug = ProviderDebugInfo(
            registrar=self.name,
            started_at=request_result.started_at,
            completed_at=request_result.completed_at,
            duration_ms=request_result.duration_ms,
            outcome="success",
            request_url=request_result.url,
            source_url=source_url,
            http_status=request_result.status_code,
            attempts=request_result.attempts,
            cache_hit=request_result.cache_hit,
            fallback_used=fallback_used,
            parser_error=parser_error,
            blocked=parser.final_status == FinalStatus.BLOCKED,
            rate_limited=parser.final_status == FinalStatus.RATE_LIMITED,
            note=detail or parser.note,
        )

        return ProviderResult(
            registrar=self.name,
            domain=domain,
            status=status,
            final_status=parser.final_status,
            registration_price=parser.registration_price,
            renewal_price=parser.renewal_price,
            currency=parser.currency,
            premium=parser.premium,
            promo=parser.promo,
            source=self.name,
            source_url=source_url,
            checked_at=checked_at,
            detail=detail or parser.note,
            confidence=parser.confidence,
            prices=[option],
            debug=debug,
        )

    def _error_result(
        self,
        *,
        domain: str,
        final_status: FinalStatus,
        detail: str,
        source_url: Optional[str],
        request_url: Optional[str],
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_ms: int = 0,
        attempts: int = 0,
        http_status: Optional[int] = None,
        fallback_used: bool = False,
    ) -> ProviderResult:
        now = datetime.now(timezone.utc)
        started = started_at or now
        completed = completed_at or now

        debug = ProviderDebugInfo(
            registrar=self.name,
            started_at=started,
            completed_at=completed,
            duration_ms=duration_ms,
            outcome="error",
            request_url=request_url,
            source_url=source_url,
            http_status=http_status,
            attempts=attempts,
            cache_hit=False,
            fallback_used=fallback_used,
            blocked=final_status == FinalStatus.BLOCKED,
            rate_limited=final_status == FinalStatus.RATE_LIMITED,
            note=detail,
        )

        return ProviderResult(
            registrar=self.name,
            domain=domain,
            status=final_status_to_legacy(final_status),
            final_status=final_status,
            source=self.name,
            source_url=source_url,
            checked_at=now,
            detail=detail,
            confidence=0.1,
            prices=[],
            debug=debug,
        )
