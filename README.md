# CRM Scrape Notion (Local Development)

This project uses:

- FastAPI backend (`backend/`)
- Postgres canonical datastore
- Background worker for queue processing
- Notion as projection/secondary UI

## Prerequisites

- Python 3.11+
- Docker Desktop (recommended)
- PowerShell

## Option A: Run locally with Docker (recommended)

### 1) Start DB + API + worker

```powershell
docker compose -f docker-compose.local.yml up --build
```

API will be at `http://localhost:10000`.

### 2) Apply DB schema

In a second terminal:

```powershell
docker compose -f docker-compose.local.yml exec api python -m app.storage.migrate
```

### 3) Seed local workspace/user mapping

```powershell
docker compose -f docker-compose.local.yml exec api python -m app.storage.seed_dev
```

### 4) Smoke test

```powershell
Invoke-RestMethod http://localhost:10000/health
```

### 5) Verify Playwright in worker image (optional)

```powershell
docker compose -f docker-compose.local.yml run --rm worker python -c "from playwright.sync_api import sync_playwright; print('playwright_ok')"
```

## Option B: Run backend natively (without Docker API/worker)

You can still use Docker only for Postgres, then run Python locally.

### 1) Start Postgres only

```powershell
docker compose -f docker-compose.local.yml up -d db
```

### 2) Create and activate venv

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3) Configure env vars

```powershell
Copy-Item .env.example .env
```

Edit `.env` and keep:

- `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/crm`
- `NOTION_WEBHOOK_SIGNING_SECRET=local-dev-secret`
- `LOCAL_AUTH_BYPASS=true` (local-only shortcut)

Then load it in PowerShell:

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $name, $value = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($name, $value, 'Process')
}
```

### 4) Apply schema

```powershell
python -m app.storage.migrate
```

### 5) Seed local workspace/user mapping

```powershell
python -m app.storage.seed_dev
```

### 6) Run API

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 10000 --reload
```

### 7) Run worker (new terminal, same venv/env)

```powershell
python -m app.workers.job_worker
```

## Test Notion writeback flow locally

This endpoint expects Notion-style signed webhook headers.

1) Build a JSON payload, for example:

```json
{
  "workspace_id": "00000000-0000-0000-0000-000000000000",
  "prospect_id": "00000000-0000-0000-0000-000000000000",
  "editable_fields": {
    "pipeline_stage": "Engaged",
    "notes": "Updated from Notion"
  }
}
```

2) Compute HMAC SHA256 of `{timestamp}.{payload}` with `NOTION_WEBHOOK_SIGNING_SECRET`.

3) Send:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:10000/notion/webhook/notion-update `
  -Headers @{
    "X-Notion-Timestamp" = "1710000000"
    "X-Notion-Signature" = "<hex hmac>"
    "Content-Type" = "application/json"
  } `
  -Body '<payload-json>'
```

If valid, a `from_notion` job is enqueued and the worker applies allowlisted fields.

## Protected route usage (local)

Most routes require:

- `Authorization: Bearer <token>`
- `X-Workspace-Id: <workspace_id>`

For local development with `LOCAL_AUTH_BYPASS=true`, token content is ignored but the header must exist.

Example:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:10000/notion/sync?prospect_id=11111111-1111-1111-1111-111111111111" `
  -Headers @{
    "Authorization" = "Bearer local-dev"
    "X-Workspace-Id" = "11111111-1111-1111-1111-111111111111"
  }
```

## Useful endpoints

- `GET /health`
- `GET /prospects`
- `POST /scrape/runs?source=pr_newswire`
- `GET /notion/sync/status`
- `POST /notion/webhook/notion-update`

## Current implementation scope

- Route and worker scaffolding are implemented.
- Queue processing is wired for `from_notion` allowlisted fields.
- `to_notion` worker path is implemented and updates/creates Notion pages.
- Conflict records are persisted for non-allowlisted Notion inbound fields.

