"""Minimal account and family relationship adapter for the public demo."""
from backend.core.db.connection import get_conn
ROLE_CAREGIVER = 'caregiver'
ROLE_ELDER = 'elder'

def get_role(user_id):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT role FROM users WHERE username=%s AND status=%s', (user_id, 'active'))
            row = cursor.fetchone()
    return row[0] if row else ROLE_ELDER

def elders_of(user_id):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT elder_id FROM user_relative WHERE caregiver_id=%s ORDER BY elder_id', (user_id,))
            return [row[0] for row in cursor.fetchall()]

def link_pair(caregiver_id, elder_id):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute('INSERT INTO user_relative(caregiver_id,elder_id) VALUES (%s,%s) ON CONFLICT DO NOTHING', (caregiver_id, elder_id))
        conn.commit()
