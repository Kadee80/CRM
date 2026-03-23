import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from psycopg.rows import dict_row

from app.config import get_required_env
from app.notion.client import upsert_page
from app.storage.db import get_conn

ALLOWLIST = {"pipeline_stage", "notes", "primary_icp"}


def enqueue_notion_sync_job(
  workspace_id: str,
  prospect_id: str,
  direction: str,
  payload: dict[str, Any] | None = None,
) -> str:
  payload = payload or {}
  with get_conn() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
      cur.execute(
        """
        insert into notion_sync_jobs (workspace_id, prospect_id, direction, status, payload)
        values (%s, %s, %s, 'queued', %s)
        returning id
        """,
        (workspace_id, prospect_id, direction, payload),
      )
      row = cur.fetchone()
    conn.commit()
  return str(row["id"])


def enqueue_to_notion_for_workspace(workspace_id: str, prospect_id: str | None = None) -> int:
  with get_conn() as conn:
    with conn.cursor() as cur:
      if prospect_id:
        cur.execute(
          """
          insert into notion_sync_jobs (workspace_id, prospect_id, direction, status, payload)
          values (%s, %s, 'to_notion', 'queued', '{}'::jsonb)
          on conflict do nothing
          """,
          (workspace_id, prospect_id),
        )
        inserted = cur.rowcount
      else:
        cur.execute(
          """
          insert into notion_sync_jobs (workspace_id, prospect_id, direction, status, payload)
          select p.workspace_id, p.id, 'to_notion', 'queued', '{}'::jsonb
          from prospects p
          where p.workspace_id = %s
          """,
          (workspace_id,),
        )
        inserted = cur.rowcount
    conn.commit()
  return inserted


def fetch_next_job() -> dict[str, Any] | None:
  with get_conn() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
      cur.execute(
        """
        select id, workspace_id, prospect_id, direction, payload, attempt_count, max_attempts
        from notion_sync_jobs
        where status = 'queued'
        order by created_at asc
        limit 1
        for update skip locked
        """
      )
      row = cur.fetchone()
      if not row:
        conn.commit()
        return None
      cur.execute(
        """
        update notion_sync_jobs
        set status = 'running',
            updated_at = now()
        where id = %s
        """,
        (row["id"],),
      )
    conn.commit()
  return row


def mark_job_succeeded(job_id: str) -> None:
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        update notion_sync_jobs
        set status = 'succeeded',
            updated_at = now()
        where id = %s
        """,
        (job_id,),
      )
    conn.commit()


def mark_job_failed(job_id: str, attempt_count: int, max_attempts: int, error: str) -> None:
  next_status = "dead_letter" if attempt_count + 1 >= max_attempts else "queued"
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        update notion_sync_jobs
        set status = %s,
            attempt_count = attempt_count + 1,
            last_error = %s,
            updated_at = now()
        where id = %s
        """,
        (next_status, error[:2000], job_id),
      )
    conn.commit()


def apply_allowlisted_fields_from_notion(job: dict[str, Any]) -> None:
  payload = job.get("payload") or {}
  editable_fields = payload.get("editable_fields", {})
  updates = {k: v for k, v in editable_fields.items() if k in ALLOWLIST}
  non_allowlisted = {k: v for k, v in editable_fields.items() if k not in ALLOWLIST}
  if non_allowlisted:
    create_conflicts(
      workspace_id=str(job["workspace_id"]),
      prospect_id=str(job["prospect_id"]),
      notion_fields=non_allowlisted,
      notion_last_edited_at=payload.get("notion_last_edited_at"),
    )
  if not updates:
    return

  set_parts = []
  values: list[Any] = []
  for field, value in updates.items():
    set_parts.append(f"{field} = %s")
    values.append(value)

  set_parts.append("updated_at = %s")
  values.append(datetime.now(timezone.utc))
  values.append(job["prospect_id"])
  values.append(job["workspace_id"])

  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(
        f"""
        update prospects
        set {", ".join(set_parts)}
        where id = %s and workspace_id = %s
        """,
        tuple(values),
      )
      for field, value in updates.items():
        cur.execute(
          """
          insert into field_change_events (
            workspace_id, prospect_id, source, field_name, old_value, new_value, changed_by_user_id
          )
          values (%s, %s, 'notion_sync', %s, null, %s::jsonb, null)
          """,
          (job["workspace_id"], job["prospect_id"], field, _json_scalar(value)),
        )
      cur.execute(
        """
        update notion_conflicts
        set status = 'resolved_notion',
            resolved_at = now()
        where workspace_id = %s and prospect_id = %s and field_name = any(%s) and status = 'open'
        """,
        (job["workspace_id"], job["prospect_id"], list(updates.keys())),
      )
    conn.commit()


