from __future__ import annotations

from psycopg.rows import dict_row

from app.scrape.config import get_source_config
from app.scrape.extractors.pr_newswire import extract_news_release_items
from app.scrape.http_fetch import fetch_html_with_fallback
from app.scrape.prospect_upsert import upsert_prospect_from_source_item
from app.storage.db import get_conn


def execute_scrape_run(run_id: str) -> None:
  with get_conn() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
      cur.execute(
        """
        select id, workspace_id, source_name, status
        from scrape_runs
        where id = %s::uuid
        limit 1
        """,
        (run_id,),
      )
      run = cur.fetchone()
      if not run:
        raise RuntimeError(f"scrape_run not found: {run_id}")
      if run["status"] not in {"queued", "running"}:
        return

    try:
      cfg = get_source_config(str(run["source_name"]))
    except KeyError as exc:
      raise RuntimeError(f"Unknown source: {run['source_name']}") from exc

    extractor = str(cfg.get("extractor", ""))
    seed_urls = cfg.get("seed_urls") or []
    crawl_budget = cfg.get("crawl_budget") or {}
    max_items = int(crawl_budget.get("max_pages_per_run", 25))

    if not seed_urls:
      raise RuntimeError("source config missing seed_urls")

    workspace_id = str(run["workspace_id"])
    source_name = str(run["source_name"])
    seed_url = str(seed_urls[0])

    if extractor != "prnewswire_feed":
      raise RuntimeError(f"extractor not implemented: {extractor}")

    html, _ = fetch_html_with_fallback(seed_url)
    items = extract_news_release_items(html, seed_url, max_items=max_items)
    deduped = list({item["url"]: item for item in items}.values())
    pages_fetched = 1

    for item in deduped:
      upsert_prospect_from_source_item(
        conn,
        workspace_id=workspace_id,
        user_id=None,
        source_name=source_name,
        url=item["url"],
        title=item["title"],
      )

    with conn.cursor() as cur:
      cur.execute(
        """
        update scrape_runs
        set status = 'succeeded',
            pages_fetched = %s,
            records_emitted = %s,
            finished_at = now(),
            error_message = null
        where id = %s::uuid
        """,
        (pages_fetched, len(deduped), str(run["id"])),
      )
    conn.commit()
