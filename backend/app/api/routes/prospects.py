from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.api.schemas.prospects import ProspectPatch, ProspectSummary
from app.auth.supabase import RequestContext, require_context


router = APIRouter()


@router.get("")
def list_prospects(
  stage: str | None = Query(default=None),
  min_total_score: int | None = Query(default=None, ge=0, le=100),
  context: RequestContext = Depends(require_context),
) -> dict:
  # TODO: Replace with workspace-scoped DB query.
  return {
    "items": [],
    "workspace_id": context.workspace_id,
    "filters": {"stage": stage, "min_total_score": min_total_score},
  }


@router.get("/{prospect_id}", response_model=ProspectSummary)
def get_prospect(prospect_id: str, context: RequestContext = Depends(require_context)) -> ProspectSummary:
  # TODO: Replace with DB lookup.
  now = datetime.now(timezone.utc)
  return ProspectSummary(
    id=prospect_id,
    company_name="Example Co",
    website=None,
    pipeline_stage="Targeted",
    fit_score=20,
    intent_score=15,
    total_score=35,
    updated_at=now,
  )


@router.patch("/{prospect_id}")
def patch_prospect(
  prospect_id: str,
  body: ProspectPatch,
  context: RequestContext = Depends(require_context),
) -> dict:
  # TODO: Persist only allowed fields and write audit event.
  return {
    "prospect_id": prospect_id,
    "workspace_id": context.workspace_id,
    "updated_fields": body.model_dump(exclude_none=True),
  }

