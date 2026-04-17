from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.config import settings
from src.exceptions import BrowserNotReadyError, DomainCheckError, NamecheapUnavailableError, RateLimitExceeded
from src.models import CheckRequest, CheckResponse, DomainCheckResult, ErrorDetail, ErrorResponse, HealthResponse
from src.scraper import MultiRegistrarChecker

scraper = MultiRegistrarChecker()
logger = logging.getLogger("domain_checker.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await scraper.start()
    yield
    await scraper.stop()


app = FastAPI(
    title="Domain Checker API",
    version="0.1.0",
    lifespan=lifespan,
)


def build_error_response(
    code: str,
    message: str,
    details: list = None,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
) -> JSONResponse:
    body = {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }
    return JSONResponse(status_code=status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error.get("loc", []))
        details.append(ErrorDetail(field=field, message=error.get("msg", "")).model_dump())
    return build_error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=details,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@app.exception_handler(BrowserNotReadyError)
async def browser_not_ready_handler(request: Request, exc: BrowserNotReadyError) -> JSONResponse:
    return build_error_response(
        code="BROWSER_NOT_READY",
        message="Browser is not ready to process requests",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@app.exception_handler(NamecheapUnavailableError)
async def namecheap_unavailable_handler(request: Request, exc: NamecheapUnavailableError) -> JSONResponse:
    return build_error_response(
        code="NAMECHEAP_UNAVAILABLE",
        message="Namecheap is temporarily unavailable",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return build_error_response(
        code="RATE_LIMIT_EXCEEDED",
        message="Rate limit exceeded. Try again later.",
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    )


@app.exception_handler(DomainCheckError)
async def domain_check_error_handler(request: Request, exc: DomainCheckError) -> JSONResponse:
    return build_error_response(
        code="DOMAIN_CHECK_ERROR",
        message=str(exc),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return build_error_response(
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        browser_ready=scraper.is_ready(),
        timestamp=datetime.now(timezone.utc),
    )


@app.post("/check", response_model=CheckResponse)
async def check_domains(payload: CheckRequest) -> CheckResponse:
    if not scraper.is_ready():
        raise BrowserNotReadyError()

    domains = [d.strip().lower() for d in payload.domains]
    logger.info("domain_check_started total_domains=%d", len(domains))
    results = await scraper.check_domains(domains)
    logger.info("domain_check_completed total_domains=%d", len(results))

    return CheckResponse(
        results=results,
        checked_at=datetime.now(timezone.utc),
        total_checks=len(results),
    )
