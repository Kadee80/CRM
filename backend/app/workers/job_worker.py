import os
import time

from app.jobs.notion_sync import (
  apply_allowlisted_fields_from_notion,
  fetch_next_job,
  mark_job_failed,
  mark_job_succeeded,
  process_to_notion,
)
from app.jobs.scrape_runs import fetch_next_scrape_run, mark_scrape_run_failed
from app.scrape.runner import execute_scrape_run


def main() -> None:
  poll_seconds = int(os.getenv("JOB_WORKER_POLL_SECONDS", "10"))
  print("job worker started")
  while True:
    scrape = fetch_next_scrape_run()
    if scrape:
      try:
        execute_scrape_run(str(scrape["id"]))
        print(f"scrape run succeeded: {scrape['id']}")
      except Exception as exc:  # pragma: no cover
        mark_scrape_run_failed(str(scrape["id"]), str(exc))
        print(f"scrape run failed: {scrape['id']} error={exc}")
      time.sleep(0.2)
      continue

    job = fetch_next_job()
    if not job:
      print("job worker idle")
      time.sleep(poll_seconds)
      continue
    try:
      if job["direction"] == "from_notion":
        apply_allowlisted_fields_from_notion(job)
      elif job["direction"] == "to_notion":
        process_to_notion(job)
      mark_job_succeeded(str(job["id"]))
      print(f"job succeeded: {job['id']}")
    except Exception as exc:  # pragma: no cover
      mark_job_failed(
        str(job["id"]),
        int(job["attempt_count"]),
        int(job["max_attempts"]),
        str(exc),
      )
      print(f"job failed: {job['id']} error={exc}")
    time.sleep(poll_seconds)


if __name__ == "__main__":
  main()
