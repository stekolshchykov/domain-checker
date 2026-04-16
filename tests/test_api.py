import time

import pytest

from src.main import scraper


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["browser_ready"] is True
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_check_single_taken_google_com(client):
    response = await client.post("/check", json={"domains": ["google.com"]})
    assert response.status_code == 200
    data = response.json()
    assert data["total_checks"] == 1
    result = data["results"][0]
    assert result["domain"] == "google.com"
    assert result["status"] == "taken"


@pytest.mark.asyncio
async def test_check_single_available_long_domain(client):
    # Very long domain that is expected to be available
    domain = "this-is-very-long-health-check-domain-name-test-1234567890.com"
    response = await client.post("/check", json={"domains": [domain]})
    assert response.status_code == 200
    data = response.json()
    result = data["results"][0]
    assert result["domain"] == domain
    assert result["status"] == "available"
    assert result["price"] is not None


@pytest.mark.asyncio
async def test_check_single_premium_knowflow_com(client):
    response = await client.post("/check", json={"domains": ["knowflow.com"]})
    assert response.status_code == 200
    data = response.json()
    result = data["results"][0]
    assert result["domain"] == "knowflow.com"
    assert result["status"] == "premium"
    assert result["price"] is not None


@pytest.mark.asyncio
async def test_check_single_taken_knowflow_xyz(client):
    response = await client.post("/check", json={"domains": ["knowflow.xyz"]})
    assert response.status_code == 200
    data = response.json()
    result = data["results"][0]
    assert result["domain"] == "knowflow.xyz"
    assert result["status"] == "taken"


@pytest.mark.asyncio
async def test_check_single_available_random_com(client):
    domain = "qwertyuiop12345abc.com"
    response = await client.post("/check", json={"domains": [domain]})
    assert response.status_code == 200
    data = response.json()
    result = data["results"][0]
    assert result["domain"] == domain
    assert result["status"] == "available"
    assert result["price"] is not None


@pytest.mark.asyncio
async def test_check_multiple_domains_returns_correct_results(client):
    domains = ["google.com", "qwertyuiop12345abc.com"]
    response = await client.post("/check", json={"domains": domains})
    assert response.status_code == 200
    data = response.json()
    assert data["total_checks"] == 2
    statuses = {r["domain"]: r["status"] for r in data["results"]}
    assert statuses["google.com"] == "taken"
    assert statuses["qwertyuiop12345abc.com"] == "available"


@pytest.mark.asyncio
async def test_check_empty_domains_returns_422(client):
    response = await client.post("/check", json={"domains": []})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any("domains" in str(d.get("field", "")) for d in data["error"]["details"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_domain",
    [
        "not_a_domain",
        "domain with spaces",
        "test.",
        "-example.com",
        "example-.com",
        "",
    ],
)
async def test_check_invalid_domain_format_returns_422(client, bad_domain):
    response = await client.post("/check", json={"domains": [bad_domain]})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_check_rate_limit_between_domains(client):
    domains = [
        "qwertyuiop12345abc.com",
        "this-is-very-long-health-check-domain-name-test-1234567890.com",
    ]
    start = time.monotonic()
    response = await client.post("/check", json={"domains": domains})
    elapsed = time.monotonic() - start
    assert response.status_code == 200
    # With 2 domains there should be at least one 5-second delay between them
    assert elapsed >= 5.0, f"Expected >= 5.0s delay, got {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_check_page_reuse(client):
    # First request creates the page
    response = await client.post("/check", json={"domains": ["google.com"]})
    assert response.status_code == 200

    page_before = scraper._page
    assert page_before is not None

    # Second request with multiple domains should reuse the same page
    domains = ["google.com", "qwertyuiop12345abc.com"]
    response = await client.post("/check", json={"domains": domains})
    assert response.status_code == 200

    page_after = scraper._page
    assert page_after is not None
    assert page_before == page_after, "Page should be reused across domains in a single request"
