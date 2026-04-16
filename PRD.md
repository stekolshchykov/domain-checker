# PRD: Nomen — AI Domain Naming Studio

## 1. Project Overview

**Nomen** is a multi-service AI-powered domain naming studio. It turns a short project description into a curated list of brandable domain names — complete with meaning, tone analysis, and tags — then checks real-time availability and pricing via Namecheap.

The system consists of three services:
- **`nextjs-app`** — Premium React frontend (public entrypoint)
- **`kimi-orchestrator`** — Express API that orchestrates Kimi Code AI and adapts the domain service
- **`domain-service`** — FastAPI + Playwright scraper for live Namecheap availability checks

---

## 2. Goals and Objectives

| # | Objective | Success Criteria |
|---|---|---|
| 1 | **Story-driven UX** | Users see exactly what they will get before they start (preview cards + global stepper) |
| 2 | **4-step flow** | Describe → Refine → Generate → Check |
| 3 | **AI naming** | Kimi Code API generates 15–20 brandable domains with meaning, tone, and tags |
| 4 | **Live availability** | Domain service scrapes Namecheap in real-time for status and pricing |
| 5 | **Secure architecture** | Only `nextjs-app:3000` is exposed publicly; backends are internal-only |
| 6 | **Resilient AI layer** | Retries, JSON fallback, Zod validation, deduplication |
| 7 | **Tested end-to-end** | Domain-service integration tests pass in Docker; orchestrator has unit tests |

---

## 3. Architecture

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
│  │   + Kimi API │              │  (Playwright)  │          │
│  └──────────────┘              └────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 3.1. Service Responsibilities

| Service | Tech | Responsibility | Public |
|---------|------|----------------|--------|
| `nextjs-app` | Next.js 16, React 19, Tailwind, Framer Motion | UI/UX, session state, BFF API calls | `3000` |
| `kimi-orchestrator` | Node.js 22, Express, TypeScript, Zod | Prompt building, Kimi Code API client, response parsing, domain-service adapter | internal |
| `domain-service` | Python 3.12, FastAPI, Playwright | Real-time Namecheap scraping for availability + pricing | internal |

---

## 4. UX Flow

### Step 1 — Describe (`/`)
- One-sentence project description
- Right-side preview shows "What you'll get": Smart names, Why it works, Live availability
- Sample result card (`novaforge.com`) demonstrates the final output format before the user commits

### Step 2 — Refine (`/brief`)
- 3 micro-steps inside the brief form:
  1. **Project & Audience** — description + target audience
  2. **Tone & Style** — tone chips + length preference
  3. **Keywords & TLDs** — include/exclude keywords + domain extensions
- Global 4-step stepper is always visible at the top

### Step 3 — Generate (`/generating` → `/ideas`)
- Animated progress screen explains the 30–90 second wait
- AI returns 15–20 domain ideas with:
  - `domainName` (full domain with TLD)
  - `meaning`
  - `whyItWorks`
  - `tone`
  - `tags`
- `/ideas` shows filterable cards; users toggle selections

### Step 4 — Check (`/results`)
- Selected domains are checked against Namecheap
- Results show:
  - Status: `available` | `taken` | `premium` | `unknown`
  - Price + currency (when available)
  - Meaning and tags merged from generation context
- Sort modes: Available first, Cheapest first, Best brand, Shortest first

---

## 5. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| **Frontend** | Next.js 16 + React 19 + TypeScript | App Router, static export, modern React features |
| **Styling** | Tailwind CSS + custom glassmorphism | Premium dark UI with aurora background |
| **Motion** | Framer Motion | Smooth page transitions, stepper animations, progress bars |
| **Orchestrator** | Express 4 + TypeScript | Lightweight, fast to iterate, perfect for BFF pattern |
| **AI Client** | Native `fetch` + Zod | No heavy SDKs; strict response validation |
| **Domain Scraper** | Python 3.12 + FastAPI + Playwright | Proven stack from original domain checker |
| **Containerization** | Docker + Docker Compose | One command to run all 3 services |

---

## 6. API Specification

### 6.1. Kimi Orchestrator

Base URL (internal): `http://kimi-orchestrator:4000`

#### `GET /api/health`

**Response 200 OK:**
```json
{
  "status": "ok",
  "domainService": "healthy",
  "timestamp": "2026-04-16T12:00:00Z"
}
```

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

**Response 200 OK:**
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
  "meta": { "generatedCount": 15, "deduplicated": true }
}
```

**Errors:**
- `422 VALIDATION_ERROR` — brief format invalid
- `500 INTERNAL_ERROR` — all Kimi API retries failed

#### `POST /api/check`

Checks availability for selected domains and merges generation context.

**Request:**
```json
{
  "domains": ["logonova.com", "brandforge.io"],
  "context": {
    "brief": { "projectDescription": "...", "tone": ["tech"], ... },
    "ideas": [ { "domainName": "logonova.com", "meaning": "..." } ]
  }
}
```

**Response 200 OK:**
```json
{
  "results": [
    {
      "domain": "logonova.com",
      "status": "available",
      "price": "$12.98",
      "currency": "USD",
      "meaning": "Fusion of logo and nova...",
      "whyItWorks": "Short, memorable...",
      "tone": "modern tech",
      "tags": ["tech", "brandable"]
    }
  ],
  "checkedAt": "2026-04-16T12:00:00Z",
  "totalChecks": 2
}
```

### 6.2. Domain Service (existing)

Base URL (internal): `http://domain-service:8000`

