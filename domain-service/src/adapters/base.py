from abc import ABC, abstractmethod
from typing import Optional

from src.models import DomainCheckResult


class RegistrarAdapter(ABC):
    """Abstract base class for domain registrar availability check adapters."""

    name: str = "unknown"

    @abstractmethod
    async def check_domain(self, domain: str) -> DomainCheckResult:
        """Check availability for a single domain. Must return a DomainCheckResult."""
        ...

    def _build_link(self, domain: str) -> Optional[str]:
        """Return a direct link to the registrar's page for this domain."""
        return None
