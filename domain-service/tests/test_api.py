from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.main import scraper
from src.models import DomainCheckResult, FinalStatus


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["browser_ready"] is True
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_check_returns_normalized_fields(client, monkeypatch):
    now = datetime.now(timezone.utc)
    mock_result = DomainCheckResult(
        domain="example.com",
        status="available",
        final_status=FinalStatus.STANDARD_PRICE,
        registrar="aggregated",
        price="$12.99",
        registration_price="$12.99",
        renewal_price="$15.99",
        currency="USD",
        premium=False,
        promo=True,
        source="aggregated",
        source_url="https://example.test/search?domain=example.com",
        checked_at=now,
        detail="namecheap: available signal",
        confidence=0.77,
        prices=[],
        provider_results=[],
    )
    monkeypatch.setattr(scraper, "check_domains", AsyncMock(return_value=[mock_result]))

    response = await client.post("/check", json={"domains": ["example.com"]})
    assert response.status_code == 200
    body = response.json()

    assert body["total_checks"] == 1
    result = body["results"][0]
    assert result["domain"] == "example.com"
    assert result["status"] == "available"
    assert result["final_status"] == "standard_price"
    assert result["registration_price"] == "$12.99"
    assert result["renewal_price"] == "$15.99"
    assert result["promo"] is True
    assert result["confidence"] == 0.77


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_domain",
    ["not a domain", "", "invalid", "-foo.com", "foo-.com", "foo"],
)
async def test_check_invalid_domain_returns_422(client, bad_domain):
    response = await client.post("/check", json={"domains": [bad_domain]})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_check_requires_domain_list(client):
    response = await client.post("/check", json={"domains": []})
    assert response.status_code == 422