FastAPI auto-generates OpenAPI docs at `/docs` and `/openapi.json`.

#### `GET /health`

**Response 200 OK:**
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

**Response 200 OK:**
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

---

## 7. Kimi Code API Integration

The orchestrator calls **Kimi Code API** (not the standard Moonshot Open Platform).

| Setting | Value |
|---|---|
| Base URL | `https://api.kimi.com/coding/v1` |
| Model | `kimi-for-coding` |
| Auth | `Authorization: Bearer <KIMI_API_KEY>` |
| Required Header | `User-Agent: claude-code/1.0` |

> **Note:** Keys prefixed with `sk-kimi-` require the `.kimi.com` endpoint and the `claude-code/1.0` User-Agent. Using `api.moonshot.cn/v1` results in `401 Invalid Authentication`.

The prompt instructs the model to return **only valid JSON** matching the domain schema. The orchestrator:
1. Retries up to 3 times with exponential backoff
2. Requests `response_format: { type: "json_object" }`
3. Falls back to `reasoning_content` if `content` is empty
4. Validates with Zod and deduplicates by domain name

---

## 8. Docker Infrastructure

### 8.1. Services

```yaml
services:
  domain-service:
    build: ./domain-service
    expose: ["8000"]
    environment:
      - APP_ENV=production
      - PLAYWRIGHT_HEADLESS=true
      - RATE_LIMIT_SECONDS=1.0

  kimi-orchestrator:
    build: ./kimi-orchestrator
    expose: ["4000"]
    environment:
      - KIMI_API_KEY=${KIMI_API_KEY}
      - KIMI_API_BASE_URL=${KIMI_API_BASE_URL}
      - KIMI_MODEL=${KIMI_MODEL}
      - DOMAIN_SERVICE_URL=http://domain-service:8000

  nextjs-app:
    build: ./nextjs-app
    ports:
      - "3000:3000"
    environment:
      - KIMI_ORCHESTRATOR_URL=http://kimi-orchestrator:4000

  test:
    build: ./domain-service
    profiles: [test]
    command: ["pytest", "-v", "tests/"]
```

### 8.2. Commands

```bash
# Start the full stack
docker compose up --build -d

# Run domain-service integration tests
docker compose --profile test run --rm test

# Run orchestrator unit tests
cd kimi-orchestrator && npm test
```

---

## 9. Project Structure

```
domain-checker/
├── PRD.md                              # This document
├── README.md                           # Quick-start guide
├── docker-compose.yml                  # Multi-service orchestration
├── .env.example                        # Environment template
├── domain-service/                     # FastAPI + Playwright
│   ├── src/
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── kimi-orchestrator/                  # Express + Kimi API client
│   ├── src/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── prompts/
│   │   └── types/
│   ├── tests/
│   ├── Dockerfile
│   └── package.json
└── nextjs-app/                         # Next.js 16 frontend
    ├── app/
    │   ├── page.tsx                    # Landing / Describe
    │   ├── brief/page.tsx              # Refine stepper
    │   ├── generating/page.tsx         # AI progress
    │   ├── ideas/page.tsx              # Select names
    │   └── results/page.tsx            # Availability results
    ├── components/
    │   ├── Stepper.tsx                 # Global 4-step stepper
    │   ├── SessionProvider.tsx
    │   └── ui/
    ├── lib/
    │   ├── actions.ts
    │   └── types.ts
    ├── Dockerfile
    └── package.json
```

---

## 10. Environment Requirements

- Docker Engine 24.0+ and Docker Compose v2+
- Valid Kimi Code API key (`sk-kimi-...`)
- Port `3000` free on the host
- ~2 GB free disk space (Playwright image + Firefox)

---

## 11. Limitations and Risks

| Risk | Mitigation |
|------|------------|
| Namecheap DOM changes | Fallback to Aftermarket API + integration test monitoring |
| Kimi API latency (30–90s) | Progress UI with clear messaging; 180s timeout |
| Kimi Code API auth quirks | Documented endpoint + mandatory `User-Agent` header |
| Rate limiting on domain checks | 5-second delay enforced globally in scraper |
| Large batch checks | Semaphore-based parallel processing (up to 4 domains concurrently) |

---

## 12. Future Roadmap

- [ ] Saved shortlists / session history
- [ ] Export results (CSV, PDF)
- [ ] Compare TLD pricing side-by-side
- [ ] Regenerate from favorites
- [x] Logo / color palette generation expansion (implemented in results page)
- [ ] Redis caching for Namecheap results

---

*Document updated: 2026-04-16*
*Author: AI Agent (Kimi CLI)*
