import os
import uuid
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[2]
ADMIN_URL = os.environ.get("TEST_PG_ADMIN_URL", "postgresql://postgres@localhost:5432/postgres")
SQL = [ROOT / "supabase/tests/supabase_stub.sql", *sorted((ROOT / "supabase/migrations").glob("*.sql"))]


@pytest.fixture
def db():
    """테스트마다 새 DB에 Supabase 흉내 + schema.sql 적용."""
    name = "t_" + uuid.uuid4().hex[:12]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"create database {name}")
    url = psycopg.conninfo.make_conninfo(ADMIN_URL, dbname=name)
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            for f in SQL:
                conn.execute(f.read_text())
            yield conn
    finally:
        with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
            admin.execute(f"drop database if exists {name} with (force)")
