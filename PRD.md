# PRD: Domain Checker API

## 1. Project Overview

**Domain Checker** is an HTTP API service deployed in a Docker container. It accepts one or more domain names and returns their availability status for registration, along with the price (if the domain is available) or occupancy information (if the domain is already registered).

Data is collected **in real time** from the open Namecheap registrar interface via browser automation (Playwright) and auxiliary internal Namecheap APIs.

---

## 2. Goals and Objectives

| # | Objective | Success Criteria |
|---|---|---|
| 1 | Accept requests with one or many domains | `POST /check` supports a `domains` array of any size (no limit) |
| 2 | Determine domain status | `available` / `taken` / `premium` / `unknown` |
| 3 | Extract registration price | Return `price` and `currency` for available/premium domains |
| 4 | Operate via a real background browser | Playwright headless Firefox inside Docker |
| 5 | Implement proper API behavior | HTTP codes, validation, structured errors |
| 6 | Deploy and test in Docker | `docker-compose up --build` + `docker-compose run --rm test` |
| 7 | Cover diverse scenarios with tests | 16 automated API tests for taken, available, premium domains, validation, rate-limit, and reuse page |

---

## 3. Namecheap Research

### 3.1. Results Page URL
```
https://www.namecheap.com/domains/registration/results/?domain=<DOMAIN>
```

Examples:
- `https://www.namecheap.com/domains/registration/results/?domain=KnowFlow.com`
- `https://www.namecheap.com/domains/registration/results/?domain=qwertyuiop12345abc.com`

### 3.2. Page Response Variants

The following patterns were identified by analyzing the DOM structure of the loaded page:

#### A. Taken Domain
- Text label present: `Taken` or `Registered in YYYY`
- Action button: `Make offer`
- Example domains: `knowflow.xyz`, `knowflow.io`, `knowflow.cloud`

#### B. Available Domain
- Registration price displayed (e.g. `€9.33/yr`, `€4.23/yr`)
- Action button: `Add to cart`
- Discount badge may be present: `42% OFF`, `New`
- Example domains: `qwertyuiop12345abc.com`, `qwertyuiop12345abc.org`

#### C. Premium Domain
- Label: `Premium`
- High price (e.g. `€8,842.53`)
- Button: `Add to cart`
- Example: `knowflow.com` (premium)

### 3.3. Internal Namecheap APIs

During page loading, Namecheap makes XHR requests. Some of them can be used as an additional data source:

**Aftermarket Status API:**
```
GET https://aftermarket.namecheapapi.com/domain/status?domain=<DOMAIN>
```

Responses:
- Available: `{"type":"ok","data":[{"domain":"qwertyuiop12345abc.com","status":"notfound"}]}`
- Taken/Aftermarket: `{"type":"ok","data":[{"domain":"knowflow.com","status":"active","price":10405,"retail":10456,"type":"buynow","username":"sedo"}]}`

> **Note:** this API only returns information for domains in the aftermarket list, or `notfound`. For full analysis (discounts, exact retail prices, premium status), parsing the main page via browser is required.

---

## 4. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| **Backend** | Python 3.12 + FastAPI | Simplicity, speed of development, built-in validation (Pydantic), async out of the box |
| **Browser Automation** | Playwright (async API) | Official support for headless Firefox, stable operation in Docker, convenient Python API |
| **Server** | Uvicorn | Standard ASGI server for FastAPI, works in Docker without issues |
| **Testing** | pytest + pytest-asyncio + HTTPX | HTTPX is the native async client for testing FastAPI, pytest-asyncio for Playwright fixtures |
| **Configuration** | Pydantic Settings + `.env` | Type-safe configuration, convenient in Docker via `environment:` |
| **Containerization** | Docker + Docker Compose | One `docker-compose.yml` to spin up the service and run tests |

