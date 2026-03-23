-- CRM v2 canonical schema (Postgres source of truth)
-- Notion is a projection layer and never canonical storage.

create extension if not exists pgcrypto;

create table if not exists workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table if not exists workspace_users (
  workspace_id uuid not null references workspaces(id) on delete cascade,
  user_id uuid not null,
  role text not null check (role in ('owner', 'admin', 'member', 'viewer')),
  created_at timestamptz not null default now(),
  primary key (workspace_id, user_id)
);

create table if not exists prospects (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  company_name text not null,
  website text,
  canonical_domain text,
  primary_icp text not null default 'FS+Tech PR/Marketing',
  pipeline_stage text not null default 'Targeted'
    check (pipeline_stage in ('Targeted', 'Contacted', 'Engaged', 'Qualified', 'Proposal', 'Won', 'Lost', 'Nurture')),
  notes text,
  created_by_user_id uuid,
  updated_by_user_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_prospects_workspace on prospects(workspace_id);
create index if not exists idx_prospects_domain on prospects(workspace_id, canonical_domain);

create table if not exists prospect_identities (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid not null references prospects(id) on delete cascade,
  workspace_id uuid not null references workspaces(id) on delete cascade,
  identity_type text not null check (identity_type in ('canonical_domain', 'normalized_company_name', 'external_id')),
  identity_value text not null,
  created_at timestamptz not null default now(),
  unique (workspace_id, identity_type, identity_value)
);

create table if not exists signals (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid not null references prospects(id) on delete cascade,
  workspace_id uuid not null references workspaces(id) on delete cascade,
  signal_type text not null,
  summary text not null,
  confidence numeric(5, 2) not null default 0.00 check (confidence >= 0 and confidence <= 1),
  detected_at timestamptz not null default now()
);

create index if not exists idx_signals_prospect on signals(prospect_id);

create table if not exists evidence (
  id uuid primary key default gen_random_uuid(),
  signal_id uuid not null references signals(id) on delete cascade,
  workspace_id uuid not null references workspaces(id) on delete cascade,
  url text not null,
  title text,
  source_name text,
  published_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists scores (
  prospect_id uuid primary key references prospects(id) on delete cascade,
  workspace_id uuid not null references workspaces(id) on delete cascade,
  fit_score integer not null check (fit_score between 0 and 50),
  intent_score integer not null check (intent_score between 0 and 50),
  total_score integer not null check (total_score between 0 and 100),
  fit_components_json jsonb not null default '{}'::jsonb,
  intent_components_json jsonb not null default '{}'::jsonb,
  scored_at timestamptz not null default now()
);

create table if not exists source_records (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  source_name text not null,
  source_url text not null,
  raw_payload jsonb not null,
  normalized_payload jsonb,
  processed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists scrape_runs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  source_name text not null,
  status text not null check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  pages_fetched integer not null default 0,
  records_emitted integer not null default 0,
  error_message text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists notion_links (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  prospect_id uuid not null references prospects(id) on delete cascade,
  notion_page_id text not null,
  last_synced_hash text,
  last_synced_at timestamptz,
  sync_status text not null default 'pending' check (sync_status in ('pending', 'synced', 'failed', 'conflict')),
  unique (workspace_id, prospect_id),
  unique (workspace_id, notion_page_id)
);

create table if not exists notion_sync_jobs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  prospect_id uuid not null references prospects(id) on delete cascade,
  direction text not null check (direction in ('to_notion', 'from_notion')),
  status text not null check (status in ('queued', 'running', 'succeeded', 'failed', 'dead_letter')),
  attempt_count integer not null default 0,
  max_attempts integer not null default 5,
  payload jsonb not null default '{}'::jsonb,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists notion_conflicts (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  prospect_id uuid not null references prospects(id) on delete cascade,
  field_name text not null,
  app_value jsonb,
  notion_value jsonb,
  app_last_updated_at timestamptz,
  notion_last_edited_at timestamptz,
  status text not null default 'open' check (status in ('open', 'resolved_app', 'resolved_notion')),
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create index if not exists idx_notion_conflicts_scope
  on notion_conflicts (workspace_id, prospect_id, status, created_at desc);

create table if not exists field_change_events (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  prospect_id uuid not null references prospects(id) on delete cascade,
  source text not null check (source in ('app_ui', 'scraper', 'notion_sync', 'admin')),
  field_name text not null,
  old_value jsonb,
  new_value jsonb,
  changed_by_user_id uuid,
  changed_at timestamptz not null default now()
);

