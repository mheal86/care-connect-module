"""Standalone review host for the exported Care Connect module, bound to localhost."""
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware
from backend.auth import get_current_user_id
from backend.core.db.connection import close_pool, get_conn, init_db
from backend.core.features.care_connect.store import get_care_connect_store
from backend.core import authz
from backend.routes import care_connect, care_extensions

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

def password_hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 200000).hex()

def seed_demo():
    password = os.environ.get('DEMO_PASSWORD', '')
    if len(password) < 12:
        raise RuntimeError('Set DEMO_PASSWORD to at least 12 characters in your local .env.')
    accounts = [('family_demo', 'Gia đình mẫu', 'caregiver'), ('elder_demo', 'Người cao tuổi mẫu', 'elder'),
                ('staff_demo', 'Nhân viên cơ sở mẫu', 'caregiver'), ('other_demo', 'Gia đình khác', 'caregiver')]
    with get_conn() as conn:
        with conn.cursor() as cursor:
            for username, name, role in accounts:
                salt = secrets.token_hex(16)
                cursor.execute("INSERT INTO users(username,password_hash,salt,display_name,role) VALUES (%s,%s,%s,%s,%s) ON CONFLICT(username) DO UPDATE SET password_hash=EXCLUDED.password_hash, salt=EXCLUDED.salt",
                               (username, password_hash(password, salt), salt, name, role))
            cursor.execute("INSERT INTO user_profile(user_id,data) VALUES (%s,%s::jsonb) ON CONFLICT(user_id) DO NOTHING",
                           ('elder_demo', json.dumps({'supportNeeds': 'Hỗ trợ sinh hoạt mẫu', 'contact': 'Người liên hệ mẫu', 'dailyRoutine': 'Sinh hoạt mẫu'})))
        conn.commit()
    authz.link_pair('family_demo', 'elder_demo')
    get_care_connect_store().seed_all(staff_memberships=[{'facility_id': 'an-nhien', 'user_id': 'staff_demo', 'member_role': 'manager'}])

@asynccontextmanager
async def lifespan(app):
    init_db()
    seed_demo()
    yield
    close_pool()

class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=200)

def create_app() -> FastAPI:
    app = FastAPI(title='Care Connect module review', version='1.0.0', lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=os.environ.get('APP_SECRET_KEY') or secrets.token_hex(32),
                       session_cookie='care_demo_session', same_site='lax', max_age=3600)

    @app.get('/health')
    async def health():
        return {'status': 'ok', 'scope': 'care-connect-module'}

    @app.post('/api/demo/login')
    async def login(payload: LoginPayload, request: Request):
        with get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT password_hash,salt,status FROM users WHERE username=%s', (payload.username,))
                row = cursor.fetchone()
        if not row or row[2] != 'active' or not hmac.compare_digest(password_hash(payload.password, row[1]), row[0]):
            raise HTTPException(401, 'Invalid demo credentials.')
        request.session.clear()
        request.session['user_id'] = payload.username
        return {'username': payload.username}

    @app.post('/api/demo/logout')
    async def logout(request: Request):
        request.session.clear()
        return {'ok': True}

    @app.get('/api/demo/me')
    async def me(user_id: str = Depends(get_current_user_id)):
        return {'username': user_id}

    care_connect.register_routes(app)
    care_extensions.register_routes(app)
    return app

app = create_app()