### Why Python + FastAPI + Playwright in Docker is the optimal choice
- **Playwright** has official Docker images (`mcr.microsoft.com/playwright/python:v1.x.x-noble`) with pre-installed system dependencies and browsers.
- **Headless Firefox** is used in production — it more reliably passes Namecheap's Cloudflare protection compared to Chromium.
- **FastAPI** + **Uvicorn** are easy to package into a single container, start quickly, and consume minimal resources.
- No separate Selenium Grid or complex orchestration is required — everything runs in **one container**.
- For tests, `docker-compose run --rm test` is enough to run the browser inside the same image.

---

## 5. Architecture

### 5.1. Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                         │
│  ┌─────────────────┐      POST /check       ┌───────────┐  │
│  │   Client        │ ─────────────────────> │  FastAPI  │  │
│  │   (curl/tests)  │  { "domains": [...] }  │   App     │  │
│  └─────────────────┘                        └─────┬─────┘  │
│                                                   │         │
│                                                   ▼         │
│                                         ┌───────────────┐  │
│                                         │ RateLimited   │  │
│                                         │ Namecheap     │  │
│                                         │ Scraper       │  │
│                                         │ (Playwright)  │  │
│                                         └───────┬───────┘  │
│                                                 │          │
│                                                 ▼          │
│                                         ┌───────────────┐  │
│                                         │  Headless     │  │
│                                         │  Firefox      │  │
│                                         └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 5.2. Single Domain Check Algorithm

1. **Start the browser** (if not already running) — Playwright Firefox in headless mode.
2. **Open the page** `https://www.namecheap.com/domains/registration/results/?domain=<domain>`.
3. **Wait for results** to load (up to 15 seconds).
4. **Close the cookie dialog** if it appears.
5. **Parse the DOM:**
   - Find the heading with the exact domain name (e.g. `h2: "knowflow.com"`).
   - Determine the presence of labels: `Taken`, `Registered in`, `Premium`.
   - Determine the button type: `Make offer` (taken) or `Add to cart` (available/premium).
   - Extract the price from the `strong` element next to the domain.
6. **Fallback to Aftermarket API:** if the DOM does not contain a clear result (timeout, CAPTCHA, etc.), call `aftermarket.namecheapapi.com`.
7. **Form the result:**
   - `status`: `available` | `taken` | `premium` | `unknown`
   - `price`: price string or `null`
   - `currency`: extracted currency (`EUR`, `USD`) or `null`
   - `source`: `namecheap_page` | `aftermarket_api` | `unknown`

### 5.3. Multiple Domains and Rate Limiting

#### A. Page Reuse
- If **multiple domains** are passed in a single API request, they are checked **sequentially in the same browser tab**.
- After checking the first domain, the page is **not closed**. Instead, navigation (`page.goto()`) to the next domain's URL is performed.
- This reduces overhead from creating/closing contexts and lowers the digital fingerprint for Namecheap anti-fraud.

#### B. Strict Rate Limit — Minimum 5 Seconds Between Any Requests
- A **minimum 5-second** interval must be observed between **any two sequential domain checks** (within a single API request or across different requests).
- This is implemented via a global async lock + a last-request tracker (`last_request_at`).
- Before each `page.goto()`, the scraper calculates: `sleep = max(0, 5.0 - (now - last_request_at))` and performs `await asyncio.sleep(sleep)`.
- Thus, even if a client sends 100 domains in one `POST /check`, they will be processed in one tab with a ≥5 second pause between each.

#### C. Concurrency and Limits
- Parallel processing of different API requests is allowed, but each domain check still passes through the shared rate-limiter.
- The maximum number of simultaneous checks (semaphore) is limited to **1** to guarantee the 5-second interval between any pair of requests.
- **No limit** on the number of domains in a single request (`max_length` removed).
- **No HTTP connection timeout** — the server waits until all domains are checked, regardless of duration.

---

## 6. API Specification

### 6.1. Check Domains

**Endpoint:** `POST /check`

