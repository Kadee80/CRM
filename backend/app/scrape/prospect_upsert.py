from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

from psycopg import Connection
from psycopg.rows import dict_row


def _canonical_domain(url: str) -> str:
  netloc = urlparse(url).netloc.lower()
  if netloc.startswith("www."):
    netloc = netloc[4:]
  return netloc


def upsert_prospect_from_source_item(
  conn: Connection,
  *,
  workspace_id: str,
  user_id: Optional[str],
  source_name: str,
  url: str,
  title: str,
) -> str:
  """
  Insert a source record, then upsert a prospect keyed by canonical domain within the workspace.
  Returns prospect_id.
  """
  domain = _canonical_domain(url)
  company_name = (title or "").strip() or domain
  if len(company_name) > 200:
    company_name = company_name[:200]

  raw_payload: dict[str, Any] = {
    "title": title,
    "url": url,
    "source": source_name,
  }

  with conn.cursor(row_factory=dict_row) as cur:
    cur.execute(
      """
      select prospect_id
      from prospect_identities
      where workspace_id = %s
        and identity_type = 'canonical_domain'
        and identity_value = %s
      limit 1
      """,
      (workspace_id, domain),
    )
    row = cur.fetchone()
    if row:
      prospect_id = str(row["prospect_id"])
      cur.execute(
        """
        insert into source_records (workspace_id, source_name, source_url, raw_payload)
        values (%s, %s, %s, %s::jsonb)
        """,
        (workspace_id, source_name, url, raw_payload),
      )
      return prospect_id

    cur.execute(
      """
      insert into prospects (
        workspace_id, company_name, website, canonical_domain,
        created_by_user_id, updated_by_user_id
      )
      values (%s::uuid, %s, %s, %s, %s, %s)
      returning id
      """,
      (workspace_id, company_name, url, domain, user_id, user_id),
    )
    prospect_id = str(cur.fetchone()["id"])

    cur.execute(
      """
      insert into prospect_identities (prospect_id, workspace_id, identity_type, identity_value)
      values (%s::uuid, %s::uuid, 'canonical_domain', %s)
      """,
      (prospect_id, workspace_id, domain),
    )

    cur.execute(
      """
      insert into scores (prospect_id, workspace_id, fit_score, intent_score, total_score)
      values (%s::uuid, %s::uuid, 0, 0, 0)
      """,
      (prospect_id, workspace_id),
    )

    cur.execute(
      """
      insert into source_records (workspace_id, source_name, source_url, raw_payload)
      values (%s, %s, %s, %s::jsonb)
      """,
      (workspace_id, source_name, url, raw_payload),
    )

  return prospect_id
