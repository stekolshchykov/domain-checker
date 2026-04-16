class DomainCheckError(Exception):
    """Base exception for domain checker errors."""
    pass


class BrowserNotReadyError(DomainCheckError):
    pass


class RateLimitExceeded(DomainCheckError):
    pass


class NamecheapUnavailableError(DomainCheckError):
    pass