**Request Body:**
```json
{
  "domains": ["example.com", "brand-new-startup.io", "knowflow.com"]
}
```

> **Note:** there is no limit on the number of domains. The server does not drop the HTTP connection by timeout — the request runs until all domains are checked.

**Response 200 OK:**
```json
{
  "results": [
    {
      "domain": "example.com",
      "status": "taken",
      "price": null,
      "currency": null,
      "source": "namecheap_page"
    },
    {
      "domain": "brand-new-startup.io",
      "status": "available",
      "price": "€29.73/yr",
      "currency": "EUR",
      "source": "namecheap_page"
    },
    {
      "domain": "knowflow.com",
      "status": "premium",
      "price": "€8,842.53",
      "currency": "EUR",
      "source": "namecheap_page"
    }
  ],
  "checked_at": "2026-04-16T10:35:00Z",
  "total_checks": 3
}
```

**Status enum:**
- `available` — domain is free for registration, price is present.
- `taken` — domain is already registered.
- `premium` — domain is available but falls into the premium category with a higher price.
- `unknown` — could not determine status (error, CAPTCHA, timeout).

### 6.2. Health Check

**Endpoint:** `GET /health`

**Response 200 OK:**
```json
{
  "status": "ok",
  "browser_ready": true,
  "timestamp": "2026-04-16T10:35:00Z"
}
```

### 6.3. Internal Rate-Limiter Model

The `RateLimitedScraper` class in `scraper.py` has:
- `_last_request_at: float` — timestamp of the last HTTP request to Namecheap.
- `_lock: asyncio.Lock` — guarantees that only one domain is being checked at a time.

Pseudo-code of the `_throttle()` method:
```python
async def _throttle(self):
    elapsed = time.monotonic() - self._last_request_at
    delay = settings.rate_limit_seconds - elapsed
    if delay > 0:
        await asyncio.sleep(delay)
    self._last_request_at = time.monotonic()
```

The `check_domains(domains: list[str])` method:
1. Opens one `page` (if not already open).
2. For each domain, calls `_throttle()`.
3. Executes `await page.goto(url)`.
4. Parses the DOM.
5. After processing all domains, **does not close** `page` — leaves it open for the next API request (or closes it on application shutdown).

### 6.4. Response Codes and Error Handling

| HTTP Code | Scenario | Response Body |
|-----------|----------|---------------|
| `200 OK` | Successful domain check | `{ "results": [...], "checked_at": "...", "total_checks": N }` |
| `400 Bad Request` | Invalid JSON or missing required field | `{ "detail": "Invalid JSON body" }` or Pydantic validation error |
| `422 Unprocessable Entity` | Pydantic validation error (empty list, invalid domain format) | Standard Pydantic error response |
| `429 Too Many Requests` | Global API-level rate limiter (too many requests) | `{ "detail": "Rate limit exceeded. Try again later." }` |
| `500 Internal Server Error` | Unexpected scraper error, browser crash | `{ "detail": "Internal server error" }` |
| `503 Service Unavailable` | Browser not ready or cannot connect to Namecheap | `{ "detail": "Browser not ready" }` or `{ "detail": "Namecheap unavailable" }` |

#### Domain Format Validation
Before opening the browser, Pydantic validates each domain with a regular expression:
```
^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)+$
```

Rejected inputs: domains without a dot, with spaces, ending with a dot, with a hyphen at the label boundary, empty strings. On invalid format, `422` is returned with `error.code = VALIDATION_ERROR`.

#### Unified Error Model
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      { "field": "domains", "message": "List must contain at least 1 domain" }
    ]
  }
}
```

#### Custom FastAPI Exception Handlers
- `RequestValidationError` → 422 with unified error model
- `BrowserNotReadyError` (custom scraper exception) → 503 or 500
- `RateLimitExceeded` → 429
- `Exception` (catch-all) → 500 with minimal info (production-safe)

---

## 7. Docker Infrastructure

### 7.1. Dockerfile

The official Playwright image is used as the base to avoid manual installation of Firefox system dependencies.

```dockerfile
# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# App code
COPY src/ ./src/
COPY tests/ ./tests/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 7.2. Docker Compose

