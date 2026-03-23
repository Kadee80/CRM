import os


def get_env(name: str, default: str | None = None) -> str | None:
  value = os.getenv(name, default)
  return value


def get_required_env(name: str) -> str:
  value = os.getenv(name)
  if not value:
    raise RuntimeError(f"Missing required environment variable: {name}")
  return value

