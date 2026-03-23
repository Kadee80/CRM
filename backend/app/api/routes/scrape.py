from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.supabase import RequestContext, require_context
from app.scrape.config import get_source_config
from app.storage.db import get_conn


router = APIRouter()


@router.post("/runs")
def create_scrape_run(
  source: str = Query(...),
  context: RequestContext = Depends(require_context),
) -> dict:
  source_cfg = _get_source(source)
  if not source_cfg.get("enabled") or not source_cfg.get("allowed_by_policy"):
    raise HTTPException(status_code=400, detail=f"Source is not policy-enabled: {source}")
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        insert into scrape_runs (workspace_id, source_name, status)
        values (%s, %s, 'queued')
        returning id
        """,
        (context.workspace_id, source),
      )
      run_id = cur.fetchone()[0]
    conn.commit()
  return {"status": "queued", "source": source, "run_id": str(run_id)}


@router.get("/runs/{run_id}")
def get_scrape_run(run_id: str, context: RequestContext = Depends(require_context)) -> dict:
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        select id, source_name, status, pages_fetched, records_emitted, error_message, started_at, finished_at
        from scrape_runs
        where id = %s and workspace_id = %s
        """,
        (run_id, context.workspace_id),
      )
      row = cur.fetchone()
  if not row:
    raise HTTPException(status_code=404, detail="Run not found")
  return {
    "id": str(row[0]),
    "source_name": row[1],
    "status": row[2],
    "pages_fetched": row[3],
    "records_emitted": row[4],
    "error_message": row[5],
    "started_at": row[6],
    "finished_at": row[7],
  }


@router.post("/session/validate")
def validate_source_session(
  source: str = Query(...),
  context: RequestContext = Depends(require_context),
) -> dict:
  _ = context
  cfg = _get_source(source)
  # TODO: Check cookie/session health for a source without scraping.
  return {
    "source": source,
    "auth_required": bool(cfg.get("auth_required", False)),
    "session_valid": False,
    "details": "Not implemented",
  }


def _get_source(source_id: str) -> dict:
  try:
    return get_source_config(source_id)
  except KeyError:
    raise HTTPException(status_code=404, detail=f"Unknown source: {source_id}") from None