```yaml
version: "3.9"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - PLAYWRIGHT_HEADLESS=true
      - RATE_LIMIT_SECONDS=5.0
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  test:
    build: .
    environment:
      - APP_ENV=test
      - PLAYWRIGHT_HEADLESS=true
      - RATE_LIMIT_SECONDS=5.0
      - TEST_BASE_URL=http://api:8000
    command: ["pytest", "-v", "tests/"]
    depends_on:
      api:
        condition: service_healthy
    profiles:
      - test
```

### 7.3. Local Development and Testing Commands

```bash
# Spin up the service
docker-compose up --build api

# Run tests inside Docker (only supported method)
docker-compose --profile test run --rm test

# Stop everything
docker-compose down
```

### 7.4. Why Tests Must Run in Docker
- The official Playwright image contains all system libraries required for headless Firefox (libnss3, libatk, libcups, etc.).
- These dependencies are hard to maintain consistently across host OSes (macOS, various Linux distributions).
- Docker guarantees **reproducibility**: the same browser, same fonts, same environment.
- `docker-compose --profile test run --rm test` is the only supported way to run tests locally.

---

## 8. Implementation Phases

### Phase 1 — Environment Setup
- [x] Initialize Python project (`pyproject.toml`)
- [x] Install dependencies: `fastapi`, `uvicorn[standard]`, `playwright`, `pydantic-settings`, `httpx`, `pytest`, `pytest-asyncio`, `pytest-playwright`
- [x] Create `Dockerfile` based on `mcr.microsoft.com/playwright/python:v1.58.0-noble`
- [x] Create `docker-compose.yml` with `api` and `test` services
- [x] Verify container starts: `docker-compose up --build api`

### Phase 2 — Browser Scraping Module
- [x] Create `src/scraper.py` with `RateLimitedScraper` class
- [x] Implement `_throttle()` with 5-second delay and `asyncio.Lock`
- [x] Implement `check_domain(domain: str) -> DomainResult` with headless Firefox
- [x] Configure User-Agent and viewport to reduce blocking risk
- [x] Implement DOM parsing via Namecheap page selectors
- [x] Integrate fallback to Aftermarket API
- [x] Handle errors (timeout, unexpected page structure)

### Phase 3 — API Development
- [x] Create `src/main.py` with FastAPI application
- [x] Implement Pydantic models (`src/models.py`) for requests/responses/errors
- [x] Implement `POST /check` and `GET /health` endpoints
- [x] Implement custom exception handlers (422, 429, 500, 503)
- [x] Add regex domain-format validation with informative 422 responses
- [x] Global lifecycle management for the browser context (startup / shutdown)

### Phase 4 — Docker Integration and Local Testing
- [x] Configure `Dockerfile` to copy `src/` and `tests/`
- [x] Successfully start the service via `docker-compose up --build api`
- [x] Verify endpoints from host: `curl http://localhost:8000/health`

### Phase 5 — Testing (Docker Only)
- [x] Write API tests in `tests/test_api.py`
- [x] Tests cover:
  - Available domains
  - Taken domains
  - Premium domain
  - Validation error checks (empty list, invalid domain format)
  - **Rate-limiting:** elapsed time measurement between checks in one request (≥5 sec)
  - **Reuse page:** verify that no more than 1 page is created for multiple domains in a single request
- [x] Successful run: `docker run --rm domain-checker-api pytest -v tests/`

### Phase 6 — Documentation
- [x] `README.md` with installation and run instructions in English
- [x] `curl` request examples
- [x] Description of environment variables

---

## 9. Test Plan (16 Tests)

