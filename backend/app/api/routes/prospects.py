from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.rows import dict_row

from app.api.schemas.prospects import ProspectPatch, ProspectSummary
from app.auth.supabase import RequestContext, require_context
from app.storage.db import get_conn


router = APIRouter()


@router.get("")
def list_prospects(
  stage: str | None = Query(default=None),
  min_total_score: int | None = Query(default=None, ge=0, le=100),
  limit: int = Query(default=50, ge=1, le=200),
  offset: int = Query(default=0, ge=0),
  context: RequestContext = Depends(require_context),
) -> dict:
  where = ["p.workspace_id = %s"]
  params: list[object] = [context.workspace_id]
  if stage:
    where.append("p.pipeline_stage = %s")
    params.append(stage)
  if min_total_score is not None:
    where.append("coalesce(s.total_score, 0) >= %s")
    params.append(min_total_score)
  params.extend([limit, offset])

  with get_conn() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
      cur.execute(
        f"""
        select
          p.id::text as id,
          p.company_name,
          p.website,
          p.pipeline_stage,
          coalesce(s.fit_score, 0) as fit_score,
          coalesce(s.intent_score, 0) as intent_score,
          coalesce(s.total_score, 0) as total_score,
          p.updated_at
        from prospects p
        left join scores s on s.prospect_id = p.id
        where {" and ".join(where)}
        order by coalesce(s.total_score, 0) desc, p.updated_at desc
        limit %s offset %s
        """,
        tuple(params),
      )
      rows = cur.fetchall()

  return {
    "items": [ProspectSummary.model_validate(row).model_dump(mode="json") for row in rows],
    "workspace_id": context.workspace_id,
    "filters": {"stage": stage, "min_total_score": min_total_score, "limit": limit, "offset": offset},
  }


@router.get("/{prospect_id}", response_model=ProspectSummary)
def get_prospect(prospect_id: str, context: RequestContext = Depends(require_context)) -> ProspectSummary:
  with get_conn() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
      cur.execute(
        """
        select
          p.id::text as id,
          p.company_name,
          p.website,
          p.pipeline_stage,
          coalesce(s.fit_score, 0) as fit_score,
          coalesce(s.intent_score, 0) as intent_score,
          coalesce(s.total_score, 0) as total_score,
          p.updated_at
        from prospects p
        left join scores s on s.prospect_id = p.id
        where p.id = %s and p.workspace_id = %s
        limit 1
        """,
        (prospect_id, context.workspace_id),
      )
      row = cur.fetchone()
  if not row:
    raise HTTPException(status_code=404, detail="Prospect not found")
  return ProspectSummary.model_validate(row)


@router.patch("/{prospect_id}")
def patch_prospect(
  prospect_id: str,
  body: ProspectPatch,
  context: RequestContext = Depends(require_context),
) -> dict:
  updates = body.model_dump(exclude_none=True)
  if not updates:
    return {"prospect_id": prospect_id, "workspace_id": context.workspace_id, "updated_fields": {}}

  set_parts = []
  set_values: list[object] = []
  for field, value in updates.items():
    set_parts.append(f"{field} = %s")
    set_values.append(value)
  set_values.extend([context.user_id, prospect_id, context.workspace_id])

  with get_conn() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
      cur.execute(
        """
        select id
        from prospects
        where id = %s and workspace_id = %s
        limit 1
        """,
        (prospect_id, context.workspace_id),
      )
      existing = cur.fetchone()
      if not existing:
        raise HTTPException(status_code=404, detail="Prospect not found")

      cur.execute(
        f"""
        update prospects
        set {", ".join(set_parts)},
            updated_by_user_id = %s,
            updated_at = now()
        where id = %s and workspace_id = %s
        """,
        tuple(set_values),
      )
      for field, value in updates.items():
        cur.execute(
          """
          insert into field_change_events (
            workspace_id, prospect_id, source, field_name, old_value, new_value, changed_by_user_id
          )
          values (%s, %s, 'app_ui', %s, null, to_jsonb(%s::text), %s)
          """,
          (context.workspace_id, prospect_id, field, str(value), context.user_id),
        )
    conn.commit()

  return {
    "prospect_id": prospect_id,
    "workspace_id": context.workspace_id,
    "updated_fields": updates,
  }

