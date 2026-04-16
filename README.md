# Domain Checker API

HTTP API service for checking domain availability via Namecheap. Runs inside a Docker container with headless Firefox (Playwright).

## Stack

- **Python 3.12 + FastAPI**
- **Playwright (headless Firefox)**
- **Docker + Docker Compose**
- **pytest** for testing

## Quick Start

```bash
docker-compose up --build api
```

The API will be available at `http://localhost:8000`.

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## API Endpoints

### `POST /check`

Accepts an array of domains and returns their availability status. There is **no limit** on the number of domains — the request runs to completion.

**Request:**
```json
{
  "domains": ["google.com", "knowflow.com"]
}
```

**Response 200 OK:**
```json
{
  "results": [
    {
      "domain": "google.com",
      "status": "taken",
      "price": null,
      "currency": null,
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
  "checked_at": "2026-04-16T11:31:30Z",
  "total_checks": 2
}
```

#### Possible Domain Statuses

| Status | Description | Example Price |
|--------|-------------|---------------|
| `available` | Domain is free for registration | `€9.33/yr` |
| `taken` | Domain is already registered | `null` |
| `premium` | Domain is available but premium | `€8,842.53` |
| `unknown` | Could not determine status | `null` |

#### Response Examples for Different Scenarios

**Available domain:**
```json
{
  "domain": "qwertyuiop12345abc.com",
  "status": "available",
  "price": "€9.33/yr",
  "currency": "EUR",
  "source": "namecheap_page"
}
```

**Taken domain:**
```json
{
  "domain": "google.com",
  "status": "taken",
  "price": null,
  "currency": null,
  "source": "namecheap_page"
}
```

**Non-existent TLD (valid format):**
```json
{
  "domain": "nonexistent-tld-12345.zzz",
  "status": "available",
  "price": null,
  "currency": null,
  "source": "aftermarket_api"
}
```

### `GET /health`

Health check with browser readiness verification.

**Response 200 OK:**
```json
{
  "status": "ok",
  "browser_ready": true,
  "timestamp": "2026-04-16T11:30:17Z"
}
```

## HTTP Response Codes

| Code | Scenario |
|------|----------|
| `200 OK` | Successful domain check or health check |
| `400 Bad Request` | Invalid JSON or missing required field |
| `422 Unprocessable Entity` | Validation error: empty list, invalid domain format |
| `429 Too Many Requests` | Rate limit exceeded (rare due to internal throttling) |
| `500 Internal Server Error` | Unexpected error |
| `503 Service Unavailable` | Browser is not ready |

## Domain Validation

The API validates the format of each domain **before** opening the browser. The following are rejected with `422`:

- `not_a_domain` — no dot
- `domain with spaces` — contains spaces
- `test.` — ends with a dot
- `-example.com` — starts with a hyphen
- `example-.com` — hyphen before the dot
- `[]` / `null` — empty list or non-string

If the format is valid but the TLD does not exist, the API returns `available` based on the Namecheap Aftermarket API.

## How It Works

- **Rate limiting:** a strict **5-second** pause between any two domain checks. For example, 10 domains will take at least **45 seconds**.
- **Page reuse:** multiple domains in a single request are checked sequentially in **one Firefox tab** without recreation.
- **Fallback:** if the Namecheap page is unavailable or lacks data, the Aftermarket API is used.
- **No connection timeout:** the server does not drop the HTTP connection regardless of how long the check takes.

## Testing (Docker only)

```bash
docker-compose --profile test run --rm test
```

Currently there are **16 tests**, including:
- taken, available, and premium domains
- validation of empty and invalid domains
- rate-limiting verification (≥5 seconds between domains)
- page reuse verification

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PLAYWRIGHT_HEADLESS` | Run browser in headless mode | `true` |
| `RATE_LIMIT_SECONDS` | Minimum interval between checks | `5.0` |
| `PAGE_TIMEOUT_MS` | Page load timeout for a single domain | `15000` |
| `LONG_HEALTH_CHECK_DOMAIN` | Long domain used for tests | `this-is-very-long-health-check-domain-name-test-1234567890.com` |