| # | Test | Expected Result | Domain Type / Scenario |
|---|------|-----------------|------------------------|
| 1 | `POST /check` → `["google.com"]` | `status: taken` | Taken |
| 2 | `POST /check` → `["facebook.com"]` | `status: taken` | Taken |
| 3 | `POST /check` → `["amazon.com"]` | `status: taken` | Taken |
| 4 | `POST /check` → `["knowflow.com"]` | `status: premium`, `price` present | Premium |
| 5 | `POST /check` → `["knowflow.xyz"]` | `status: taken` | Taken |
| 6 | `POST /check` → `["qwertyuiop12345abc.com"]` | `status: available`, `price` present | Available |
| 7 | `POST /check` → `["this-is-very-long-health-check-domain-name-test-1234567890.com"]` | `status: available`, `price` present | Available (long domain) |
| 8 | `POST /check` → `["google.com", "qwertyuiop12345abc.com"]` | Both results correct | Mixed |
| 9 | `POST /check` → `[]` | HTTP 422 Validation Error | Validation error |
| 10 | `GET /health` | `status: ok`, `browser_ready: true` | Health check |
| 11 | `POST /check` → 2 domains | Elapsed ≥5 sec (one 5-sec delay) | Rate limit |
| 12 | `POST /check` → 1 domain, then `POST /check` → 2 domains | Delay between requests ≥5 sec, no more than 1 page created | Rate limit + reuse page |
| 13 | `POST /check` → `["not_a_domain"]` | HTTP 422 Validation Error | Invalid format (no dot) |
| 14 | `POST /check` → `["domain with spaces"]` | HTTP 422 Validation Error | Invalid format (spaces) |
| 15 | `POST /check` → `["test."]` | HTTP 422 Validation Error | Invalid format (trailing dot) |
| 16 | `POST /check` → `["-example.com"]` | HTTP 422 Validation Error | Invalid format (leading hyphen) |

> **Important:** during test execution, Playwright must launch the browser in headless mode **inside the Docker container**.

---

## 10. Project Structure

```
domain-checker/
├── PRD.md                      # This document
├── README.md                   # Run instructions in English
├── Dockerfile                  # Image based on Playwright Python
├── docker-compose.yml          # api + test services
├── pyproject.toml              # Python dependencies
├── .env.example                # Example environment variables
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app + exception handlers
│   ├── config.py               # Pydantic Settings
│   ├── scraper.py              # Playwright Namecheap scraper
│   ├── models.py               # Pydantic API models
│   └── exceptions.py           # Custom exceptions
└── tests/
    ├── __init__.py
    ├── conftest.py             # pytest fixtures (event_loop, http_client)
    └── test_api.py             # API tests (run inside Docker)
```

---

## 11. Environment Requirements

- Docker Engine 24.0+ and Docker Compose v2+
- ~2 GB free disk space (Playwright image + Firefox)
- Internet access to load Namecheap pages
- Port `8000` free on the host (or configurable via `.env`)

---

## 12. Limitations and Risks

| Risk | Mitigation |
|------|------------|
| Namecheap may change the page DOM | CI test monitoring + fallback to Aftermarket API |
| Rate limiting / CAPTCHA | 1 page + 5-second delay between any requests, headless mode with real User-Agent |
| Slow page loading | 10–15 second timeout, graceful degradation to `unknown` |
| Dependency on external site | Error logging, retry mechanism |
| Playwright in Docker requires a lot of space | Use the official slim image, periodically clean unused layers |

---

## 13. Future Roadmap

- [ ] Bulk checking support via Namecheap Beast Mode internal API
- [ ] Redis caching (1-hour TTL)
- [ ] Webhook notifications on domain status change
- [ ] Support for other registrars (GoDaddy, Porkbun)
- [ ] Scaling via a pool of browser contexts (while keeping rate limits)

---

*Document created: 2026-04-16*
*Author: AI Agent (Kimi CLI)*
