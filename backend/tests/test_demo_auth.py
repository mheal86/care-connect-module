"""Regression coverage for the local demo's configured credentials and sessions."""
import pytest
from backend.tests import db_support

_SKIP = db_support.skip_reason()
if _SKIP:
    pytest.skip(_SKIP, allow_module_level=True)
pytestmark = pytest.mark.postgres

@pytest.fixture(autouse=True)
def clean_demo_database():
    db_support.activate()
    db_support.truncate_all(include_users=True)
    from backend.core.features.care_connect.store import reset_care_connect_store
    reset_care_connect_store()
    yield
    reset_care_connect_store()

def test_configured_password_and_session_logout(monkeypatch):
    from backend.app import create_app
    from fastapi.testclient import TestClient
    password='demo-auth-regression-password'
    monkeypatch.setenv('DEMO_PASSWORD',password)
    with TestClient(create_app()) as client:
        assert client.get('/api/demo/me').status_code == 401
        assert client.post('/api/demo/login',json={'username':'family_demo','password':'DEMO_PASSWORD'}).status_code == 401
        assert client.post('/api/demo/login',json={'username':'family_demo','password':password}).status_code == 200
        assert client.get('/api/care/me').json()['username'] == 'family_demo'
        assert client.post('/api/demo/logout').status_code == 200
        assert client.get('/api/care/me').status_code == 401

def test_changed_demo_password_applies_after_backend_restart(monkeypatch):
    from backend.app import create_app
    from fastapi.testclient import TestClient
    monkeypatch.setenv('DEMO_PASSWORD','old-demo-password-2026')
    with TestClient(create_app()) as client:
        assert client.post('/api/demo/login',json={'username':'staff_demo','password':'old-demo-password-2026'}).status_code == 200
    monkeypatch.setenv('DEMO_PASSWORD','new-demo-password-2026')
    with TestClient(create_app()) as client:
        assert client.post('/api/demo/login',json={'username':'staff_demo','password':'old-demo-password-2026'}).status_code == 401
        assert client.post('/api/demo/login',json={'username':'staff_demo','password':'new-demo-password-2026'}).status_code == 200
