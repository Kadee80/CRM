from datetime import datetime, timezone

from fastapi import APIRouter


router = APIRouter()


@router.get("")
def get_health() -> dict:
  return {"ok": True, "timestamp": datetime.now(timezone.utc).isoformat()}

