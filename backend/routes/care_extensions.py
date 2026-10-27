"""Local-test SOS, consented profile sharing and non-clinical interaction summaries."""
from __future__ import annotations
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
import psycopg2.extras
from fastapi import Depends
from pydantic import BaseModel, Field
from backend.auth import get_current_user_id
from backend.core import authz
from backend.core.db.connection import get_conn
from backend.core.errors import CodedHTTPException
from backend.core.features.care_connect.store import get_care_connect_store

class TrialAlertPayload(BaseModel):
    profileId: str = Field(min_length=1, max_length=255)
    clientEventId: str = Field(min_length=8, max_length=128)
    source: Literal['manual', 'simulator']
    note: str = Field(min_length=5, max_length=1000)

class ProfileGrantPayload(BaseModel):
    profileId: str = Field(min_length=1, max_length=255)
    facilityId: str = Field(min_length=1, max_length=64)
    fields: list[Literal['supportNeeds', 'contact', 'dailyRoutine']] = Field(min_length=1, max_length=3)
    consent: bool = False
    days: int = Field(default=7, ge=1, le=90)


def profile_ids(user_id: str) -> list[str]:
    """List only the caller and explicitly linked elder accounts."""
    linked = authz.elders_of(user_id)
    if linked:
        return list(dict.fromkeys(linked))
    if _query('SELECT 1 FROM care_facility_members WHERE user_id=%s LIMIT 1', (user_id,)):
        return []
    return [user_id]


