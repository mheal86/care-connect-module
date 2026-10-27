"""Scratch PostgreSQL test database support (`TEST_DATABASE_URL`).

Never connects to `DATABASE_URL` directly: only `TEST_DATABASE_URL` opts a test run into
the PostgreSQL tier, and the database name must end with `_test` or `test` to prevent
accidental truncation of a developer or production database.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
from urllib.parse import urlparse

_ORIGINAL_DB_URL: Optional[str] = None
_ACTIVATED = False


def _test_url() -> str:
    return (os.getenv("TEST_DATABASE_URL") or "").strip()


def skip_reason() -> Optional[str]:
    """Return a skip reason string if `TEST_DATABASE_URL` is unset, unsafe, or unreachable."""
    url = _test_url()
    if not url:
        return "TEST_DATABASE_URL is not set (skipping @pytest.mark.postgres tier)"
    parsed = urlparse(url)
    dbname = (parsed.path or "").lstrip("/")
    if not dbname or not (dbname.endswith("_test") or dbname.endswith("test")):
        return (
            f"Refusing to run destructive Postgres tests against database {dbname!r}; "
            "TEST_DATABASE_URL database name must end with '_test' or 'test'."
        )
    try:
        import psycopg2

        conn = psycopg2.connect(url, connect_timeout=3)
        conn.close()
    except Exception as e:
        return f"TEST_DATABASE_URL is unreachable: {e}"
    return None


def activate() -> None:
    """Point `DATABASE_URL` at `TEST_DATABASE_URL` and initialize schema."""
    global _ORIGINAL_DB_URL, _ACTIVATED
    reason = skip_reason()
    if reason:
        raise RuntimeError(reason)
    if not _ACTIVATED:
        _ORIGINAL_DB_URL = os.environ.get("DATABASE_URL")
        _ACTIVATED = True
    os.environ["DATABASE_URL"] = _test_url()
    from backend.core.db import connection

    connection.close_pool()
    connection.init_db()


def deactivate() -> None:
    """Restore the original `DATABASE_URL` and close the test pool."""
    global _ACTIVATED
    if not _ACTIVATED:
        return
    from backend.core.db import connection

    connection.close_pool()
    if _ORIGINAL_DB_URL is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = _ORIGINAL_DB_URL
    _ACTIVATED = False


def truncate_all(include_users: bool = False) -> None:
    """Truncate application tables in the scratch database."""
    from backend.core.db.connection import get_conn

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tablename
                  FROM pg_tables
                 WHERE schemaname = 'public'
                """
            )
            tables = [r[0] for r in cur.fetchall()]
            if not include_users:
                tables = [t for t in tables if t != "users"]
            if tables:
                quoted = ", ".join(f'"{t}"' for t in tables)
                cur.execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
            if include_users and "users" in tables:
                cur.execute(
                    """
                    INSERT INTO users (username, password_hash, salt, display_name)
                    VALUES ('default', '', '', 'Default')
                    ON CONFLICT (username) DO NOTHING
                    """
                )
        conn.commit()


def seed_users(*usernames: str, role: str = "elder") -> None:
    """Insert active test accounts with the given `role`."""
    from backend.core.db.connection import get_conn

    with get_conn() as conn:
        with conn.cursor() as cur:
            for uname in usernames:
                cur.execute(
                    """
                    INSERT INTO users (username, password_hash, salt, display_name, role, status)
                    VALUES (%s, 'testhash', 'testsalt', %s, %s, 'active')
                    ON CONFLICT (username) DO UPDATE SET
                        role = EXCLUDED.role,
                        status = 'active'
                    """,
                    (uname, uname.capitalize(), role),
                )
        conn.commit()
