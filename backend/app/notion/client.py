from typing import Any

import httpx

from app.config import get_required_env

NOTION_VERSION = "2022-06-28"


def _headers() -> dict[str, str]:
  return {
    "Authorization": f"Bearer {get_required_env('NOTION_API_TOKEN')}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
  }


def build_notion_properties(prospect: dict[str, Any]) -> dict[str, Any]:
  return {
    "CompanyName": {"title": [{"text": {"content": str(prospect.get("company_name", ""))}}]},
    "Website": {"url": prospect.get("website")},
    "PipelineStage": {"select": {"name": str(prospect.get("pipeline_stage", "Targeted"))}},
    "PrimaryICP": {"select": {"name": str(prospect.get("primary_icp", "FS+Tech PR/Marketing"))}},
    "Notes": {"rich_text": [{"text": {"content": str(prospect.get("notes") or "")}}]},
    "AppRecordID": {"rich_text": [{"text": {"content": str(prospect.get("prospect_id"))}}]},
  }


def upsert_page(
  *,
  notion_page_id: str | None,
  notion_database_id: str,
  prospect: dict[str, Any],
) -> dict[str, Any]:
  properties = build_notion_properties(prospect)
  with httpx.Client(timeout=30) as client:
    if notion_page_id:
      response = client.patch(
        f"https://api.notion.com/v1/pages/{notion_page_id}",
        headers=_headers(),
        json={"properties": properties},
      )
      response.raise_for_status()
      return response.json()
    response = client.post(
      "https://api.notion.com/v1/pages",
      headers=_headers(),
      json={"parent": {"database_id": notion_database_id}, "properties": properties},
    )
    response.raise_for_status()
    return response.json()

