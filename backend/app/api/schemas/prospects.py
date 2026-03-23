from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


PipelineStage = Literal[
  "Targeted", "Contacted", "Engaged", "Qualified", "Proposal", "Won", "Lost", "Nurture"
]


class ProspectSummary(BaseModel):
  id: str
  company_name: str
  website: Optional[HttpUrl] = None
  pipeline_stage: PipelineStage
  fit_score: int = Field(ge=0, le=50)
  intent_score: int = Field(ge=0, le=50)
  total_score: int = Field(ge=0, le=100)
  updated_at: datetime


class ProspectPatch(BaseModel):
  pipeline_stage: Optional[PipelineStage] = None
  notes: Optional[str] = None


class ProspectNotionEditablePatch(BaseModel):
  # Keep this allowlist tight for Notion writeback safety.
  pipeline_stage: Optional[PipelineStage] = None
  notes: Optional[str] = None
  primary_icp: Optional[str] = None


class ProspectConflict(BaseModel):
  field: str
  app_value: str | None = None
  notion_value: str | None = None
  app_last_updated_at: Optional[datetime] = None
  notion_last_edited_at: Optional[datetime] = None

