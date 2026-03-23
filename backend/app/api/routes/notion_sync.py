from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app.api.schemas.prospects import ProspectConflict, ProspectNotionEditablePatch
from app.auth.supabase import RequestContext, require_context
from app.config import get_required_env
from app.jobs.notion_sync import (
  enqueue_notion_sync_job,
  enqueue_to_notion_for_workspace,
  list_open_conflicts,
  resolve_conflict_with_notion_values,
)
from app.notion.security import verify_webhook_signature
from app.storage.db import get_conn


router = APIRouter()


@router.post("/sync")
def trigger_sync(
  prospect_id: str | None = Query(default=None),
  context: RequestContext = Depends(require_context),
) -> dict:
  count = enqueue_to_notion_for_workspace(context.workspace_id, prospect_id)
  return {"status": "queued", "direction": "to_notion", "prospect_id": prospect_id, "enqueued": count}


@router.get("/sync/status")
def get_sync_status(context: RequestContext = Depends(require_context)) -> dict:
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        select
          count(*) filter (where status = 'queued') as queued,
          count(*) filter (where status = 'running') as running,
          count(*) filter (where status = 'failed') as failed,
          count(*) filter (where status = 'dead_letter') as dead_letter
        from notion_sync_jobs
        where workspace_id = %s
        """,
        (context.workspace_id,),
      )
      queued, running, failed, dead_letter = cur.fetchone()
  return {"queued": queued, "running": running, "failed": failed, "dead_letter": dead_letter}


@router.post("/webhook/notion-update")
async def handle_notion_update_webhook(
  request: Request,
  x_notion_signature: str | None = Header(default=None),
  x_notion_timestamp: str | None = Header(default=None),
) -> dict:
  if not x_notion_signature or not x_notion_timestamp:
    raise HTTPException(status_code=400, detail="Missing Notion signature headers")

  body_bytes = await request.body()
  signing_secret = get_required_env("NOTION_WEBHOOK_SIGNING_SECRET")
  is_valid = verify_webhook_signature(
    signing_secret=signing_secret,
    payload=body_bytes,
    timestamp=x_notion_timestamp,
    signature_header=x_notion_signature,
  )
  if not is_valid:
    raise HTTPException(status_code=401, detail="Invalid webhook signature")

  payload = await request.json()
  workspace_id = payload.get("workspace_id")
  prospect_id = payload.get("prospect_id")
  editable_fields = payload.get("editable_fields", {})
  notion_last_edited_at = payload.get("notion_last_edited_at")
  if not workspace_id or not prospect_id:
    raise HTTPException(status_code=400, detail="workspace_id and prospect_id are required")

  job_id = enqueue_notion_sync_job(
    workspace_id=str(workspace_id),
    prospect_id=str(prospect_id),
    direction="from_notion",
    payload={"editable_fields": editable_fields, "notion_last_edited_at": notion_last_edited_at},
  )
  return {"accepted": True, "job_id": job_id}


@router.get("/conflicts/{prospect_id}", response_model=list[ProspectConflict])
def get_notion_conflicts(
  prospect_id: str,
  context: RequestContext = Depends(require_context),
) -> list[ProspectConflict]:
  rows = list_open_conflicts(context.workspace_id, prospect_id)
  return [
    ProspectConflict(
      field=str(row["field_name"]),
      app_value=str(row["app_value"]) if row["app_value"] is not None else None,
      notion_value=str(row["notion_value"]) if row["notion_value"] is not None else None,
      app_last_updated_at=row["app_last_updated_at"],
      notion_last_edited_at=row["notion_last_edited_at"],
    )
    for row in rows
  ]


@router.post("/apply-from-notion/{prospect_id}")
def apply_notion_changes(
  prospect_id: str,
  body: ProspectNotionEditablePatch,
  context: RequestContext = Depends(require_context),
) -> dict:
  updates = body.model_dump(exclude_none=True)
  resolve_conflict_with_notion_values(context.workspace_id, prospect_id, updates)
  return {
    "prospect_id": prospect_id,
    "applied_fields": updates,
    "source": "notion_sync",
  }

