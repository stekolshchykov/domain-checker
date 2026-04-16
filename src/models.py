import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

DOMAIN_RE = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)+$"
)


class DomainCheckResult(BaseModel):
    domain: str
    status: str = Field(..., pattern="^(available|taken|premium|unknown)$")
    price: Optional[str] = None
    currency: Optional[str] = None
    source: str = Field(default="unknown")
    detail: Optional[str] = None


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
