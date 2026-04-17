from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    playwright_headless: bool = True
    rate_limit_seconds: float = 5.0
    page_timeout_ms: int = 15000
    max_concurrent_domains: int = 8
    max_concurrent_requests: int = 35
    request_timeout_seconds: float = 10.0
    request_retry_attempts: int = 3
    request_retry_base_seconds: float = 0.35
    request_retry_jitter_seconds: float = 0.25
    request_cache_ttl_seconds: float = 15.0
    circuit_breaker_failure_threshold: int = 4
    circuit_breaker_open_seconds: float = 30.0
    provider_reliability_alpha: float = 0.15
    provider_reliability_floor: float = 0.2
    test_base_url: str = "http://api:8000"
    long_health_check_domain: str = "this-is-very-long-health-check-domain-name-test-1234567890.com"

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
