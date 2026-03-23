# Deployment Blueprint (Render + Supabase + Vercel)

## Topology

- Backend API: Render web service (`crm-api`)
- Background jobs: Render worker service (`crm-worker`)
- Database + Auth: Supabase (Postgres + Auth)
- Frontend: Vercel (Next.js) or Render static site

This split removes Heroku dyno coupling between web and scraper/sync workloads.
It also uses separate Dockerfiles so worker-specific dependencies do not inflate API images.

## Why this solves dyno constraints

- API and worker scale independently.
- Worker crashes or heavy scraping do not block API response times.
- Durable state remains in Supabase Postgres, not local disk.
- Notion sync is asynchronous and retryable.

## Step-by-Step Setup

1. Create a Supabase project.
2. Get `DATABASE_URL`, `SUPABASE_URL`, and JWT metadata values.
3. Apply `backend/app/storage/schema.sql` to Supabase Postgres.
4. Connect GitHub repo to Render and enable Blueprint deploy (`render.yaml`).
5. Set required secret env vars in Render:
   - `DATABASE_URL`
   - `SUPABASE_URL`
   - `SUPABASE_JWKS_URL`
   - `SUPABASE_JWT_AUDIENCE`
   - `SUPABASE_JWT_ISSUER`
   - `NOTION_API_TOKEN`
   - `NOTION_DATABASE_ID`
   - `NOTION_WEBHOOK_SIGNING_SECRET`
6. Deploy frontend to Vercel and set:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_BASE_URL` (Render API URL)

## Free-tier-safe defaults

- Keep `JOB_WORKER_POLL_SECONDS=10` or higher.
- Scraping limits in `scraper-config/sources.yaml`:
  - `max_pages_per_run` low (10-25)
  - low per-domain request rate
- Use API/RSS sources first; Playwright only as fallback.
- Run scrape jobs on-demand, not cron-heavy schedules.

## Bidirectional Notion Sync Policy

Recommended:

- Canonical store remains Postgres.
- Notion writes back only allowlisted fields:
  - `pipeline_stage`
  - `notes`
  - `primary_icp`
- High-risk fields require manual conflict review:
  - `company_name`, `website`, `canonical_domain`, and all scores

Server-side flow:

1. Notion edit event arrives at `POST /notion/webhook/notion-update`.
2. API verifies webhook signature.
3. API enqueues `from_notion` sync job.
4. Worker evaluates field-level diffs.
5. Low-risk allowlisted fields auto-apply.
6. High-risk fields are marked `conflict` and surfaced to UI via `GET /notion/conflicts/{prospect_id}`.
7. Reviewer resolves via explicit API action.

## Operational checks

- API health: `GET /health`
- Queue health: `GET /notion/sync/status`
- Source auth preflight: `POST /scrape/session/validate?source=...`
- Add alerting on:
  - repeated worker failures
  - rising dead-letter jobs
  - sync conflict backlog

## Minimal production hardening

- Rotate Notion and Supabase secrets on schedule.
- Never log auth cookies or bearer tokens.
- Enforce workspace scoping on every read/write query.
- Store audit trail of state-changing actions.

