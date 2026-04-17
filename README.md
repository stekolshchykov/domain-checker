# Nomen — AI Domain Naming Studio

A production-minded, multi-service stack that turns domain name search into a premium AI-assisted experience.

> **Goal:** Help founders, product teams, and creators discover brandable domain names with meaning — then check availability and pricing in real time.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Public Internet                         │
│                          │                                  │
│                          ▼                                  │
│              ┌──────────────────────┐                       │
│              │   nextjs-app (3000)  │  ← Only public port   │
│              │   Next.js 16 + TS    │                       │
│              └──────────┬───────────┘                       │
│                         │ internal network                   │
│         ┌───────────────┴───────────────┐                   │
│         ▼                               ▼                   │
│  ┌──────────────┐              ┌────────────────┐          │
│  │kimi-orchestra│              │ domain-service │          │
│  │  tor (4000)  │              │    (8000)      │          │
│  │ Node/Express │─────────────▶│  FastAPI/py    │          │
│  │   + Kimi API │              │  (untouched)   │          │
│  └──────────────┘              └────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### Services

| Service | Tech | Responsibility | Public Port |
|---------|------|----------------|-------------|
| `nextjs-app` | Next.js 16, Tailwind, Framer Motion | Premium UI, UX flow, BFF API layer | `3000` |
| `kimi-orchestrator` | Node.js 22, Express, TypeScript, Zod | Prompt engineering, Kimi API client, response parsing, domain-service adapter | internal only |
| `domain-service` | Python 3.12, FastAPI, Playwright | Domain availability & pricing scraping (parallelized, multi-registrar) | internal only |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Kimi API key (`KIMI_API_KEY`)

### 1. Clone & configure

```bash
cp .env.example .env
# Edit .env and add your KIMI_API_KEY
```

### 2. Run the full stack

```bash
docker compose up --build -d
```

### 3. Open the app

Visit [http://localhost:3000](http://localhost:3000)

### 4. Run tests

```bash
# Orchestrator unit + integration tests
cd kimi-orchestrator && npm test

# Domain-service integration tests
docker compose --profile test run --rm test
```

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `KIMI_API_KEY` | Yes | Your Kimi API key |
| `KIMI_API_BASE_URL` | No | Default: `https://api.kimi.com/coding/v1` |
| `KIMI_MODEL` | No | Default: `kimi-for-coding` |
| `KIMI_ORCHESTRATOR_URL` | No | Internal URL for Next.js → orchestrator |
| `DOMAIN_SERVICE_URL` | No | Internal URL for orchestrator → domain-service |

---

## UX Flow

1. **Hero** — Enter your project idea in one sentence.
2. **Brief Stepper** — Answer 3 quick questions (audience, tone, keywords, TLDs).
3. **Generating** — AI crafts 15–20 brandable domain names with meanings.
4. **Ideas** — Review cards, read the "why it works", toggle selections, apply filters.
5. **Results** — See availability, pricing, and "Top Pick" recommendations.

---

## API Documentation

### Kimi Orchestrator

Base URL (internal): `http://kimi-orchestrator:4000`

#### `GET /api/health`
Returns orchestrator + downstream domain-service health.

#### `POST /api/generate`
Generates domain ideas from a brief.

**Request:**
```json
{
  "projectDescription": "AI logo generator for startups",
  "audience": "founders and designers",
  "tone": ["tech", "modern"],
  "lengthPreference": "short",
  "keywords": ["logo", "brand"],
  "exclusions": ["pix"],
  "tlds": [".com", ".io"]
}
```

**Response:**
```json
{
  "domains": [
    {
      "domainName": "logonova.com",
      "meaning": "Fusion of logo and nova — a new star for your brand",
      "whyItWorks": "Short, memorable, suggests creation and freshness",
      "tone": "modern tech",
      "tags": ["tech", "brandable", "short"]
    }
  ],
  "meta": { "generatedCount": 42, "deduplicated": true }
}
```

#### `POST /api/check`
Checks availability for selected domains and merges generation context.

**Request:**
```json
{
  "domains": ["logonova.com", "brandforge.io"],
  "context": { "brief": { ... }, "ideas": [ ... ] }
}
```

**Response:**
```json
{
  "results": [
    {
      "domain": "logonova.com",
      "status": "available",
      "price": "$12.98",
      "meaning": "...",
      "tags": ["tech"]
    }
  ],
  "checkedAt": "2026-04-16T12:00:00Z",
  "totalChecks": 2
}
```

### Domain Service (existing)

Base URL (internal): `http://domain-service:8000`

#### `GET /health`
```json
{
  "status": "ok",
  "browser_ready": true,
  "timestamp": "2026-04-16T12:00:00Z"
}
```

#### `POST /check`
**Request:**
```json
{ "domains": ["example.com"] }
```

**Response:**
```json
{
  "results": [
    {
      "domain": "example.com",
      "status": "available",
      "price": "$12.98",
      "currency": "USD",
      "source": "namecheap_page"
    }
  ],
  "checked_at": "2026-04-16T12:00:00Z",
  "total_checks": 1
}
```

**Statuses:** `available` | `taken` | `premium` | `unknown`

**Errors (unified envelope):**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [...]
  }
}
```

---

## Project Structure

```
domain-checker/
├── domain-service/          # Existing FastAPI + Playwright service
│   ├── src/
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── kimi-orchestrator/       # New Node.js orchestrator
│   ├── src/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── prompts/
│   │   └── types/
│   ├── tests/
│   ├── Dockerfile
│   └── package.json
├── nextjs-app/              # New Next.js 16 frontend
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── public/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Design Philosophy

- **Modular domain intelligence** — registrar adapters share one runner, one parser model, one normalized result schema.
- **Security first** — only the Next.js frontend is exposed publicly.
- **Premium UX** — dark aurora theme, glass cards, motion design, zero clutter.
- **Resilient AI layer** — retries, JSON extraction fallback, strict Zod validation, deduplication.
- **Tested** — unit tests for parsing/prompts, integration tests for API contracts, e2e smoke scenarios.

---

## Known Limitations & Next Steps

- **Rate limiting:** Checks now use global + per-registrar limits, retry/backoff, circuit-breaker, and cache; some providers still throttle or block automated traffic.
- **Operational-only runs:** If providers return mixed non-decisive states (`blocked`/`parsing_failed`/`temporarily_unavailable`) without dominant consensus, aggregate status is intentionally `unknown` to avoid false availability claims.
- **Parser conservatism:** marker matching now uses token boundaries and domain-aware JSON guards to reduce false positives from noisy layouts.
- **Adaptive weighting:** aggregator applies per-provider reliability EMA to reduce impact from chronically noisy/blocked registrars during consensus.
- **Kimi latency:** Generation can take 10–30 seconds. The UI shows animated progress states.
- **Recent additions:**
  - Global footer with GitHub link
  - Brand identity assets (color palette + 5 SVG logos) generated by AI and shown on results
  - Domain pipeline upgraded to 50+ registrar adapters with normalized statuses (`available`, `unavailable`, `premium`, `discounted`, `transfer_only`, `blocked`, etc.)
  - Full hydration guards eliminating SSR redirect flashes
  - Faster bulk checks with controlled parallelism and graceful partial results
- **Future ideas:**
  - Saved shortlists / session history
  - Export results (CSV, PDF)
  - Compare TLD pricing side-by-side
  - Regenerate from favorites
  - Logo / slogan generation expansion

---

## License

MIT (or as specified by the project owner)
