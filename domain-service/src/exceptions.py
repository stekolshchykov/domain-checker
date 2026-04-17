class DomainCheckError(Exception):
    """Base exception for domain checker errors."""
    pass


class BrowserNotReadyError(DomainCheckError):
    pass


class RateLimitExceeded(DomainCheckError):
    pass


class NamecheapUnavailableError(DomainCheckError):
    pass


class ProviderRequestError(DomainCheckError):
    def __init__(self, provider: str, message: str):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.message = message


class ProviderBlockedError(ProviderRequestError):
    pass


class ProviderRateLimitedError(ProviderRequestError):
    def __init__(self, provider: str, message: str, retry_after: float | None = None):
        super().__init__(provider, message)
        self.retry_after = retry_after


class ProviderTemporarilyUnavailableError(ProviderRequestError):
    pass


class CircuitBreakerOpenError(ProviderRequestError):
    pass
