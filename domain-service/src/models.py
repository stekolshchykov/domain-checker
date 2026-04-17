import re
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

DOMAIN_RE = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)+$"
)
LEGACY_STATUS_PATTERN = "^(available|taken|premium|unknown)$"


class FinalStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PREMIUM = "premium"
    DISCOUNTED = "discounted"
    STANDARD_PRICE = "standard_price"
    TRANSFER_ONLY = "transfer_only"
    UNSUPPORTED_TLD = "unsupported_tld"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    PARSING_FAILED = "parsing_failed"
    UNKNOWN = "unknown"


def final_status_to_legacy(status: FinalStatus, premium_flag: bool = False) -> str:
    if status == FinalStatus.PREMIUM:
        return "premium"
    if premium_flag and status in (FinalStatus.AVAILABLE, FinalStatus.DISCOUNTED, FinalStatus.STANDARD_PRICE):
        return "premium"
    if status in (FinalStatus.AVAILABLE, FinalStatus.DISCOUNTED, FinalStatus.STANDARD_PRICE):
        return "available"
    if status in (FinalStatus.UNAVAILABLE, FinalStatus.TRANSFER_ONLY):
        return "taken"
    return "unknown"


class PriceOption(BaseModel):
    source: str
    status: FinalStatus = FinalStatus.UNKNOWN
    price: Optional[str] = None
    renewal_price: Optional[str] = None
    currency: Optional[str] = None
    link: Optional[str] = None
    premium: bool = False
    promo: bool = False
    note: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ProviderDebugInfo(BaseModel):
    registrar: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    outcome: str
    request_url: Optional[str] = None
    source_url: Optional[str] = None
    http_status: Optional[int] = None
    attempts: int = 0
    cache_hit: bool = False
    fallback_used: bool = False
    parser_error: Optional[str] = None
    blocked: bool = False
    rate_limited: bool = False
    provider_reliability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    note: Optional[str] = None


class ProviderResult(BaseModel):
    registrar: str
    domain: str
    status: str = Field(..., pattern=LEGACY_STATUS_PATTERN)
    final_status: FinalStatus = FinalStatus.UNKNOWN
    registration_price: Optional[str] = None
    renewal_price: Optional[str] = None
    currency: Optional[str] = None
    premium: bool = False
    promo: bool = False
    source: str = "unknown"
    source_url: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    detail: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    prices: List[PriceOption] = Field(default_factory=list)
    debug: Optional[ProviderDebugInfo] = None


class DomainCheckResult(BaseModel):
    domain: str
    status: str = Field(default="unknown", pattern=LEGACY_STATUS_PATTERN)
    final_status: FinalStatus = FinalStatus.UNKNOWN
    registrar: str = "aggregated"
    price: Optional[str] = None
    registration_price: Optional[str] = None
    renewal_price: Optional[str] = None
    currency: Optional[str] = None
    premium: bool = False
    promo: bool = False
    source: str = "unknown"
    source_url: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    detail: Optional[str] = None
    note: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    prices: List[PriceOption] = Field(default_factory=list)
    provider_results: List[ProviderResult] = Field(default_factory=list)

    @field_validator("price", mode="after")
    @classmethod
    def normalize_price(cls, value: Optional[str], info):
        if value is not None:
            return value.strip()
        if "registration_price" in info.data and info.data["registration_price"]:
            return info.data["registration_price"]
        return value


class CheckRequest(BaseModel):
    domains: List[str] = Field(..., min_length=1)

    @field_validator("domains", mode="before")
    @classmethod
    def validate_domains(cls, v):
        if not isinstance(v, list):
            raise ValueError("domains must be a list")
        if len(v) == 0:
            raise ValueError("domains must contain at least 1 item")
        for d in v:
            if not isinstance(d, str) or not d.strip():
                raise ValueError("each domain must be a non-empty string")
            if not DOMAIN_RE.match(d.strip().lower()):
                raise ValueError(f"'{d}' is not a valid domain format")
        return v


class CheckResponse(BaseModel):
    results: List[DomainCheckResult]
    checked_at: datetime
    total_checks: int


class HealthResponse(BaseModel):
    status: str
    browser_ready: bool
    timestamp: datetime


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    error: dict
