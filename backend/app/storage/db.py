from contextlib import contextmanager
from typing import Iterator

import psycopg

from app.config import get_required_env


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
  database_url = get_required_env("DATABASE_URL")
  with psycopg.connect(database_url, autocommit=False) as conn:
    yield conn

