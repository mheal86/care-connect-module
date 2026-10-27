"""Care Connect domain package (Chapter 4 extension)."""

from backend.core.features.care_connect.model import (
    ALLOWED_TRANSITIONS,
    CAREGIVER_ACTIONS,
    REASON_REQUIRED_ACTIONS,
    STAFF_ACTIONS,
    TERMINAL_STATUSES,
    CareActorRole,
    CareConsultType,
    CareFacilityType,
    CareLevel,
    CareMemberRole,
    CarePriceUnit,
    CareRequestAction,
    CareRequestStatus,
    CareServiceCategory,
    CareSupportTag,
    resolve_transition,
)
from backend.core.features.care_connect.recommend import (
    RECOMMEND_RULES_VERSION,
    rank_facilities,
    score_facility,
)
from backend.core.features.care_connect.store import (
    CareConnectStore,
    get_care_connect_store,
    reset_care_connect_store,
)
from backend.core.features.care_connect.validation import (
    validate_phone,
    validate_reason,
    validate_slot_is_future,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "CAREGIVER_ACTIONS",
    "REASON_REQUIRED_ACTIONS",
    "RECOMMEND_RULES_VERSION",
    "STAFF_ACTIONS",
    "TERMINAL_STATUSES",
    "CareActorRole",
    "CareConnectStore",
    "CareConsultType",
    "CareFacilityType",
    "CareLevel",
    "CareMemberRole",
    "CarePriceUnit",
    "CareRequestAction",
    "CareRequestStatus",
    "CareServiceCategory",
    "CareSupportTag",
    "get_care_connect_store",
    "rank_facilities",
    "reset_care_connect_store",
    "resolve_transition",
    "score_facility",
    "validate_phone",
    "validate_reason",
    "validate_slot_is_future",
]
