import asyncio
from typing import List, Optional

from src.models import DomainCheckResult, PriceOption
from src.adapters import DEFAULT_ADAPTERS
from src.adapters.base import RegistrarAdapter
from src.adapters.namecheap import NamecheapAdapter


class MultiRegistrarChecker:
    """Checks domain availability across multiple registrars in parallel."""

    def __init__(self):
        self._adapters: List[RegistrarAdapter] = []
        self._namecheap: Optional[NamecheapAdapter] = None
        for adapter_cls in DEFAULT_ADAPTERS:
            adapter = adapter_cls()
            self._adapters.append(adapter)
            if isinstance(adapter, NamecheapAdapter):
                self._namecheap = adapter

    async def start(self) -> None:
        if self._namecheap:
            await self._namecheap.start()

    async def stop(self) -> None:
        if self._namecheap:
            await self._namecheap.stop()
        # HTTP-based adapters may also hold clients; close them gracefully
        for adapter in self._adapters:
            if hasattr(adapter, "_client") and hasattr(adapter._client, "aclose"):
                try:
                    await adapter._client.aclose()
                except Exception:
                    pass

    async def check_domains(self, domains: List[str]) -> List[DomainCheckResult]:
        results = []
        for domain in domains:
            result = await self._check_domain_parallel(domain.strip().lower())
            results.append(result)
        return results

    async def _check_domain_parallel(self, domain: str) -> DomainCheckResult:
        """Run all adapters concurrently and aggregate their results."""
        tasks = [self._run_adapter(adapter, domain) for adapter in self._adapters]
        adapter_results = await asyncio.gather(*tasks, return_exceptions=True)

        successes: List[DomainCheckResult] = []
        details: List[str] = []

        for res in adapter_results:
            if isinstance(res, Exception):
                details.append(str(res))
                continue
            successes.append(res)

        return self._aggregate_results(domain, successes, details)

    async def _run_adapter(self, adapter: RegistrarAdapter, domain: str) -> DomainCheckResult:
        """Wrap adapter call so exceptions become results rather than breaking gather."""
        try:
            return await adapter.check_domain(domain)
        except Exception as exc:
            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source=adapter.name,
                detail=str(exc),
                prices=[],
            )

    def _aggregate_results(
        self,
        domain: str,
        successes: List[DomainCheckResult],
        details: List[str],
    ) -> DomainCheckResult:
        """Aggregate multiple registrar results into one DomainCheckResult."""
        if not successes:
            return DomainCheckResult(
                domain=domain,
                status="unknown",
                source="unknown",
                detail="; ".join(details) if details else "All registrars failed",
                prices=[],
            )

        # Collect all price options from successful checks
        prices: List[PriceOption] = []
        for res in successes:
            for po in res.prices:
                if po.price or po.link:
                    prices.append(po)
            # Also wrap legacy single-price results if prices list is empty
            if not res.prices and (res.price or res.source != "unknown"):
                link = None
                if hasattr(res, "prices") and len(res.prices) == 0:
                    # Try to infer link from source name
                    link = self._infer_link(res.source, domain)
                prices.append(
                    PriceOption(
                        source=self._source_display_name(res.source),
                        price=res.price,
                        currency=res.currency,
                        link=link,
                    )
                )

        # Deduplicate prices by source
        seen = set()
        unique_prices = []
        for po in prices:
            key = (po.source, po.price)
            if key in seen:
                continue
            seen.add(key)
            unique_prices.append(po)

        # Determine overall status by priority
        # Namecheap is the most reliable source, so use its status if available.
        # Fallback to general consensus if Namecheap is not in successes.
        namecheap_result = next(
            (r for r in successes if r.source.startswith("namecheap")), None
        )
        if namecheap_result and namecheap_result.status != "unknown":
            overall_status = namecheap_result.status
        else:
            statuses = [r.status for r in successes]
            if "taken" in statuses:
                overall_status = "taken"
            elif "premium" in statuses:
                overall_status = "premium"
            elif "available" in statuses:
                overall_status = "available"
            else:
                overall_status = "unknown"

        # Pick best representative price for backward compatibility
        # Prefer available with price, then any with price
        best = None
        for res in successes:
            if res.status == overall_status and res.price:
                best = res
                break
        if best is None:
            for res in successes:
                if res.price:
                    best = res
                    break
        if best is None:
            best = successes[0]

        detail_parts = []
        for r in successes:
            if r.detail and r.detail != "Could not determine availability":
                detail_parts.append(r.detail)
        for d in details:
            if d and d != "Could not determine availability":
                detail_parts.append(d)

        return DomainCheckResult(
            domain=domain,
            status=overall_status,
            price=best.price,
            currency=best.currency,
            source="aggregated",
            detail="; ".join(detail_parts) if detail_parts else None,
            prices=unique_prices,
        )

    def _source_display_name(self, source: str) -> str:
        mapping = {
            "namecheap_page": "namecheap",
            "namecheap_api": "namecheap",
            "aftermarket_api": "namecheap",
            "godaddy_api": "godaddy",
            "godaddy_page": "godaddy",
            "letshost": "letshost",
            "cloudflare_api": "cloudflare",
            "cloudflare_page": "cloudflare",
        }
        return mapping.get(source, source)

    def _infer_link(self, source: str, domain: str) -> Optional[str]:
        if "namecheap" in source:
            return f"https://www.namecheap.com/domains/registration/results/?domain={domain}"
        if "godaddy" in source:
            return f"https://www.godaddy.com/en/domainsearch/find?domainToCheck={domain}"
        if "letshost" in source:
            return f"https://billing.letshost.ie/cart.php?a=add&domain=register&query={domain}"
        if "cloudflare" in source:
            return f"https://domains.cloudflare.com/?domain={domain}"
        return None

    def is_ready(self) -> bool:
        if self._namecheap:
            return self._namecheap.is_ready()
        return True
