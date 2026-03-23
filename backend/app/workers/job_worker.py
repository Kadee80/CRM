import os
import time

from app.jobs.notion_sync import (
  apply_allowlisted_fields_from_notion,
  fetch_next_job,
  mark_job_failed,
  mark_job_succeeded,
  process_to_notion,
)


def main() -> None:
  poll_seconds = int(os.getenv("JOB_WORKER_POLL_SECONDS", "10"))
  print("job worker started")
  while True:
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
