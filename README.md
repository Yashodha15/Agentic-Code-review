# Agentic Code Review

Agentic Code Review is a GitHub-connected, repository-aware, hierarchical multi-agent review platform. It authenticates pull-request webhooks, creates a deterministic review plan from the changed files and detected technologies, delegates focused investigations to specialist agents and subagents, validates every proposed finding against the real diff, publishes policy-eligible inline comments, and exposes the complete execution graph in real time.

The central design principle is simple: **models perform analysis; deterministic application code controls trust, orchestration, budgets, verification, persistence, and publication.** The result is an AI review workflow that is observable, bounded, reproducible in tests, and safe to use as part of a merge policy.

## Contents

- [Objective](#objective)
- [Capabilities](#capabilities)
- [Architecture](#architecture)
- [Review lifecycle](#review-lifecycle)
- [Agent system](#agent-system)
- [Planning and technology detection](#planning-and-technology-detection)
- [Verification and GitHub publication](#verification-and-github-publication)
- [Policy and limits](#policy-and-limits)
- [State and failure semantics](#state-and-failure-semantics)
- [Backend](#backend)
- [Angular application](#angular-application)
- [Operations console](#operations-console)
- [API](#api)
- [Persistence](#persistence)
- [GitHub App setup](#github-app-setup)
- [Security model](#security-model)
- [Configuration](#configuration)
- [Local development](#local-development)
- [Containers and production deployment](#containers-and-production-deployment)
- [Testing](#testing)
- [Repository map](#repository-map)
- [Troubleshooting](#troubleshooting)
- [Current constraints and extension points](#current-constraints-and-extension-points)

## Objective

The project provides an automated first-pass pull-request reviewer that combines the breadth of parallel AI analysis with the predictability required by production engineering systems.

For every supported pull-request event, the platform aims to:

1. Prove that the request came from GitHub.
2. persist the delivery exactly once, even when GitHub retries it;
3. retrieve the pull-request diff and a controlled set of manifests;
4. detect affected languages and frameworks;
5. choose required specialist teams using deterministic rules;
6. run focused subagents concurrently and consolidate their evidence through leads;
7. join all specialist branches before verification;
8. reject findings that do not point to a real changed line;
9. deduplicate results and enforce repository policy;
10. publish an auditable GitHub review and check run; and
11. stream all lifecycle, agent, subagent, finding, and failure state to the UI.

The platform complements human review. It does not claim that a model can certify correctness. Instead, it creates a transparent and bounded review pass whose incomplete execution is never silently represented as a clean result.

## Capabilities

### GitHub ingestion

- GitHub App webhook integration.
- SHA-256 HMAC validation of `X-Hub-Signature-256` using constant-time comparison.
- A 2 MiB webhook-body limit.
- Strict Pydantic validation of the required payload subset.
- Idempotency through the unique `X-GitHub-Delivery` value.
- Support for `opened`, `reopened`, `synchronize`, and `ready_for_review` pull-request actions.
- Safe acknowledgement of unsupported events/actions without creating review work.

### Agent orchestration

- Signal-based detection for Python, JavaScript, TypeScript, React, Angular, FastAPI, and Django.
- Deterministic risk and specialist planning before any model call.
- Five stable specialist leads: correctness, security, frontend, architecture, and testing.
- Focused named subagents beneath selected leads.
- Parallel LangGraph specialist branches and a true fan-in barrier.
- Concurrent subagent calls within each specialist branch.
- Lead consolidation of subagent evidence.
- Partial-failure preservation when one agent or subagent fails.

### Verification and enforcement

- Dependency-free GitHub unified-diff parsing.
- Validation of destination paths and new-side added/modified lines.
- Rejection of absolute paths and directory traversal.
- Stable fingerprints and confidence-based deduplication.
- Minimum-severity and maximum-comment filters.
- Specialist, subagent, depth, runtime, and estimated-cost ceilings.
- Optional merge blocking on critical findings.
- Fail-closed behavior for incomplete selected analysis.

### Product and operations

- Angular 22 product UI with reusable cards, pills, rows, agent cards, dialogs, empty states, and notifications.
- Workspace metrics, recent reviews, and nested live execution timeline.
- Full review archive and detailed visual execution graph.
- Switchable findings/event-timeline side panel with independent scrolling.
- Live Server-Sent Events (SSE) updates.
- Snackbar notifications for initiated, blocked, and completed reviews.
- Separate Streamlit engineering console.
- Durable SQLite storage and queue.
- Docker Compose and Caddy-based HTTPS deployment.
- Automated GitHub Actions test, build, audit, and deployment workflow.
- Fake model and GitHub providers for offline tests.

## Architecture

```text
┌────────────────────────────── GitHub ──────────────────────────────┐
│ pull_request webhook ─────────────────────────────────────────┐     │
│ PR diff + manifests ◄── installation-scoped API token ────┐  │     │
│ review comments + "Code Review" check ◄───────────────────┤  │     │
└────────────────────────────────────────────────────────────┼──┼─────┘
                                                             │  │
                         ┌───────────────────────────────────┘  ▼
                         │                           FastAPI webhook/API
                         │                                   │
                         │                           persist + enqueue
                         │                                   ▼
                         │                    SQLite/WAL shared state
                         │                     reviews · jobs · traces
                         │                     findings · active policy
                         │                                   │ claim
                         ▼                                   ▼
                GitHub REST client                     review worker
                         ▲                                   │
                         │                  adapters → planner → policy
                         │                                   │
                         │                             LangGraph fan-out
                         │                      specialist leads + subagents
                         │                                   │
                         └──────────── publish ◄── verify + fan-in

 Angular product UI ◄──────────── HTTP + SSE ───────────► FastAPI
 Streamlit operations console ◄────── HTTP ─────────────► FastAPI
```

Production runs four services:

| Service | Responsibility | Port |
| --- | --- | ---: |
| `api` | Webhook ingestion, read API, SSE, policy API | `8000` internal |
| `worker` | Queue polling, GitHub/model calls, orchestration, publication | none |
| `console` | Streamlit engineering console | `8501` internal |
| `gateway` | Caddy TLS, authentication, routing, Angular static hosting | `80`, `443` |

The API and worker use the same SQLite file in the `aegis-data` named volume. Caddy serves the Angular browser bundle directly.

## Review lifecycle

### 1. Authenticate the webhook

GitHub sends `POST /api/v1/github/webhooks`. The API reads the exact bytes, rejects payloads over 2 MiB, and verifies the `sha256=` HMAC before JSON parsing. It also requires a non-empty delivery ID no longer than 255 characters.

### 2. Validate and ingest the event

The validated payload contains the repository name, installation ID, pull-request number, head/base SHAs, and action. A new delivery creates a UUID review in `queued` state. The unique delivery ID makes retries idempotent: repeated deliveries return the original review and are not enqueued twice.

The API appends `webhook` and `queue` trace events and creates a durable job. If queue insertion fails, the review is marked failed and the endpoint returns HTTP 503.

### 3. Claim the durable job

The worker polls every two seconds by default. Claiming changes the queue record from `queued` to `running`, increments its attempt count, changes the review to `running`, and appends a `worker` trace.

### 4. Fetch controlled GitHub context

The worker exchanges a GitHub App JWT for a short-lived installation token, or uses `GITHUB_TOKEN` in local development. It fetches the PR as a unified diff and checks only this manifest allowlist at the exact head SHA:

```text
package.json        angular.json       tsconfig.json
pyproject.toml      requirements.txt   Pipfile
manage.py
```

It does not crawl the repository or execute pull-request code.

### 5. Filter and plan

Complete diff sections matching `ignored_paths` are removed. Adapters inspect changed paths and the allowed manifests. The deterministic planner selects specialists and assigns a risk level. Policy then truncates specialist/subagent counts and delegation depth before any model work.

### 6. Execute the hierarchy

Every specialist exists as a LangGraph branch. Unselected specialists record `skipped` without calling a model. A selected branch runs up to four subagents concurrently, captures their results/errors, then sends successful subagent evidence to its lead for consolidation.

All specialist branches join at one barrier. Verification does not start until every branch has completed, skipped, or returned a captured failure.

### 7. Verify findings

The verifier parses the diff and requires every candidate to name a repository-relative destination path and an added/modified line on the new side of a hunk. Invalid candidates are rejected. Equivalent candidates are deduplicated, retaining the highest-confidence result.

### 8. Enforce policy and persist

The worker keeps verified findings at or above `minimum_severity`, caps them at `maximum_comments`, persists them with completed agents and errors, and calculates merge-blocking reasons.

### 9. Publish to GitHub

The worker creates a PR review with inline comments and a check run named `Code Review`. It uses `REQUEST_CHANGES` and a failing check when execution errors or blocking policy reasons exist; otherwise it uses a non-blocking `COMMENT` review and successful check.

Configure branch protection to require `Code Review` if this result must gate merging.

## Agent system

| Lead | Responsibility | Default subagents |
| --- | --- | --- |
| `correctness` | Control flow, state, boundaries, concurrency, async behavior, errors, serialization, resources | `control-flow`, `boundary-cases`, `error-handling` |
| `security` | Authentication, authorization, input handling, data protection, secrets, infrastructure, dependencies | `authentication`, `authorization`, `input-validation` |
| `frontend` (Angular) | Lifecycle, rendering, browser security, accessibility, client/server boundaries | `rxjs-lifecycle`, `template-safety`, `change-detection`, `accessibility` |
| `frontend` (React) | Hooks, rendering, browser security, accessibility | `hooks-lifecycle`, `rendering`, `browser-security`, `accessibility` |
| `architecture` | API compatibility, persistence, migration, configuration, dependency boundaries | `api-contract`, `data-migration`, `dependency-boundaries` |
| `testing` | Coverage gaps, weak assertions, edge cases, regression proof | `coverage-gaps`, `edge-case-design`, `regression-tests` |

Subagents investigate narrow concerns. The lead is a consolidation layer: it receives subagent findings as structured supporting context and returns the branch's final candidates. Published findings are normalized to the lead as `source_agent`, while traces preserve the executed subagents.

### Provider contract

The graph depends on a provider-neutral protocol:

```python
class ReviewModelProvider(Protocol):
    def review(self, request: AgentRequest) -> list[ReviewFinding]: ...
```

`AgentRequest` includes agent identity, parent, requested subagents, system instructions, diff, changed files, and optional supporting context. `AnthropicReviewProvider` implements the real integration; `FakeReviewProvider` provides deterministic offline behavior.

Anthropic is invoked through LangChain structured output. A permissive internal response schema is normalized into the strict public model. Common nested/JSON-encoded output is unwrapped, and a malformed candidate is dropped without losing valid siblings.

## Planning and technology detection

Adapters combine changed-file extensions, marker files, and manifest terms. One signal group produces confidence `0.55`; each additional independent group adds `0.20`, capped at `1.0`. Multiple adapters may match simultaneously.

| Adapter | Signals |
| --- | --- |
| Python | `.py`, `.pyi`, `pyproject.toml`, `requirements.txt`, `Pipfile` |
| JavaScript | `.js`, `.jsx`, `.mjs`, `.cjs`, `package.json` |
| TypeScript | `.ts`, `.tsx`, `tsconfig.json`, `typescript` manifest text |
| React | `.jsx`, `.tsx`, React/Next/Remix manifest text |
| Angular | `angular.json`, `@angular/core`, `@angular/cli` |
| FastAPI | `fastapi` manifest text |
| Django | `manage.py`, `django` manifest text |

Deterministic selection rules:

| Condition | Result |
| --- | --- |
| Every review | Select correctness |
| Path includes auth, access, credential, crypto, password, permission, policy, security, secret, token, or session | Select security |
| Angular or React detected | Select frontend with framework-specific subagents |
| Path includes migration, database, repository, model, or schema | Select architecture |
| At least one changed file is not test-only | Select testing |

Risk becomes `high` when security is selected, `medium` when architecture is selected or at least ten files changed, and `low` otherwise.

## Verification and GitHub publication

A finding contains:

| Field | Contract |
| --- | --- |
| `title` | 3–120 character issue title |
| `category` | 2–50 character classification |
| `severity` | `low`, `medium`, `high`, `critical` |
| `confidence` | `0.0`–`1.0` |
| `path` | normalized repository-relative destination path |
| `line` | positive new-side line number |
| `comment` | 5–4000 character explanation |
| `evidence` | supporting strings |
| `suggested_fix` | optional remediation |
| `source_agent` | responsible lead |
| `status` | `proposed`, `verified`, or `rejected` |

Validation rejects absolute/traversing paths, unchanged files, context lines, deleted lines, and nonexistent destinations. A fingerprint combines normalized title, category, path, and line. The highest-confidence candidate wins when fingerprints collide.

Published inline comments include severity, title, explanation, and formatted confidence. A separate check run is the authoritative machine-readable outcome.

## Policy and limits

The active policy is stored in SQLite and read when a queued review begins.

### Publication policy

| Setting | Default | Meaning |
| --- | ---: | --- |
| `minimum_severity` | `medium` | Do not publish lower-severity verified findings |
| `require_verified_findings` | `true` | Keep unverified output out of publication |
| `block_on_critical_findings` | `true` | Make verified critical findings block merging |
| `allow_reproduction_tests` | `true` | Permit selection of `regression-tests` investigation |
| `ignored_paths` | generated directories | Remove matching diff sections before review |

Default ignored paths are `**/node_modules/**`, `**/dist/**`, and `**/build/**`.

### Execution ceilings

| Setting | Default | Range |
| --- | ---: | ---: |
| `maximum_specialist_agents` | 6 | 1–20 |
| `maximum_subagents` | 12 | 1–50 |
| `maximum_delegation_depth` | 2 | 1–4 |
| `maximum_runtime_seconds` | 900 | 30–3600 |
| `maximum_comments` | 12 | 1–50 |
| `maximum_cost_usd` | 3.00 | >0–100 |

Cost enforcement is invocation-based because the shared provider contract does not expose billing telemetry. `AEGIS_ESTIMATED_CALL_COST_USD` defaults to `0.25`; allowed calls equal `floor(maximum_cost_usd / estimate)`, with at least one call. This is a conservative guardrail, not an invoice estimator.

## State and failure semantics

### Review states

| State | Meaning |
| --- | --- |
| `queued` | Persisted and awaiting claim |
| `running` | Claimed by the worker |
| `completed` | Worker reached result persistence; errors may still block merging |
| `failed` | Worker could not complete its lifecycle |
| `canceled` | Reserved lifecycle value in API/UI contracts |

Trace events additionally support `skipped`, which is expected for specialists not selected by the plan.

### Why a review can fail with zero findings

Findings and execution health are separate dimensions. Zero findings means no candidate survived validation and publication policy. A failed/blocked result means a required step did not complete—for example:

- a provider call failed;
- the estimated model-cost ceiling was reached;
- total runtime expired;
- GitHub context could not be fetched; or
- publishing the review/check failed.

Treating incomplete analysis as clean would be unsafe, so errors remain blocking even when there are no findings. The UI treats `status == failed` **or any non-empty `errors` list** as blocked.

## Backend

The backend targets Python 3.11+ and uses Pydantic 2. Optional dependency groups separate agents, API, console, and development tooling.

| Module | Responsibility |
| --- | --- |
| `api/app.py` | FastAPI factory, webhook/read/SSE/policy endpoints |
| `api/schemas.py` | HTTP and persisted review/trace contracts |
| `services/reviews.py` | Idempotent ingestion and job publication |
| `github/webhooks.py` | HMAC authentication |
| `github/client.py` | App tokens, context retrieval, reviews, checks |
| `adapters/` | Technology detection |
| `planning.py` | Deterministic assignments and risk |
| `agents/catalog.py` | Lead definitions and instructions |
| `graph.py` | LangGraph state, fan-out, fan-in, verification |
| `providers/` | Anthropic and fake providers |
| `diff_parser.py` | Unified-diff parsing and publishable lines |
| `validation.py` | Finding validation and deduplication |
| `policy_enforcement.py` | Ignore rules, budgets, timeout, blockers |
| `worker.py` | End-to-end asynchronous processing |
| `storage/` | Protocols, in-memory stores, SQLite stores/queue |
| `runtime.py` | Production API dependency wiring |
| `cli.py` | API and worker commands |

CLI:

```bash
python -m aegis_review.cli api [--host 127.0.0.1] [--port 8000]
python -m aegis_review.cli worker-once
python -m aegis_review.cli worker [--poll-seconds 2]
```

## Angular application

The primary product UI is a standalone-component Angular 22 application in `apps/web`.

| Route | View |
| --- | --- |
| `/` | Workspace dashboard |
| `/reviews` | Complete review archive |
| `/reviews/:id` | Individual review graph, findings, and timeline |
| `/ops/` | Streamlit console in production (not an Angular route) |

### Workspace

The workspace shows total, active, finding, and completed counts; the six newest review runs; a distinct latest marker; semantic finding/status pills; and a live nested timeline for the newest review. Empty and API-error states are explicit.

### Archive

The archive presents the full review collection with one consistent row grid for repository/PR, latest marker, findings, decision, and navigation. Blocked rows use danger semantics; findings and states use reusable colored pills.

### Review detail

The detail route has a two-column layout. The main canvas visualizes system stages, the LangGraph coordinator, lead branches, and their subagents. A viewport-bounded right panel switches between verified findings and the complete event timeline and scrolls independently.

### Live state and notifications

`ReviewStore` performs an initial HTTP request and subscribes to the review-list SSE stream. Detail/workspace views subscribe to review-specific snapshots. Native `EventSource` callbacks run inside Angular's zone.

The notification service diffs incoming state and displays snackbars for new reviews, newly blocked reviews, and newly completed reviews. It retains the latest 20 notifications in memory for the header notification panel.

### Reusable components

| Component | Purpose |
| --- | --- |
| `ui-app-header` | Brand, navigation, live status, policy, notifications |
| `ui-status-pill` | Shared status/severity treatment |
| `ui-surface-card` | Consistent titled surface |
| `ui-empty-state` | Accessible no-data explanation |
| `ui-policy-dialog` | Compact active-policy editor |
| `ui-notification-stack` | Snackbar stack and history |
| `review-row` | Consistent review list item |
| `review-agent-card` | Lead and delegated subagent presentation |

## Operations console

Streamlit provides a separate engineering surface with fleet metrics, review selection, agent/subagent summaries, verified finding evidence, suggested fixes, raw timelines, errors, and the complete policy editor. It communicates with FastAPI through `AEGIS_API_URL`; in production it is available under `/ops/` behind Basic Authentication.

## API

FastAPI exposes OpenAPI documentation at `/docs` when the endpoint is directly accessible.

| Method and path | Description |
| --- | --- |
| `GET /health` | Public non-sensitive liveness response |
| `POST /api/v1/github/webhooks` | Signed GitHub ingestion, returns HTTP 202 |
| `GET /api/v1/reviews?limit=50` | Newest-first reviews; range 1–200 |
| `GET /api/v1/reviews/events` | Named `reviews` SSE stream |
| `GET /api/v1/reviews/{id}` | One review |
| `GET /api/v1/reviews/{id}/traces` | Ordered trace events |
| `GET /api/v1/reviews/{id}/findings` | Ordered persisted findings |
| `GET /api/v1/reviews/{id}/events` | Named `review` SSE snapshot |
| `GET /api/v1/policy` | Active/default policy |
| `PUT /api/v1/policy` | Validate and replace policy |

Both SSE routes accept `once=true` for tests/diagnostics. They poll persisted state every second, emit only when serialized state changes, and otherwise send keep-alive comments. This design allows separate API and worker processes to share SQLite as truth.

Webhook response example:

```json
{
  "accepted": true,
  "duplicate": false,
  "review_id": "fa0f548c-6d7a-44d1-a6c5-a10f39507ea5",
  "reason": null
}
```

Invalid signatures return 401, oversized bodies 413, invalid payloads 422, unknown reviews 404, and queue failures 503.

## Persistence

SQLite uses WAL mode and a five-second busy timeout. Review storage, job queue, and policy store use separate connections.

| Table | Purpose |
| --- | --- |
| `reviews` | Current review aggregate; unique delivery ID provides idempotency |
| `review_traces` | Append-only events keyed by review and sequence |
| `review_findings` | Ordered final findings |
| `review_jobs` | Queue status, attempts, last error, timestamps |
| `platform_policy` | Singleton active policy (`id = 1`) |

Domain objects are stored as validated Pydantic JSON payloads. Trace/finding foreign keys cascade with the parent review.

## GitHub App setup

Required repository permissions:

- **Metadata:** read
- **Contents:** read
- **Pull requests:** read and write
- **Checks:** read and write

Subscribe to **Pull request** events and set the webhook URL to:

```text
https://<host>/api/v1/github/webhooks
```

Install the app only on repositories that should be reviewed. The webhook secret must match `GITHUB_WEBHOOK_SECRET`.

The worker signs a short-lived RS256 JWT with the App ID/private key, exchanges it for an installation token, and caches that token until two minutes before expiry. The browser never receives this credential. Setting `GITHUB_TOKEN` locally takes precedence over App-token generation.

Require the check named `Code Review` in branch protection to make the result a merge gate.

## Security model

### Trust boundaries

- Webhook content is untrusted until HMAC verification.
- Diffs/manifests remain untrusted model input.
- Model output remains untrusted until schema and diff validation.
- Credentials live only in API/worker deployment contexts.
- Pull-request code is never executed by the current runtime.

### Controls

- Constant-time signature validation and request-size limits.
- Pydantic schema validation.
- Installation-scoped, short-lived GitHub tokens.
- Read-only external secret mounts; secrets are not copied into images.
- Controlled manifest allowlist.
- Prompt boundary around `<untrusted_diff>`.
- Path traversal and changed-line enforcement.
- Deduplication and publication policy.
- Agent, depth, time, cost, and comment ceilings.
- Fail-closed behavior on incomplete analysis.
- Basic Authentication around production UI, API, SSE, and operations routes.
- Only webhook and health routes are public; the webhook has HMAC authentication.
- GitHub Actions workflow permission is explicitly `contents: read`.

Never commit `.env`, `deploy/auth.env`, tokens, provider keys, or GitHub App PEM files.

## Configuration

Copy `.env.example` to `.env`:

| Variable | Required/default | Description |
| --- | --- | --- |
| `GITHUB_WEBHOOK_SECRET` | required by API | GitHub HMAC secret |
| `GITHUB_APP_ID` | production worker | App identifier |
| `GITHUB_APP_PRIVATE_KEY_PATH` | when no token | Mounted PEM path |
| `GITHUB_TOKEN` | optional, empty | Local static-token alternative |
| `GITHUB_API_URL` | `https://api.github.com` | GitHub API base URL |
| `ANTHROPIC_API_KEY` | required by worker | Provider credential |
| `AEGIS_MODEL` | required by worker | Available Anthropic model ID |
| `AEGIS_DATABASE_PATH` | `./data/aegis.db` | Shared SQLite path |
| `AEGIS_ESTIMATED_CALL_COST_USD` | `0.25` | Per-invocation budget estimate |
| `AEGIS_API_URL` | `http://127.0.0.1:8000` | Streamlit API URL |

Production `deploy/auth.env` additionally supplies `AEGIS_ADMIN_USER` and a Caddy-compatible `AEGIS_ADMIN_PASSWORD_HASH`.

## Local development

Prerequisites: Python 3.11+, npm, and a Node version supported by Angular 22 (CI/production use Node 24.19).

### Backend

```bash
python3 -m pip install -e '.[agents,api,console,dev]'
cp .env.example .env
set -a
. ./.env
set +a
```

Start API and worker in separate configured terminals:

```bash
python3 -m aegis_review.cli api
python3 -m aegis_review.cli worker
```

Verify the API:

```bash
curl http://127.0.0.1:8000/health
```

### Angular

```bash
cd apps/web
npm ci
npm start
```

Open `http://127.0.0.1:4200`. The development proxy forwards `/api` to `http://127.0.0.1:8000`.

### Optional Streamlit console

From the repository root:

```bash
AEGIS_API_URL=http://127.0.0.1:8000 \
  streamlit run src/aegis_review/console/app.py
```

GitHub needs a reachable HTTPS webhook. Use a trusted development tunnel/reverse proxy and never expose maintenance endpoints without authentication.

## Containers and production deployment

### Local Compose

Prepare `.env` and, for App authentication, `secrets/github-app.pem`, then:

```bash
docker compose up --build
```

Open `http://localhost:4200`. Stop without deleting data using `docker compose down`. Deleting the `aegis-data` volume permanently removes reviews, traces, findings, jobs, and policy.

The root Python image uses Python 3.12 slim, installs agents/API/console dependencies, creates a non-root `aegis` user, and stores data under `/data`. The Angular image builds with Node 24.19 and serves through Nginx with SPA fallback and API proxying.

### Production Compose and Caddy

`docker-compose.prod.yml` reuses one `aegis-app:latest` image for API, worker, and console. SQLite and Caddy data are named volumes; source/static/secret mounts are read-only where appropriate.

| External path | Destination | Protection |
| --- | --- | --- |
| `/api/v1/github/webhooks` | FastAPI | GitHub HMAC, no Basic Auth |
| `/health` | FastAPI | public |
| review SSE paths | FastAPI | Basic Auth, buffering disabled |
| `/api/*` | FastAPI | Basic Auth |
| `/ops*` | Streamlit | Basic Auth |
| everything else | Angular SPA | Basic Auth |

### Continuous deployment

`.github/workflows/review.yml` runs for pull requests and pushes to `main`.

Backend job: Python 3.12, dependency installation, pytest.

Frontend job: Node 24.19, `npm ci`, production build, `npm audit --omit=dev`.

After both pass on `main`, the serialized production job:

1. packages the repository without `.git`;
2. configures a dedicated SSH identity from secrets;
3. uploads the release;
4. replaces tracked application files while preserving production secrets/data;
5. builds Angular on the VM;
6. builds/restarts Compose;
7. restarts Caddy to refresh recreated upstream addresses;
8. records `RELEASE_SHA`; and
9. retries the canonical HTTPS health endpoint until startup completes.

Required deployment secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`, and `DEPLOY_URL`. `ANTHROPIC_API_KEY` is also configured as a repository secret; the production worker environment is maintained on the VM.

## Testing

The repository currently collects 60 backend test cases covering adapters, provider normalization, API/security/SSE behavior, console presentation, diff parsing, offline end-to-end execution, GitHub publication, graph hierarchy and partial failures, planning, policy limits, SQLite durability, validation, webhooks, and worker lifecycle.

```bash
# Backend and offline lifecycle
python3 -m pytest

# Angular production build
cd apps/web
npm ci
npm run build

# Angular unit tests
npm test -- --watch=false

# Production dependency audit
npm audit --omit=dev
```

Offline tests use fake GitHub/model providers and temporary databases; they do not call Anthropic or GitHub.

## Repository map

```text
.
├── .github/workflows/review.yml   CI and production deployment
├── apps/web/                      Angular product application
│   ├── public/favicon.svg
│   └── src/app/
│       ├── core/                  models, API, state, notifications
│       ├── pages/                 workspace, archive, review detail
│       ├── review/                review row and agent card
│       └── ui/                    header, pills, cards, dialog, empty state
├── deploy/Caddyfile               HTTPS, auth, routing, SSE
├── secrets/.gitkeep               untracked-secret mount location
├── src/aegis_review/
│   ├── adapters/                  technology detection
│   ├── agents/                    specialist catalog
│   ├── api/                       FastAPI and schemas
│   ├── console/                   Streamlit operations UI
│   ├── github/                    webhook and REST integration
│   ├── providers/                 Anthropic and fake model providers
│   ├── services/                  ingestion service
│   ├── storage/                   protocols, memory, SQLite, policy
│   ├── cli.py                     process entry points
│   ├── config.py                  policy models
│   ├── diff_parser.py             unified-diff parser
│   ├── graph.py                   hierarchical LangGraph
│   ├── models.py                  provider-independent domain models
│   ├── planning.py                deterministic planner
│   ├── policy_enforcement.py      budgets and publication rules
│   ├── runtime.py                 production API wiring
│   ├── settings.py                environment helpers
│   ├── validation.py              finding verification
│   └── worker.py                  review transaction
├── tests/                         unit, integration, offline E2E
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
└── pyproject.toml
```

## Troubleshooting

### Review never appears

Verify App installation, pull-request event subscription, webhook URL, delivery HTTP status, matching webhook secret, and API logs.

### Review stays queued

Verify the worker is running, API/worker share the same database, and the worker has Anthropic model credentials plus GitHub App/token credentials. Inspect `review_jobs` and worker logs.

### Failed with zero findings

Inspect `review.errors` and the event timeline. This means no verified issue was publishable **and** required analysis was incomplete. `PolicyLimitExceeded: estimated model cost limit reached` can be addressed by increasing `maximum_cost_usd`, tuning `AEGIS_ESTIMATED_CALL_COST_USD`, or reducing selected specialists/subagents. Rerun successfully before treating the PR as clean.

### UI does not update live

Confirm the authenticated SSE endpoint is reachable, Caddy's SSE matcher precedes generic `/api/*`, buffering remains disabled, and API/worker share SQLite.

### Older detail does not load

Request review/traces/findings directly, confirm the SQLite volume still exists, use the persisted review UUID in `/reviews/:id`, and confirm production Basic Authentication reaches API calls.

### Old UI after deployment

Compare VM `RELEASE_SHA` with the workflow SHA, ensure Angular's `dist/aegis-console/browser` was rebuilt/mounted at `/srv/web`, restart Caddy after container recreation, then hard-refresh cached assets.

### Brief health failure during deployment

Caddy can be unavailable for seconds after restart. The workflow retries all connection/HTTP errors against the canonical HTTPS URL to avoid false failures.

## Current constraints and extension points

- SQLite and its job queue target a single-node deployment. Horizontal workers need shared transactional claim semantics.
- Cost is invocation-based estimation, not provider billing telemetry.
- The runtime reviews diffs/manifests but does not clone or execute PR code.
- `allow_reproduction_tests` controls the regression-test investigation; no sandbox executor exists yet.
- Technology detection is signal-based rather than a full repository parser.
- Policy is platform-wide; per-repository resolution can be added behind `PolicyStore`.
- Additional model providers can implement `ReviewModelProvider` without changing the graph.
- PostgreSQL can implement `ReviewRepository` without changing API/worker business logic.
- Redis or a workflow platform can implement `ReviewJobPublisher`/queue semantics.
- Angular notification history is session-local.
- Production authentication is Basic Authentication; multi-tenant use should add organization SSO and RBAC.
- The GitHub check must be required by branch protection if failures must block merging.

## Design principles

1. **Deterministic control, probabilistic analysis:** models find issues; code governs trust and effects.
2. **Fail closed:** incomplete required analysis is not a clean review.
3. **Observable execution:** major lifecycle and agent outcomes are persisted.
4. **Bounded autonomy:** time, cost, concurrency, depth, and output are explicit policy.
5. **Provider independence:** orchestration and verification do not depend on Anthropic response objects.
6. **Safe inline publication:** a model cannot comment on an unrelated or unchanged line.
7. **Operational simplicity:** SQLite and Compose provide a complete single-node system with clear migration seams.

---

Agentic Code Review turns a pull-request webhook into an auditable hierarchy of focused reviewers while keeping final authority in deterministic code and repository policy.
