# Code Review

Code Review is a GitHub-connected, hierarchical multi-agent code-review
platform. It receives signed pull-request webhooks, plans a repository-aware
review, runs specialist leads and focused sub-agents through LangGraph, validates
every proposed inline comment, publishes verified findings to GitHub, and exposes
the complete execution through an Angular maintenance console.

## What is implemented

- GitHub App webhook ingestion with SHA-256 signature verification
- Idempotent webhook delivery handling
- Durable SQLite review, policy, trace, finding, and job storage
- GitHub App installation-token authentication with short-lived token caching
- Optional static GitHub token support for local development
- Pull-request diff and repository-manifest retrieval
- Unified-diff parsing and changed-line validation
- Python, JavaScript, TypeScript, React, Angular, FastAPI, and Django detection
- Deterministic risk and specialist planning
- Parallel LangGraph specialist leads with a real fan-in barrier
- Concurrent, separately invoked sub-agents under every selected lead
- Lead consolidation of sub-agent evidence
- Structured Anthropic responses through LangChain
- Deterministic fake model and GitHub providers for offline testing
- Finding validation, confidence tracking, fingerprinting, and deduplication
- Partial-failure handling for individual agents and sub-agents
- Policy-controlled severity, comment, specialist, sub-agent, cost, and runtime limits
- GitHub inline review publication
- FastAPI review, finding, trace, and policy endpoints
- Angular 22 dashboard, review explorer, agent trace, findings, and policy UI
- Streamlit engineering console for agent inspection and policy maintenance
- Docker Compose deployment for the API, worker, Angular UI, and Streamlit console
- Offline end-to-end test from signed webhook through persisted published review

## Runtime architecture

```text
GitHub pull_request webhook
          |
          v
FastAPI signature verification
          |
          v
SQLite durable job queue  <------ Angular product UI
          |                 <------ Streamlit operations console
          v                         |
Background worker            FastAPI read/config API
          |
          +--> GitHub diff and manifests
          +--> language/framework adapters
          +--> deterministic review plan
          +--> specialist leads
                 +--> focused sub-agents
          +--> deterministic verification
          +--> GitHub Reviews API
```

## Repository layout

```text
src/aegis_review/
  adapters/       Language and framework detection
  agents/         Specialist lead definitions
  api/            FastAPI application and HTTP schemas
  github/         Webhook security, GitHub App auth, and API client
  providers/      Anthropic and deterministic fake model providers
  services/       Review-ingestion application services
  storage/        In-memory and durable SQLite implementations
  graph.py        Hierarchical LangGraph orchestration
  worker.py       Review execution and publication lifecycle
  cli.py          API and worker commands
  console/        Streamlit engineering and maintenance console

apps/web/         Angular 22 maintenance console
tests/            Unit, graph, API, worker, storage, and end-to-end tests
```

## Local development

Python 3.11+ and a supported Node release are required. Angular 22 supports
Node 22.22.3+, Node 24.15+, or Node 26+.

Install the backend:

```bash
python3 -m pip install -e '.[agents,api,dev]'
```

Configure it:

```bash
cp .env.example .env
```

Export the values from `.env` into the API and worker process environments.
At minimum, configure:

- `GITHUB_WEBHOOK_SECRET`
- `GITHUB_APP_ID` and `GITHUB_APP_PRIVATE_KEY_PATH`, or local `GITHUB_TOKEN`
- `ANTHROPIC_API_KEY`
- `AEGIS_MODEL`
- `AEGIS_DATABASE_PATH`

Run the backend processes in separate terminals:

```bash
python3 -m aegis_review.cli api
python3 -m aegis_review.cli worker
```

Run the Angular console:

```bash
cd apps/web
npm install
npm start
```

The Angular development proxy forwards `/api` to `http://127.0.0.1:8000`.

Run the Streamlit operations console:

```bash
python3 -m pip install -e '.[agents,api,console,dev]'
AEGIS_API_URL=http://127.0.0.1:8000 streamlit run src/aegis_review/console/app.py
```

For the production Compose stack, the Angular UI is served at `/` and the
authenticated Streamlit console is served at `/ops`.

## Docker Compose

Create `.env` from `.env.example`. For GitHub App authentication, put the PEM
file under `./secrets` and set:

```text
GITHUB_APP_PRIVATE_KEY_PATH=/run/secrets/github-app.pem
```

Then start the platform:

```bash
docker compose up --build
```

Open `http://localhost:4200`. The API and worker share the durable `aegis-data`
volume.

## GitHub App configuration

Create a GitHub App with these repository permissions:

- Contents: read
- Metadata: read
- Pull requests: read and write

Subscribe to the Pull request event. Configure the webhook URL as:

```text
https://your-aegis-host/api/v1/github/webhooks
```

Set the same random webhook secret in GitHub and `GITHUB_WEBHOOK_SECRET`.
Install the App only on repositories that should receive automated reviews.

## API

```text
GET  /health
POST /api/v1/github/webhooks
GET  /api/v1/reviews
GET  /api/v1/reviews/{review_id}
GET  /api/v1/reviews/{review_id}/traces
GET  /api/v1/reviews/{review_id}/findings
GET  /api/v1/policy
PUT  /api/v1/policy
```

FastAPI also exposes OpenAPI documentation at `/docs` in the default runtime.

## Verification

Backend and complete local lifecycle:

```bash
python3 -m pytest
```

Angular production compilation:

```bash
cd apps/web
npm run build
```

Production frontend dependency audit:

```bash
npm audit --omit=dev
```

Offline tests never call Anthropic or GitHub. Real credentials are used only by
the explicitly started worker process.

## Security boundaries

- Pull-request content is always treated as untrusted model input.
- Model output cannot choose worker commands.
- Only destination paths and added/modified lines can become inline comments.
- GitHub App credentials remain in the worker and are never sent to reviewed code.
- The current worker analyzes diffs and manifests; it does not execute pull-request
  code. Sandboxed compiler, linter, and test adapters can be added later without
  changing the review or provider contracts.
- The Angular maintenance API is intended for a trusted local/private network in
  this release. Add organization SSO or an authenticating reverse proxy before
  exposing it publicly.
