from pathlib import Path

from app.storage.db import get_conn


def apply_schema() -> None:
  schema_path = Path(__file__).with_name("schema.sql")
  sql = schema_path.read_text(encoding="utf-8")
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(sql)
    conn.commit()


if __name__ == "__main__":
  apply_schema()
  print("Schema applied successfully.")

