"""Demo identity adapter. The original company's authentication is not exported."""
from fastapi import HTTPException, Request
from backend.core.db.connection import get_conn

def get_current_user_id(request: Request) -> str:
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(401, 'Sign in to the local demo first.')
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1 FROM users WHERE username=%s AND status=%s', (user_id, 'active'))
            if not cursor.fetchone():
                raise HTTPException(401, 'Account is unavailable.')
    return user_id
