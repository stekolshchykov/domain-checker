from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    playwright_headless: bool = True
    rate_limit_seconds: float = 5.0
    page_timeout_ms: int = 15000
    test_base_url: str = "http://api:8000"
    long_health_check_domain: str = "this-is-very-long-health-check-domain-name-test-1234567890.com"

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
