"""Pydantic request and response schemas for Care Connect routes."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CareMemberFacilityOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    facility_id: str
    facilityId: Optional[str] = None
    member_role: Literal["staff", "manager"] = "staff"
    memberRole: Optional[str] = None


class CareMeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    username: str
    account_role: str
    accountRole: Optional[str] = None
    member_facilities: list[CareMemberFacilityOut] = Field(default_factory=list)
    memberFacilities: list[CareMemberFacilityOut] = Field(default_factory=list)


class CreateCareRequestPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    consent: bool = False

    profile_id: str = Field(default="elder-1", alias="profileId")
    profile_name: str = Field(default="Người cao tuổi", alias="profileName")
    profile_age: int = Field(default=70, alias="profileAge")
    care_level: Literal["L1", "L2", "L3"] = Field(default="L1", alias="careLevel")
    care_needs: str = Field(default="", alias="careNeeds")
    facility_id: str = Field(..., alias="facilityId")
    service_id: str = Field(..., alias="serviceId")
    consult_type: Literal["visit", "phone", "video"] = Field(
        default="visit", alias="consultType"
    )
    preferred_slot: str = Field(..., alias="preferredSlot")
    slot_id: Optional[str] = Field(default=None, alias="slotId")
    contact_name: str = Field(..., alias="contactName")
    contact_phone: str = Field(..., alias="contactPhone")
    note: str = ""
    reminder_opt_in: bool = Field(default=False, alias="reminderOptIn")


class CareRequestActionPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    action: Literal[
        "start_review",
        "staff_cancel",
        "confirm",
        "propose_slot",
        "reject",
        "complete",
        "accept_slot",
        "cancel",
    ]
    expected_version: int = Field(..., alias="expectedVersion")
    note: str = ""
    proposed_slot: Optional[str] = Field(default=None, alias="proposedSlot")
    slot_id: Optional[str] = Field(default=None, alias="slotId")


class CareRecommendRequestPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    care_level: Literal["L1", "L2", "L3"] = Field(default="L1", alias="careLevel")
    preferred_region: str = Field(default="", alias="preferredRegion")
    service_type: str = Field(default="", alias="serviceType")
    required_tags: list[str] = Field(default_factory=list, alias="requiredTags")
    preferred_district: str = Field(default="", alias="preferredDistrict")
    max_distance_km: float = Field(default=0.0, alias="maxDistanceKm")
    budget_max: int = Field(default=0, alias="budgetMax")
    budget_unit: Literal["month", "day", "session", "contact"] = Field(
        default="month", alias="budgetUnit"
    )
    preferred_type: str = Field(default="", alias="preferredType")


class CareFeedbackPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    rating: int = Field(..., ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    comment: str = ""


class CareFeedbackModerationPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    moderation_status: Literal["approved", "rejected", "pending"] = Field(
        ..., alias="moderationStatus"
    )


class CareCatalogServicePayload(BaseModel):
    """Public service details editable by a facility manager."""

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    category: Literal["stay", "day", "rehab", "medical"]
    price: int = Field(ge=0, le=2000000000)
    price_unit: Literal["month", "day", "session"]
    ui_id: Literal["longstay", "daycare", "rehab"]
    accepting: bool = True


class CareCatalogPayload(BaseModel):
    """Validated catalogue input; verification flags are never supplied by clients."""

    name: str = Field(min_length=2, max_length=255)
    facility_type: Literal["nursing_home", "day_care", "rehab", "home_care"]
    region: Literal["hcm", "hanoi", "danang"]
    address: str = Field(min_length=5, max_length=1000)
    description: str = Field(min_length=5, max_length=3000)
    phone: str = Field(default="", max_length=64)
    published: bool
    amenities: list[str] = Field(default_factory=list, max_length=30)
    services: list[CareCatalogServicePayload] = Field(min_length=1, max_length=20)
