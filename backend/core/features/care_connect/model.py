"""Domain constants and state machine for Care Connect requests."""

from __future__ import annotations

from typing import Literal, Optional

CareLevel = Literal["L1", "L2", "L3"]
CareFacilityType = Literal["nursing_home", "day_care", "rehab", "home_care"]
CareServiceCategory = Literal["stay", "day", "rehab", "medical"]
CareConsultType = Literal["visit", "phone", "video"]
CareActorRole = Literal["caregiver", "staff"]
CareMemberRole = Literal["staff", "manager"]
CarePriceUnit = Literal["month", "day", "session", "contact"]

CareSupportTag = Literal[
    "dementia",
    "stroke_rehab",
    "post_surgery",
    "mobility_aid",
    "medication_mgmt",
    "night_monitoring",
    "physiotherapy",
    "nutrition_plan",
    "companionship",
]

CareRequestStatus = Literal[
    "PENDING",
    "IN_REVIEW",
    "CONFIRMED",
    "RESCHEDULE_PROPOSED",
    "COMPLETED",
    "REJECTED",
    "CANCELLED",
]

CareRequestAction = Literal[
    "start_review",
    "staff_cancel",
    "confirm",
    "propose_slot",
    "reject",
    "complete",
    "accept_slot",
    "cancel",
]

VALID_CARE_LEVELS: frozenset[str] = frozenset({"L1", "L2", "L3"})
VALID_FACILITY_TYPES: frozenset[str] = frozenset(
    {"nursing_home", "day_care", "rehab", "home_care"}
)
VALID_CONSULT_TYPES: frozenset[str] = frozenset({"visit", "phone", "video"})
VALID_SUPPORT_TAGS: frozenset[str] = frozenset(
    {
        "dementia",
        "stroke_rehab",
        "post_surgery",
        "mobility_aid",
        "medication_mgmt",
        "night_monitoring",
        "physiotherapy",
        "nutrition_plan",
        "companionship",
    }
)

STAFF_ACTIONS: frozenset[str] = frozenset(
    {"start_review", "confirm", "propose_slot", "reject", "complete", "staff_cancel"}
)
CAREGIVER_ACTIONS: frozenset[str] = frozenset({"accept_slot", "cancel"})

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"COMPLETED", "REJECTED", "CANCELLED"}
)

REASON_REQUIRED_ACTIONS: frozenset[str] = frozenset(
    {"propose_slot", "reject", "cancel", "staff_cancel"}
)

ALLOWED_TRANSITIONS: dict[str, dict[str, str]] = {
    "PENDING": {
        "staff_cancel": "CANCELLED",
        "start_review": "IN_REVIEW",
        "confirm": "CONFIRMED",
        "propose_slot": "RESCHEDULE_PROPOSED",
        "reject": "REJECTED",
        "cancel": "CANCELLED",
    },
    "IN_REVIEW": {
        "staff_cancel": "CANCELLED",
        "confirm": "CONFIRMED",
        "propose_slot": "RESCHEDULE_PROPOSED",
        "reject": "REJECTED",
        "cancel": "CANCELLED",
    },
    "RESCHEDULE_PROPOSED": {
        "staff_cancel": "CANCELLED",
        "accept_slot": "CONFIRMED",
        "propose_slot": "RESCHEDULE_PROPOSED",
        "reject": "REJECTED",
        "cancel": "CANCELLED",
    },
    "CONFIRMED": {
        "staff_cancel": "CANCELLED",
        "complete": "COMPLETED",
        "propose_slot": "RESCHEDULE_PROPOSED",
        "cancel": "CANCELLED",
    },
    "COMPLETED": {},
    "REJECTED": {},
    "CANCELLED": {},
}


def can_perform_action(
    status: str, action: str, role: str
) -> bool:
    """Return True if `role` is allowed to trigger `action` from `status`."""
    if role == "staff" and action not in STAFF_ACTIONS:
        return False
    if role == "caregiver" and action not in CAREGIVER_ACTIONS:
        return False
    if role not in ("staff", "caregiver"):
        return False
    next_status = ALLOWED_TRANSITIONS.get(status, {}).get(action)
    return bool(next_status)


def resolve_transition(
    status: str, action: str, role: str
) -> tuple[Optional[str], Optional[str]]:
    """Return `(next_status, error_code)`.

    If valid, returns `(next_status, None)`.
    Otherwise returns `(None, 'ACTION')`.
    """
    if not can_perform_action(status, action, role):
        return None, "ACTION"
    next_status = ALLOWED_TRANSITIONS.get(status, {}).get(action)
    if not next_status:
        return None, "ACTION"
    return next_status, None
