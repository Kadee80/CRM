from pathlib import Path
from typing import Any

import yaml


def _sources_config_path() -> Path:
  """
  Resolve `sources.yaml` for both layouts:
  - Monorepo: `<repo>/scraper-config/sources.yaml` (local dev)
  - Container: `<backend_root>/scraper-config/sources.yaml` (Docker COPY)
  """
  here = Path(__file__).resolve()
  candidates = [
    here.parents[3] / "scraper-config" / "sources.yaml",
    here.parents[2] / "scraper-config" / "sources.yaml",
  ]
  for candidate in candidates:
    if candidate.exists():
      return candidate
  raise FileNotFoundError(f"sources.yaml not found. Tried: {', '.join(str(p) for p in candidates)}")


def load_sources_config() -> dict[str, Any]:
  path = _sources_config_path()
  return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def get_source_config(source_id: str) -> dict[str, Any]:
  data = load_sources_config()
  for src in data.get("sources", []):
    if src.get("id") == source_id:
      merged = dict(data.get("defaults", {}))
      merged.update(src)
      return merged
  raise KeyError(f"Unknown source: {source_id}")
