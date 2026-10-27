"""PostgreSQL integration tests for Care Connect store (`@pytest.mark.postgres`)."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.tests import db_support

_SKIP = db_support.skip_reason()
if _SKIP:
    pytest.skip(_SKIP, allow_module_level=True)

db_support.activate()

pytestmark = pytest.mark.postgres

from backend.core import authz  # noqa: E402
from backend.core.errors import CodedHTTPException  # noqa: E402
from backend.core.features.care_connect.store import (  # noqa: E402
    get_care_connect_store,
    reset_care_connect_store,
)


@pytest.fixture(autouse=True)
def _clean():
    db_support.truncate_all(include_users=True)
    db_support.seed_users("cg_alice", "cg_bob", role=authz.ROLE_CAREGIVER)
    db_support.seed_users("staff_an", role=authz.ROLE_CAREGIVER)
    reset_care_connect_store()
    store = get_care_connect_store()
    store.seed_all(
        staff_memberships=[
            {"facility_id": "an-nhien", "user_id": "staff_an", "member_role": "manager"}
        ]
    )
    yield
    reset_care_connect_store()


def test_create_idempotent_and_transition_conflict():
    store = get_care_connect_store()
    future_slot = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    payload = {
        "profile_id": "elder-1",
        "profile_name": "Elder One",
        "profile_age": 78,
        "care_level": "L2",
        "facility_id": "an-nhien",
        "service_id": "an-nhien-stay-30",
        "consult_type": "visit",
        "preferred_slot": future_slot,
        "contact_name": "Alice",
        "contact_phone": "0900000000",
    }

    req1, created1 = store.create_request("cg_alice", payload, idempotency_key="k1")
    req2, created2 = store.create_request("cg_alice", payload, idempotency_key="k1")
    assert created1 is True
    assert created2 is False
    assert req1["id"] == req2["id"]

    # Non-staff cannot confirm
    with pytest.raises(CodedHTTPException) as exc_forbid:
        store.apply_action(req1["id"], "cg_bob", "confirm", expected_version=1)
    assert exc_forbid.value.status_code == 403

    # Staff confirms -> version increments to 2
    confirmed = store.apply_action(req1["id"], "staff_an", "confirm", expected_version=1)
    assert confirmed["status"] == "CONFIRMED"
    assert confirmed["version"] == 2

    # Stale expected_version=1 raises 409 CONFLICT
    with pytest.raises(CodedHTTPException) as exc_conflict:
        store.apply_action(req1["id"], "staff_an", "complete", expected_version=1)
    assert (exc_conflict.value.status_code, exc_conflict.value.code) == (409, "CONFLICT")


def _payload(**changes):
    return {"profile_id": "elder-1", "profile_name": "Elder One", "profile_age": 78,
            "care_level": "L2", "facility_id": "an-nhien", "service_id": "an-nhien-stay-30",
            "consult_type": "visit", "preferred_slot": (datetime.now(timezone.utc)+timedelta(days=3)).isoformat(),
            "contact_name": "Alice", "contact_phone": "0900000000", **changes}


def test_two_concurrent_creates_with_same_key_return_one_request():
    from concurrent.futures import ThreadPoolExecutor
    import threading
    store=get_care_connect_store()
    payload=_payload()
    barrier=threading.Barrier(2)
    def submit():
        barrier.wait()
        return store.create_request("cg_alice",payload,idempotency_key="parallel-same-key")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _i: submit(),range(2)))
    assert results[0][0]["id"] == results[1][0]["id"]
    assert sum(created for _request,created in results) == 1


def test_same_idempotency_key_with_changed_content_is_rejected():
    store=get_care_connect_store()
    payload=_payload()
    store.create_request("cg_alice",payload,idempotency_key="content-key")
    with pytest.raises(CodedHTTPException) as exc:
        store.create_request("cg_alice",{**payload,"contact_name":"Changed"},idempotency_key="content-key")
    assert (exc.value.status_code,exc.value.code) == (409,"IDEMPOTENCY")


def test_two_staff_actions_on_same_version_have_one_winner():
    from concurrent.futures import ThreadPoolExecutor
    import threading
    store=get_care_connect_store()
    request,_=store.create_request("cg_alice",_payload())
    barrier=threading.Barrier(2)
    def review():
        barrier.wait()
        try:
            return store.apply_action(request["id"],"staff_an","start_review",expected_version=1)["status"]
        except CodedHTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _i: review(),range(2)))
    assert sorted(str(result) for result in results) == ["409","IN_REVIEW"]


def test_capacity_and_opted_in_reminder_follow_confirmation_and_cancellation():
    from backend.core.db.connection import get_conn
    store=get_care_connect_store()
    slot=store.list_slots("an-nhien")[0]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE care_consult_slots SET capacity=1 WHERE id=%s",(slot["id"],))
        conn.commit()
    payload=_payload(preferred_slot=slot["startsAt"],slot_id=slot["id"],reminder_opt_in=True)
    first,_=store.create_request("cg_alice",payload)
    second,_=store.create_request("cg_bob",payload)
    confirmed=store.apply_action(first["id"],"staff_an","confirm",expected_version=1)
    assert confirmed["reminderId"]
    with pytest.raises(CodedHTTPException) as exc:
        store.apply_action(second["id"],"staff_an","confirm",expected_version=1)
    assert exc.value.code == "SLOT_FULL"
    cancelled=store.apply_action(first["id"],"cg_alice","cancel",expected_version=2,note="Family changed its plan")
    assert cancelled["reminderId"] is None
    assert store.list_slots("an-nhien")[0]["bookedCount"] == 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM one_time_reminders WHERE id=%s",(confirmed["reminderId"],))
            assert cur.fetchone()[0] == 0


def test_manager_catalogue_changes_persist_and_cannot_be_written_by_family():
    store=get_care_connect_store()
    payload={"name":"Test care facility","facility_type":"nursing_home","region":"hcm","address":"An illustrative address","description":"Family consultation and daily support", "phone":"0900000000","published":False,"amenities":["accessible"],"services":[{"id":"ignored","name":"Daily care","category":"day","ui_id":"daycare","price":350000,"price_unit":"day","accepting":False}]}
    with pytest.raises(CodedHTTPException) as exc:
        store.save_facility("an-nhien","cg_alice",payload)
    assert exc.value.status_code == 403
    store.save_facility("an-nhien","staff_an",payload)
    result=store.get_facility("an-nhien")
    assert result["published"] is False
    assert result["services"][0]["accepting"] is False
    assert result["services"][0]["price"] == 350000


def test_profile_access_is_limited_to_selected_fields_and_stops_after_revocation():
    import json
    from backend.routes.care_extensions import ProfileGrantPayload, _create_grant, _read_shared, _revoke_grant
    from backend.core.db.connection import get_conn
    db_support.seed_users("elder-1",role=authz.ROLE_ELDER)
    authz.link_pair("cg_alice","elder-1")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO user_profile(user_id,data) VALUES (%s,%s::jsonb)",("elder-1",json.dumps({"supportNeeds":"Daily assistance","contact":"Private contact"})))
        conn.commit()
    grant=_create_grant("cg_alice",ProfileGrantPayload(profileId="elder-1",facilityId="an-nhien",fields=["supportNeeds"],consent=True))
    assert _read_shared(grant["id"],"staff_an")["fields"] == {"supportNeeds":"Daily assistance"}
    with pytest.raises(CodedHTTPException): _read_shared(grant["id"],"cg_bob")
    _revoke_grant(grant["id"],"cg_alice")
    with pytest.raises(CodedHTTPException) as exc: _read_shared(grant["id"],"staff_an")
    assert exc.value.status_code == 403


def test_trial_sos_is_idempotent_and_only_linked_caregiver_can_acknowledge():
    from backend.routes.care_extensions import TrialAlertPayload, _create_alert, _act_alert
    db_support.seed_users("elder-1",role=authz.ROLE_ELDER)
    authz.link_pair("cg_alice","elder-1")
    payload=TrialAlertPayload(profileId="elder-1",clientEventId="event-test-123",source="simulator",note="Please contact the family")
    alert=_create_alert("cg_alice",payload)
    assert _create_alert("cg_alice",payload)["id"] == alert["id"]
    with pytest.raises(CodedHTTPException): _act_alert(alert["id"],"cg_bob","acknowledge")
    assert _act_alert(alert["id"],"cg_alice","acknowledge")["status"] == "ACKNOWLEDGED"
