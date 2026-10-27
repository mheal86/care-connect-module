"""Small PostgreSQL adapter for the standalone review application."""
from contextlib import contextmanager
import os
import threading
from psycopg2.pool import ThreadedConnectionPool

_pool = None
_lock = threading.Lock()

@contextmanager
def get_conn():
    global _pool
    with _lock:
        if _pool is None:
            _pool = ThreadedConnectionPool(1, 10, os.environ['DATABASE_URL'])
    conn = _pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)

def init_db():
    from backend.core.db.schema import CREATE_TABLES_SQL
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_TABLES_SQL)
        conn.commit()

def close_pool():
    global _pool
    with _lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None
