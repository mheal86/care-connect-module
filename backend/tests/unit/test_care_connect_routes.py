"""Unit tests for Care Connect FastAPI routes (RBAC, 409 CONFLICT, Idempotency-Key, Feedback)."""

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth import get_current_user_id
from backend.core.errors import CodedHTTPException
from backend.core.features.care_connect.store import DEFAULT_FACILITIES_SEED
from backend.routes import care_connect


class _FakeCareStore:
    def __init__(self):
        self.facilities = list(DEFAULT_FACILITIES_SEED)
        self.members = {("an-nhien", "staff_user"): "manager"}
        self.requests = {}
        self.idem_map = {}

    def get_member_facilities(self, user_id: str):
        out = []
        for (fac_id, uid), role in self.members.items():
            if uid == user_id:
                out.append(
                    {
                        "facility_id": fac_id,
                        "facilityId": fac_id,
                        "member_role": role,
                        "memberRole": role,
                    }
                )
        return out

    def list_facilities(self, type_filter=None, level_filter=None, search=None):
        return self.facilities

    def get_facility(self, facility_id: str):
        return next((f for f in self.facilities if f["id"] == facility_id), None)

    def list_slots(self, facility_id: str, date_str=None, consult_type=None):
        return [
            {
                "id": "slot-1",
                "facility_id": facility_id,
                "consult_type": consult_type or "visit",
                "starts_at": "2026-10-25T09:00:00Z",
                "ends_at": "2026-10-25T10:00:00Z",
                "capacity": 2,
                "booked_count": 0,
                "available": 2,
                "isFull": False,
            }
        ]

    def create_request(self, user_id: str, payload: dict, idempotency_key=None):
        if idempotency_key and (user_id, idempotency_key) in self.idem_map:
            return self.requests[self.idem_map[(user_id, idempotency_key)]], False
        req_id = f"req-{len(self.requests) + 1}"
        doc = {
            "id": req_id,
            "code": f"CC-2026-010{len(self.requests) + 1}",
            "user_id": user_id,
            "facility_id": payload["facility_id"],
            "facilityId": payload["facility_id"],
            "service_id": payload["service_id"],
            "serviceId": payload["service_id"],
            "status": "PENDING",
            "version": 1,
            "events": [],
        }
        self.requests[req_id] = doc
        if idempotency_key:
            self.idem_map[(user_id, idempotency_key)] = req_id
        return doc, True

    def list_requests(self, user_id: str, scope="mine", facility_id=None, status=None):
        if scope == "facility":
            target = facility_id or "an-nhien"
            if (target, user_id) not in self.members:
                raise CodedHTTPException(403, "facility_forbidden", "Not facility staff")
            return [r for r in self.requests.values() if r["facility_id"] == target]
        return [r for r in self.requests.values() if r["user_id"] == user_id]

    def get_request(self, request_id: str, user_id: str):
        req = self.requests.get(request_id)
        if not req:
            raise CodedHTTPException(404, "request_not_found", "Not found")
        if req["user_id"] != user_id and (req["facility_id"], user_id) not in self.members:
            raise CodedHTTPException(403, "request_forbidden", "Forbidden")
        return req

    def apply_action(
        self,
        request_id: str,
        user_id: str,
        action: str,
        expected_version: int,
        note: str = "",
        proposed_slot=None,
        slot_id=None,
    ):
        req = self.requests.get(request_id)
        if not req:
            raise CodedHTTPException(404, "request_not_found", "Not found")
        if action in ("confirm", "propose_slot", "reject", "complete"):
            if (req["facility_id"], user_id) not in self.members:
                raise CodedHTTPException(403, "facility_forbidden", "Staff only")
        if req["version"] != expected_version:
            raise CodedHTTPException(409, "CONFLICT", "Version mismatch")
        req["status"] = "CONFIRMED" if action == "confirm" else req["status"]
        req["version"] += 1
        return req


class TestCareConnectRoutes(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.current_user = "cg_alice"
        self.app.dependency_overrides[get_current_user_id] = lambda: self.current_user
        care_connect.register_routes(self.app)
        self.client = TestClient(self.app)
        self.fake_store = _FakeCareStore()
        self.profile_patch = patch("backend.routes.care_connect.authz.elders_of", return_value=["elder-1"])
        self.profile_patch.start()
        self.addCleanup(self.profile_patch.stop)

    def test_idempotency_key_returns_201_then_200(self):
        payload = {
            "consent": True,
            "profileId": "elder-1",
            "profileName": "Bà Nguyễn Thị Lan",
            "profileAge": 78,
            "careLevel": "L2",
            "facilityId": "an-nhien",
            "serviceId": "an-nhien-stay-30",
            "consultType": "visit",
            "preferredSlot": "2026-11-01T09:00:00Z",
            "contactName": "Người liên hệ mẫu",
            "contactPhone": "0900000000",
        }
        with patch(
            "backend.routes.care_connect.get_care_connect_store",
            return_value=self.fake_store,
        ):
            r1 = self.client.post(
                "/api/care/requests",
                json=payload,
                headers={"Idempotency-Key": "idem-abc-1"},
            )
            self.assertEqual(r1.status_code, 201)
            self.assertTrue(r1.json()["created"])

            r2 = self.client.post(
                "/api/care/requests",
                json=payload,
                headers={"Idempotency-Key": "idem-abc-1"},
            )
            self.assertEqual(r2.status_code, 200)
            self.assertFalse(r2.json()["created"])
            self.assertEqual(r1.json()["request"]["id"], r2.json()["request"]["id"])

    def test_rbac_and_optimistic_version_conflict(self):
        with patch(
            "backend.routes.care_connect.get_care_connect_store",
            return_value=self.fake_store,
        ):
            r_create = self.client.post(
                "/api/care/requests",
                json={
                    "consent": True,
                    "facilityId": "an-nhien",
                    "serviceId": "an-nhien-stay-30",
                    "preferredSlot": "2026-11-01T09:00:00Z",
                    "contactName": "Alice",
                    "contactPhone": "0900000000",
                },
            )
            req_id = r_create.json()["request"]["id"]

            # Caregiver trying to confirm (staff action) -> 403
            r_forbid = self.client.post(
                f"/api/care/requests/{req_id}/actions",
                json={"action": "confirm", "expectedVersion": 1},
            )
            self.assertEqual(r_forbid.status_code, 403)

            # Staff confirms with version 1 -> 200 (version becomes 2)
            self.current_user = "staff_user"
            r_ok = self.client.post(
                f"/api/care/requests/{req_id}/actions",
                json={"action": "confirm", "expectedVersion": 1},
            )
            self.assertEqual(r_ok.status_code, 200)
            self.assertEqual(r_ok.json()["request"]["version"], 2)

            # Staff acts again with stale expectedVersion 1 -> 409 CONFLICT
            r_conflict = self.client.post(
                f"/api/care/requests/{req_id}/actions",
                json={"action": "complete", "expectedVersion": 1},
            )
            self.assertEqual(r_conflict.status_code, 409)
            self.assertEqual(r_conflict.json()["code"], "CONFLICT")


if __name__ == "__main__":
    unittest.main()