def _query(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = [dict(row) for row in cur.fetchall()] if cur.description else []
        conn.commit()
    return rows


def _overview(user_id: str) -> dict:
    ids = profile_ids(user_id)
    profiles = _query('SELECT username AS id, COALESCE(display_name, username) AS name FROM users WHERE username = ANY(%s) ORDER BY username', (ids,))
    alerts = _query('SELECT * FROM care_trial_alerts WHERE profile_id = ANY(%s) ORDER BY created_at DESC LIMIT 30', (ids,))
    grants = _query('SELECT g.*, COALESCE(u.display_name, g.profile_id) AS profile_name FROM care_profile_grants g LEFT JOIN users u ON u.username=g.profile_id WHERE g.owner_id=%s OR g.facility_id IN (SELECT facility_id FROM care_facility_members WHERE user_id=%s) ORDER BY g.created_at DESC LIMIT 30', (user_id, user_id))
    accesses = _query('SELECT l.* FROM care_profile_access_log l JOIN care_profile_grants g ON g.id=l.grant_id WHERE g.owner_id=%s ORDER BY l.at DESC LIMIT 20', (user_id,))
    games = []  # Chess is outside this public module snapshot.
    return {'profiles': profiles, 'alerts': alerts, 'grants': grants, 'accesses': accesses, 'games': games, 'userId': user_id, 'caregiver': authz.get_role(user_id) == authz.ROLE_CAREGIVER}


def _create_alert(user_id: str, payload: TrialAlertPayload) -> dict:
    if payload.profileId not in profile_ids(user_id):
        raise CodedHTTPException(403, 'profile_forbidden', 'Profile is not linked to this account.')
    rows = _query('''INSERT INTO care_trial_alerts (id,profile_id,created_by,client_event_id,source,note)
        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(created_by,client_event_id) DO UPDATE SET client_event_id=EXCLUDED.client_event_id RETURNING *''',
        ('sos-'+uuid.uuid4().hex[:12],payload.profileId,user_id,payload.clientEventId,payload.source,payload.note.strip()))
    row = rows[0]
    if row['profile_id'] != payload.profileId or row['source'] != payload.source or row['note'] != payload.note.strip():
        raise CodedHTTPException(409,'IDEMPOTENCY','Event ID was used with different content.')
    return row


def _act_alert(alert_id: str, user_id: str, action: str) -> dict:
    rows = _query('SELECT * FROM care_trial_alerts WHERE id=%s', (alert_id,))
    if not rows: raise CodedHTTPException(404,'NOT_FOUND','Alert not found.')
    alert=rows[0]
    if action == 'acknowledge':
        if authz.get_role(user_id) != authz.ROLE_CAREGIVER or alert['profile_id'] not in profile_ids(user_id):
            raise CodedHTTPException(403,'FORBIDDEN','Only a linked caregiver may acknowledge.')
        status='ACKNOWLEDGED'
    else:
        if alert['created_by'] != user_id: raise CodedHTTPException(403,'FORBIDDEN','Only the sender may cancel.')
        status='CANCELLED'
    updated=_query("UPDATE care_trial_alerts SET status=%s,acknowledged_by=%s,updated_at=NOW() WHERE id=%s AND status='NEW' RETURNING *", (status,user_id,alert_id))
    if not updated: raise CodedHTTPException(409,'CONFLICT','This alert has already been handled.')
    return updated[0]


def _create_grant(user_id: str, payload: ProfileGrantPayload) -> dict:
    if not payload.consent: raise CodedHTTPException(422,'CONSENT','Explicit consent is required.')
    if payload.profileId not in profile_ids(user_id): raise CodedHTTPException(403,'FORBIDDEN','Profile is not linked.')
    facility=get_care_connect_store().get_facility(payload.facilityId)
    if not facility or not facility.get('published',True): raise CodedHTTPException(404,'FACILITY','Facility is not published.')
    return _query('INSERT INTO care_profile_grants (id,profile_id,owner_id,facility_id,fields,expires_at) VALUES (%s,%s,%s,%s,%s::jsonb,%s) RETURNING *', ('grant-'+uuid.uuid4().hex[:12],payload.profileId,user_id,payload.facilityId,json.dumps(list(dict.fromkeys(payload.fields))),datetime.now(timezone.utc)+timedelta(days=payload.days)))[0]


def _revoke_grant(grant_id: str, user_id: str) -> dict:
    rows=_query('UPDATE care_profile_grants SET revoked_at=COALESCE(revoked_at,NOW()) WHERE id=%s AND owner_id=%s RETURNING *',(grant_id,user_id))
    if not rows: raise CodedHTTPException(403,'FORBIDDEN','Only the owner may revoke access.')
    _query("INSERT INTO care_profile_access_log(grant_id,actor_id,action) VALUES (%s,%s,'revoke')",(grant_id,user_id))
    return rows[0]


def _read_shared(grant_id: str, user_id: str) -> dict:
    # Lock the grant until the read and audit commit, so revocation cannot race a read.
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM care_profile_grants WHERE id=%s AND revoked_at IS NULL AND expires_at>NOW() FOR SHARE',(grant_id,))
            grant=cur.fetchone()
            if not grant: raise CodedHTTPException(403,'REVOKED','Permission expired or was revoked.')
            cur.execute('SELECT 1 FROM care_facility_members WHERE user_id=%s AND facility_id=%s',(user_id,grant['facility_id']))
            if not cur.fetchone(): raise CodedHTTPException(403,'FORBIDDEN','Not a member of the receiving facility.')
            cur.execute('SELECT data,updated_at FROM user_profile WHERE user_id=%s',(grant['profile_id'],))
            profile=cur.fetchone()
            data=profile['data'] if profile else {}
            selected={field:data.get(field,'') for field in grant['fields']}
            cur.execute("INSERT INTO care_profile_access_log(grant_id,actor_id,action) VALUES (%s,%s,'read')",(grant_id,user_id))
        conn.commit()
    return {'profileId':grant['profile_id'],'fields':selected,'source':'family-provided','updatedAt':profile['updated_at'] if profile else None,'expiresAt':grant['expires_at']}


def register_routes(app, **_kwargs) -> None:
    """Register optional extension software; no external emergency service is contacted."""
    @app.get('/api/care/extensions')
    async def overview(user_id: str=Depends(get_current_user_id)):
        return await asyncio.to_thread(_overview,user_id)
    @app.post('/api/care/trial-alerts',status_code=201)
    async def create_alert(payload: TrialAlertPayload,user_id: str=Depends(get_current_user_id)):
        return await asyncio.to_thread(_create_alert,user_id,payload)
    @app.post('/api/care/trial-alerts/{alert_id}/{action}')
    async def act_alert(alert_id: str,action: Literal['acknowledge','cancel'],user_id: str=Depends(get_current_user_id)):
        return await asyncio.to_thread(_act_alert,alert_id,user_id,action)
    @app.post('/api/care/profile-grants',status_code=201)
    async def grant(payload: ProfileGrantPayload,user_id: str=Depends(get_current_user_id)):
        return await asyncio.to_thread(_create_grant,user_id,payload)
    @app.post('/api/care/profile-grants/{grant_id}/revoke')
    async def revoke(grant_id: str,user_id: str=Depends(get_current_user_id)):
        return await asyncio.to_thread(_revoke_grant,grant_id,user_id)
    @app.get('/api/care/profile-grants/{grant_id}/shared-profile')
    async def shared(grant_id: str,user_id: str=Depends(get_current_user_id)):
        return await asyncio.to_thread(_read_shared,grant_id,user_id)
