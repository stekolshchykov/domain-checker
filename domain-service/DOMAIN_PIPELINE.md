# Domain Search / Availability / Pricing Pipeline

## Overview
The domain-checking subsystem was refactored into shared infrastructure + registrar adapters:

- `src/request_runner.py`: shared HTTP runtime with:
  - global concurrency limit,
  - per-registrar concurrency limit,
  - per-registrar min-interval rate control,
  - retries with exponential backoff + jitter,
  - rate-limit-aware retries (`429` + `Retry-After` support),
  - request timeout control,
  - in-memory TTL cache,
  - circuit breaker for repeated failures.
- `src/availability_parser.py`: shared parser/normalizer for registrar HTML/JSON hints.
- `src/adapters/base.py`: adapter contract + normalized result builder.
- `src/adapters/generic.py`: generic registrar adapter from config specs.
- `src/adapters/{namecheap,godaddy,cloudflare,letshost}.py`: provider-specific logic where needed.
- `src/adapters/__init__.py`: registrar catalog + adapter factory.
- `src/scraper.py`: parallel orchestration and result aggregation.

Runtime tuning env vars:

- `PROVIDER_RELIABILITY_ALPHA` (default `0.15`)
- `PROVIDER_RELIABILITY_FLOOR` (default `0.2`)

## Normalized Status Model
Detailed status (`final_status`):

- `available`
- `unavailable`
- `premium`
- `discounted`
- `standard_price`
- `transfer_only`
- `unsupported_tld`
- `blocked`
- `rate_limited`
- `temporarily_unavailable`
- `parsing_failed`
- `unknown`

Backward-compatible top-level `status` is still returned as one of:

- `available`
- `taken`
- `premium`
- `unknown`

Plus structured metadata:

- `registrar`
- `source_url`
- `checked_at`
- `registration_price`
- `renewal_price`
- `currency`
- `premium`
- `promo`
- `confidence`
- `detail`
- `prices[]`
- `provider_results[]`

## Registered Providers
Specialized adapters:

- `namecheap`
- `godaddy`
- `cloudflare`
- `letshost`

Generic configured adapters:

- `domaincom`, `namedotcom`, `googledomains`, `bluehost`, `hostgator`, `dreamhost`, `ionos`, `gandi`, `namesilo`, `porkbun`, `dynadot`, `hover`, `networksolutions`, `registercom`, `enom`, `ovhcloud`, `interserver`, `bigrock`, `hostinger`, `resellerclub`, `alibabacloud`, `reg123`, `eurodns`, `instra`, `namebright`, `sav`, `domainmonster`, `domainpeople`, `internetbs`, `epik`, `rebel`, `iwantmyname`, `onlydomains`, `thexyz`, `dotster`, `joker`, `strato`, `lcn`, `uk2`, `mydomain`, `namesco`, `tsohost`, `onamae`, `moniker`, `pananames`, `rrpproxy`, `names007`

## How To Add a Registrar
1. Add a `RegistrarSpec` in `src/adapters/__init__.py` with URL template + optional parser rules.
2. If the registrar has stable public JSON/API endpoints, add a dedicated adapter under `src/adapters/`.
3. Set safe runtime config (`max_concurrency`, `min_interval_seconds`, `retries`, `timeout_seconds`).
4. Add parser fixture(s) under `tests/fixtures/registrars` and unit tests.
5. Run test suite via Docker test profile.

## Diagnostics
Each provider result includes debug metadata (`ProviderDebugInfo`):

- request start/end timestamps
- duration
- request/source URL
- HTTP status
- attempts
- cache hit
- fallback used
- parser error note
- blocked/rate-limited flags
- current provider reliability score (EMA)

## Accuracy Guards
- Parser requires domain-specific evidence for decisive statuses.
- Domain matching is tolerant to split-markup formatting (for example, `example . com`).
- Keyword markers use token-boundary matching to avoid substring collisions (for example, `available` inside `unavailable`).
- If searched domain marker is missing and no clear JSON availability signal exists, parser returns `parsing_failed` with low confidence instead of guessing from generic page noise.
- JSON availability hints are ignored when no domain context is present in response HTML.
- Aggregator can downgrade weak decisive outcomes when operational failure states dominate.
- If only operational states are present and no single operational state dominates, aggregated status is normalized to `unknown` with note `operational signals mixed`.
- Aggregator applies provider reliability weighting (in-memory EMA) so consistently noisy providers contribute less to decisive consensus.
