from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException
from jwt import InvalidTokenError, PyJWKClient
from psycopg.rows import dict_row

from app.config import get_required_env
from app.storage.db import get_conn


@dataclass
class RequestContext:
  user_id: str
  workspace_id: str
  role: str


@lru_cache(maxsize=1)
def _get_jwk_client() -> PyJWKClient:
  return PyJWKClient(get_required_env("SUPABASE_JWKS_URL"))


def _decode_access_token(token: str) -> dict:
  try:
    signing_key = _get_jwk_client().get_signing_key_from_jwt(token).key
    return jwt.decode(
      token,
      signing_key,
      algorithms=["RS256"],
      audience=get_required_env("SUPABASE_JWT_AUDIENCE"),
      issuer=get_required_env("SUPABASE_JWT_ISSUER"),
    )
  except InvalidTokenError as exc:
    raise HTTPException(status_code=401, detail=f"Invalid access token: {exc}") from exc


def require_context(
  authorization: str | None = Header(default=None),
  x_workspace_id: str | None = Header(default=None),
) -> RequestContext:
  if _local_bypass_enabled():
    if not x_workspace_id:
      raise HTTPException(status_code=400, detail="Missing X-Workspace-Id header")
    return RequestContext(
      user_id="22222222-2222-2222-2222-222222222222",
      workspace_id=x_workspace_id,
      role="owner",
    )

  if not authorization or not authorization.lower().startswith("bearer "):
    raise HTTPException(status_code=401, detail="Missing bearer token")
  if not x_workspace_id:
    raise HTTPException(status_code=400, detail="Missing X-Workspace-Id header")

  token = authorization.split(" ", 1)[1].strip()
  claims = _decode_access_token(token)
  user_id = str(claims.get("sub", ""))
  if not user_id:
    raise HTTPException(status_code=401, detail="Token missing sub claim")

  with get_conn() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
      cur.execute(
        """
        select role
        from workspace_users
        where workspace_id = %s and user_id = %s
        """,
        (x_workspace_id, user_id),
      )
      row = cur.fetchone()
  if not row:
    raise HTTPException(status_code=403, detail="No access to requested workspace")

  return RequestContext(user_id=user_id, workspace_id=x_workspace_id, role=str(row["role"]))


def _local_bypass_enabled() -> bool:
  # Local development escape hatch; never enable in production.
  try:
    value = get_required_env("LOCAL_AUTH_BYPASS")
  except RuntimeError:
    return False
  return value.lower() in {"1", "true", "yes", "on"}

