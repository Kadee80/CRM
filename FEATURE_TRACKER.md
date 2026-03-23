# Feature Tracker

This document tracks implemented features and how to view/test each one.

## How to update this file

When adding a feature:

1. Add a new entry under `Implemented Features`.
2. Include:
   - `Status`
   - `What it does`
   - `Where in code`
   - `How to view/test`
3. Keep steps copy/paste ready (PowerShell where possible).

## Implemented Features

### 1) Local run + API preview

- **Status:** Implemented
- **What it does:** Runs API, DB, and worker locally; exposes docs UI.
- **Where in code:** `docker-compose.local.yml`, `backend/app/main.py`, `README.md`
- **How to view/test:**
  1. `docker compose -f docker-compose.local.yml up --build`
  2. Open [http://localhost:10000/docs](http://localhost:10000/docs)
  3. Check [http://localhost:10000/health](http://localhost:10000/health)

### 2) Workspace auth guard (with local bypass)

- **Status:** Implemented
- **What it does:** Protects routes with bearer token + workspace scope; supports local bypass mode.
- **Where in code:** `backend/app/auth/supabase.py`
- **How to view/test:**
  1. Ensure `LOCAL_AUTH_BYPASS=true` in local env.
  2. Call a protected route with headers:
     - `Authorization: Bearer local-dev`
     - `X-Workspace-Id: 11111111-1111-1111-1111-111111111111`
  3. Example:
     - `Invoke-RestMethod -Uri "http://localhost:10000/prospects" -Headers @{ "Authorization"="Bearer local-dev"; "X-Workspace-Id"="11111111-1111-1111-1111-111111111111" }`

### 3) Prospects API (DB-backed)

- **Status:** Implemented
- **What it does:** Lists, fetches, and updates prospects from Postgres with workspace scoping.
- **Where in code:** `backend/app/api/routes/prospects.py`
- **How to view/test:**
  1. List:
     - `GET /prospects?limit=50&offset=0`
  2. Filter:
     - `GET /prospects?stage=Targeted&min_total_score=0`
  3. Detail:
     - `GET /prospects/{id}`
  4. Update:
     - `PATCH /prospects/{id}` with body like `{ "notes": "Updated note", "pipeline_stage": "Engaged" }`

### 4) Notion sync jobs (two-way framework)

- **Status:** Implemented (framework)
- **What it does:** Queues outbound Notion sync and inbound Notion webhook updates with conflict tracking.
- **Where in code:** `backend/app/api/routes/notion_sync.py`, `backend/app/jobs/notion_sync.py`, `backend/app/notion/client.py`
- **How to view/test:**
  1. Trigger outbound sync:
     - `POST /notion/sync?prospect_id=<id>`
  2. Check status:
     - `GET /notion/sync/status`
  3. Check conflicts:
     - `GET /notion/conflicts/{prospect_id}`

### 5) Scrape run queue + PR Newswire ingestion slice

- **Status:** Implemented (first source slice)
- **What it does:** Queues `scrape_runs`, worker processes PR Newswire listing, stores source records, and upserts prospects by canonical domain.
- **Where in code:** `backend/app/api/routes/scrape.py`, `backend/app/jobs/scrape_runs.py`, `backend/app/scrape/runner.py`, `backend/app/scrape/extractors/pr_newswire.py`
- **How to view/test:**
  1. Queue run:
     - `POST /scrape/runs?source=pr_newswire`
  2. Poll run:
     - `GET /scrape/runs/{run_id}`
  3. View results:
     - `GET /prospects`

### 6) Worker split + Playwright worker image

- **Status:** Implemented
- **What it does:** Uses separate API and worker Dockerfiles; worker image includes Playwright Chromium.
- **Where in code:** `backend/Dockerfile.api`, `backend/Dockerfile.worker`, `render.yaml`
- **How to view/test:**
  1. Build worker:
     - `docker compose -f docker-compose.local.yml build worker`
  2. Verify Playwright import:
     - `docker compose -f docker-compose.local.yml run --rm worker python -c "from playwright.sync_api import sync_playwright; print('playwright_ok')"`

## Planned / Next

- Implement scoring service integration in scrape pipeline (`signals/scorer.py`).
- Add frontend app shell (`/login`, `/prospects`, detail view).
- Add stronger conflict resolution UI flow for Notion writeback.

## New Feature Template

Copy/paste this block when adding a new feature:

```md
### <Feature Name>

- **Status:** Implemented | Partial | Planned
- **What it does:** <1-2 sentence summary>
- **Where in code:** `<path1>`, `<path2>`
- **How to view/test:**
  1. <step>
  2. <step>
  3. <step>
```
