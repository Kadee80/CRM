from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from app.storage.db import get_conn


def fetch_next_scrape_run() -> dict[str, Any] | None:
  with get_conn() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
      cur.execute(
        """
        select id, workspace_id, source_name
        from scrape_runs
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
        update scrape_runs
        set status = 'running',
            started_at = now()
        where id = %s
        """,
        (row["id"],),
      )
    conn.commit()
  return dict(row)


def mark_scrape_run_failed(run_id: str, error: str) -> None:
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        update scrape_runs
        set status = 'failed',
            finished_at = now(),
            error_message = %s
        where id = %s::uuid
        """,
        (error[:2000], run_id),
      )
    conn.commit()