def create_conflicts(
  *,
  workspace_id: str,
  prospect_id: str,
  notion_fields: dict[str, Any],
  notion_last_edited_at: str | None,
) -> None:
  with get_conn() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
      cur.execute(
        """
        select company_name, website, canonical_domain, fit_score, intent_score, total_score, p.updated_at
        from prospects p
        left join scores s on s.prospect_id = p.id
        where p.workspace_id = %s and p.id = %s
        """,
        (workspace_id, prospect_id),
      )
      app_row = cur.fetchone() or {}
      for field, notion_value in notion_fields.items():
        cur.execute(
          """
          insert into notion_conflicts (
            workspace_id, prospect_id, field_name, app_value, notion_value,
            app_last_updated_at, notion_last_edited_at, status
          )
          values (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, 'open')
          """,
          (
            workspace_id,
            prospect_id,
            field,
            _json_scalar(app_row.get(field)),
            _json_scalar(notion_value),
            app_row.get("updated_at"),
            notion_last_edited_at,
          ),
        )
    conn.commit()


def process_to_notion(job: dict[str, Any]) -> None:
  notion_database_id = get_required_env("NOTION_DATABASE_ID")
  workspace_id = str(job["workspace_id"])
  prospect_id = str(job["prospect_id"])
  with get_conn() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
      cur.execute(
        """
        select id as prospect_id, company_name, website, pipeline_stage, primary_icp, notes, updated_at
        from prospects
        where workspace_id = %s and id = %s
        """,
        (workspace_id, prospect_id),
      )
      prospect = cur.fetchone()
      if not prospect:
        raise RuntimeError(f"Prospect not found for to_notion job: {prospect_id}")

      cur.execute(
        """
        select notion_page_id
        from notion_links
        where workspace_id = %s and prospect_id = %s
        """,
        (workspace_id, prospect_id),
      )
      link_row = cur.fetchone()
      notion_page_id = link_row["notion_page_id"] if link_row else None

    notion_page = upsert_page(
      notion_page_id=notion_page_id,
      notion_database_id=notion_database_id,
      prospect=prospect,
    )
    page_id = notion_page["id"]
    sync_hash = _sync_hash(prospect)
    with conn.cursor() as cur:
      cur.execute(
        """
        insert into notion_links (workspace_id, prospect_id, notion_page_id, last_synced_hash, last_synced_at, sync_status)
        values (%s, %s, %s, %s, now(), 'synced')
        on conflict (workspace_id, prospect_id)
        do update set notion_page_id = excluded.notion_page_id,
                      last_synced_hash = excluded.last_synced_hash,
                      last_synced_at = now(),
                      sync_status = 'synced'
        """,
        (workspace_id, prospect_id, page_id, sync_hash),
      )
    conn.commit()


def list_open_conflicts(workspace_id: str, prospect_id: str) -> list[dict[str, Any]]:
  with get_conn() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
      cur.execute(
        """
        select field_name, app_value, notion_value, app_last_updated_at, notion_last_edited_at
        from notion_conflicts
        where workspace_id = %s and prospect_id = %s and status = 'open'
        order by created_at desc
        """,
        (workspace_id, prospect_id),
      )
      rows = cur.fetchall()
  return [dict(row) for row in rows]


def resolve_conflict_with_notion_values(workspace_id: str, prospect_id: str, updates: dict[str, Any]) -> None:
  safe_updates = {k: v for k, v in updates.items() if k in ALLOWLIST}
  if not safe_updates:
    return
  set_parts = []
  values: list[Any] = []
  for field, value in safe_updates.items():
    set_parts.append(f"{field} = %s")
    values.append(value)
  values.extend([prospect_id, workspace_id])
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(
        f"""
        update prospects
        set {", ".join(set_parts)}, updated_at = now()
        where id = %s and workspace_id = %s
        """,
        tuple(values),
      )
      cur.execute(
        """
        update notion_conflicts
        set status = 'resolved_notion',
            resolved_at = now()
        where workspace_id = %s and prospect_id = %s and field_name = any(%s) and status = 'open'
        """,
        (workspace_id, prospect_id, list(safe_updates.keys())),
      )
    conn.commit()


def _json_scalar(value: Any) -> str:
  if value is None:
    return "null"
  if isinstance(value, bool):
    return "true" if value else "false"
  if isinstance(value, (int, float)):
    return str(value)
  escaped = str(value).replace('"', '\\"')
  return f"\"{escaped}\""


def _sync_hash(prospect: dict[str, Any]) -> str:
  data = {
    "company_name": prospect.get("company_name"),
    "website": prospect.get("website"),
    "pipeline_stage": prospect.get("pipeline_stage"),
    "primary_icp": prospect.get("primary_icp"),
    "notes": prospect.get("notes"),
  }
  payload = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
  return hashlib.sha256(payload).hexdigest()

