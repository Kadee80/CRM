from app.storage.db import get_conn


def seed(workspace_id: str, user_id: str, workspace_name: str = "Local Workspace") -> None:
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        insert into workspaces (id, name)
        values (%s, %s)
        on conflict (id) do update set name = excluded.name
        """,
        (workspace_id, workspace_name),
      )
      cur.execute(
        """
        insert into workspace_users (workspace_id, user_id, role)
        values (%s, %s, 'owner')
        on conflict (workspace_id, user_id) do update set role = 'owner'
        """,
        (workspace_id, user_id),
      )
    conn.commit()


if __name__ == "__main__":
  seed(
    workspace_id="11111111-1111-1111-1111-111111111111",
    user_id="22222222-2222-2222-2222-222222222222",
  )
  print("Seeded local workspace/user mapping.")

