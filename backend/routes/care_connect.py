"""FastAPI routes for Care Connect (P1 Full Stack + P4 Recommendations, Slots, Feedback)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from fastapi import Depends, Header, Query, Response

from backend.auth import get_current_user_id
from backend.core import authz
from backend.core.errors import CodedHTTPException, install_error_handlers
from backend.core.features.care_connect.recommend import (
    RECOMMEND_RULES_VERSION,
    rank_facilities,
)
from backend.core.features.care_connect.store import get_care_connect_store
from backend.routes.schemas.care_connect import (
    CareFeedbackModerationPayload,
    CareCatalogPayload,
    CareFeedbackPayload,
    CareMeResponse,
    CareRecommendRequestPayload,
    CareRequestActionPayload,
    CreateCareRequestPayload,
)

TAG = "Care Connect"


def register_routes(
    app,
    curr_dir: Optional[Path] = None,
    tts_model=None,
    user_docs: Optional[dict] = None,
    user_profile: Optional[dict] = None,
) -> None:
    install_error_handlers(app)

    @app.get("/api/care/me", response_model=CareMeResponse, tags=[TAG])
    async def get_care_me(user_id: str = Depends(get_current_user_id)):
        role = await asyncio.to_thread(authz.get_role, user_id)
        store = get_care_connect_store()
        memberships = await asyncio.to_thread(store.get_member_facilities, user_id)
        from backend.routes.care_extensions import _query, profile_ids
        profiles = await asyncio.to_thread(_query, "SELECT username AS id, COALESCE(display_name, username) AS name FROM users WHERE username=ANY(%s) ORDER BY username", (await asyncio.to_thread(profile_ids, user_id),))
        return CareMeResponse(
            username=user_id,
            account_role=role,
            accountRole=role,
            member_facilities=memberships,
            memberFacilities=memberships,
            profiles=profiles,
        )

    @app.get("/api/care/facilities", tags=[TAG])
    async def list_care_facilities(
        type: Optional[str] = Query(default=None),
        level: Optional[str] = Query(default=None),
        q: Optional[str] = Query(default=None),
        user_id: str = Depends(get_current_user_id),
    ):
        store = get_care_connect_store()
        facilities = await asyncio.to_thread(
            store.list_facilities,
            type_filter=type,
            level_filter=level,
            search=q,
        )
        memberships = await asyncio.to_thread(store.get_member_facilities, user_id)
        managed_ids = {m["facility_id"] for m in memberships}
        return {"facilities": [f for f in facilities if f.get("published", True) or f["id"] in managed_ids]}

    @app.get("/api/care/facilities/{facility_id}", tags=[TAG])
    async def get_care_facility(
        facility_id: str,
        user_id: str = Depends(get_current_user_id),
    ):
        store = get_care_connect_store()
        fac = await asyncio.to_thread(store.get_facility, facility_id)
        if not fac:
            raise CodedHTTPException(
                404, "facility_not_found", f"Facility {facility_id!r} not found."
            )
        if not fac.get("published", True) and not await asyncio.to_thread(store.is_facility_member, user_id, facility_id):
            raise CodedHTTPException(404, "facility_not_found", "Facility is not published.")
        return {"facility": fac}

    @app.put("/api/care/catalog/facilities/{facility_id}", tags=[TAG])
    async def save_care_facility(facility_id: str, payload: CareCatalogPayload, user_id: str = Depends(get_current_user_id)):
        """Save the catalogue for a managed facility, including publication and service flags."""
        if len(facility_id) > 40 or not facility_id.replace("-", "").isalnum():
            raise CodedHTTPException(422, "FACILITY", "Invalid facility identifier.")
        facility = await asyncio.to_thread(get_care_connect_store().save_facility, facility_id, user_id, payload.model_dump())
        return {"facility": facility}

    @app.get("/api/care/facilities/{facility_id}/slots", tags=[TAG])
    async def list_facility_slots(
        facility_id: str,
        date: Optional[str] = Query(default=None),
        consult_type: Optional[str] = Query(default=None),
        user_id: str = Depends(get_current_user_id),
    ):
        store = get_care_connect_store()
        slots = await asyncio.to_thread(
            store.list_slots,
            facility_id,
            date_str=date,
            consult_type=consult_type,
        )
        return {"slots": slots}

    @app.post("/api/care/recommendations", tags=[TAG])
    async def recommend_care_facilities(
        payload: CareRecommendRequestPayload,
        user_id: str = Depends(get_current_user_id),
    ):
        store = get_care_connect_store()
        facilities = await asyncio.to_thread(store.list_facilities)
        facilities = [f for f in facilities if f.get("published", True) and (not payload.preferred_region or f.get("region", "hcm") == payload.preferred_region)]
        if payload.service_type:
            facilities = [f for f in facilities if any(s.get("uiId") == payload.service_type and s.get("accepting", True) for s in f.get("services", []))]
            # Budget comparison uses the selected service and its own unit.
            facilities = [{**f, "price_from": next(s["price"] for s in f["services"] if s.get("uiId") == payload.service_type), "price_unit": next(s["priceUnit"] for s in f["services"] if s.get("uiId") == payload.service_type)} for f in facilities]
        recommendations = rank_facilities(
            facilities,
            care_level=payload.care_level,
            required_tags=payload.required_tags,
            preferred_district=payload.preferred_district,
            max_distance_km=payload.max_distance_km,
            budget_max=payload.budget_max,
            budget_unit=payload.budget_unit,
            preferred_type=payload.preferred_type,
        )
        return {
            "rules_version": RECOMMEND_RULES_VERSION,
            "rulesVersion": RECOMMEND_RULES_VERSION,
            "recommendations": recommendations,
        }

    @app.post("/api/care/requests", status_code=201, tags=[TAG])
    async def create_care_request(
        payload: CreateCareRequestPayload,
        response: Response,
        idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
        user_id: str = Depends(get_current_user_id),
    ):
        if not payload.consent:
            raise CodedHTTPException(422, "CONSENT", "Explicit consent is required before sharing a request.")
        allowed_profiles = {user_id, *await asyncio.to_thread(authz.elders_of, user_id)}
        if payload.profile_id not in allowed_profiles:
            raise CodedHTTPException(403, "profile_forbidden", "The profile must belong to you or a linked elder.")
        store = get_care_connect_store()
        req_dict, created_new = await asyncio.to_thread(
            store.create_request,
            user_id,
            payload.model_dump(by_alias=False),
            idempotency_key=idempotency_key,
        )
        if not created_new:
            response.status_code = 200
        return {"request": req_dict, "created": created_new}

    @app.get("/api/care/requests", tags=[TAG])
    async def list_care_requests(
        scope: str = Query(default="mine"),
        facility_id: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
        user_id: str = Depends(get_current_user_id),
    ):
        store = get_care_connect_store()
        requests = await asyncio.to_thread(
            store.list_requests,
            user_id,
            scope=scope,
            facility_id=facility_id,
            status=status,
        )
        return {"requests": requests}

    @app.get("/api/care/requests/{request_id}", tags=[TAG])
    async def get_care_request(
        request_id: str,
        user_id: str = Depends(get_current_user_id),
    ):
        store = get_care_connect_store()
        req_dict = await asyncio.to_thread(store.get_request, request_id, user_id)
        return {"request": req_dict}

    @app.post("/api/care/requests/{request_id}/actions", tags=[TAG])
    async def act_on_care_request(
        request_id: str,
        payload: CareRequestActionPayload,
        user_id: str = Depends(get_current_user_id),
    ):
        store = get_care_connect_store()
        req_dict = await asyncio.to_thread(
            store.apply_action,
            request_id=request_id,
            user_id=user_id,
            action=payload.action,
            expected_version=payload.expected_version,
            note=payload.note,
            proposed_slot=payload.proposed_slot,
            slot_id=payload.slot_id,
        )
        return {"request": req_dict}

    @app.post("/api/care/requests/{request_id}/feedback", status_code=201, tags=[TAG])
    async def submit_care_feedback(
        request_id: str,
        payload: CareFeedbackPayload,
        user_id: str = Depends(get_current_user_id),
    ):
        store = get_care_connect_store()
        fb = await asyncio.to_thread(
            store.create_feedback,
            request_id=request_id,
            user_id=user_id,
            rating=payload.rating,
            tags=payload.tags,
            comment=payload.comment,
        )
        return {"feedback": fb}

    @app.get("/api/care/facilities/{facility_id}/feedback", tags=[TAG])
    async def list_care_facility_feedback(
        facility_id: str,
        include_unapproved: bool = Query(default=False),
        user_id: str = Depends(get_current_user_id),
    ):
        store = get_care_connect_store()
        can_see_all = False
        if include_unapproved:
            can_see_all = await asyncio.to_thread(
                store.is_facility_member, user_id, facility_id, True
            )
        items = await asyncio.to_thread(
            store.list_facility_feedback,
            facility_id,
            include_unapproved=can_see_all,
            owner_id=user_id,
        )
        return {"feedback": items}

    @app.patch("/api/care/feedback/{feedback_id}/moderation", tags=[TAG])
    async def moderate_care_feedback(
        feedback_id: str,
        payload: CareFeedbackModerationPayload,
        user_id: str = Depends(get_current_user_id),
    ):
        store = get_care_connect_store()
        updated = await asyncio.to_thread(
            store.moderate_feedback,
            feedback_id=feedback_id,
            user_id=user_id,
            moderation_status=payload.moderation_status,
        )
        return {"feedback": updated}
