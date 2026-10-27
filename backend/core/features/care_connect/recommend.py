"""Rule-based explainable recommendation engine for Care Connect facilities (4.3.2).

Non-medical decision support: scores facilities using explicit weights and returns
both matching reasons (`reasons`) and caveats/gaps (`missing`).
"""

from __future__ import annotations

from typing import Any

RECOMMEND_RULES_VERSION = "care-rec-v1"

TAG_LABELS_VI: dict[str, str] = {
    "nursing": "Hỗ trợ chăm sóc", "garden": "Không gian xanh", "accessible": "Lối đi tiếp cận", "family": "Hỗ trợ gia đình", "rehab": "Phục hồi chức năng",
    "dementia": "Sa sút trí tuệ",
    "stroke_rehab": "Phục hồi sau tai biến",
    "post_surgery": "Hậu phẫu",
    "mobility_aid": "Hỗ trợ vận động",
    "medication_mgmt": "Quản lý thuốc",
    "night_monitoring": "Theo dõi ban đêm",
    "physiotherapy": "Vật lý trị liệu",
    "nutrition_plan": "Dinh dưỡng bệnh lý",
    "companionship": "Đồng hành tâm lý",
}


def score_facility(
    facility: dict[str, Any],
    *,
    care_level: str,
    required_tags: list[str] | None = None,
    preferred_district: str = "",
    max_distance_km: float = 0.0,
    budget_max: int = 0,
    budget_unit: str = "month",
    preferred_type: str = "",
) -> dict[str, Any]:
    """Score a single facility out of 100 and build explainable `reasons` and `missing`."""
    score = 0
    reasons: list[str] = []
    missing: list[str] = []

    suitable_for = [str(x) for x in (facility.get("suitable_for") or facility.get("suitableFor") or [])]
    support_tags = [str(x) for x in (facility.get("support_tags") or facility.get("supportTags") or [])]
    support_tags.extend(str(x) for x in (facility.get("amenities") or []))
    fac_district = str(facility.get("district") or "").strip()
    fac_type = str(facility.get("facility_type") or facility.get("type") or "").strip()
    fac_distance = float(facility.get("distance_km") if facility.get("distance_km") is not None else facility.get("distanceKm", 0.0))
    price_from = int(facility.get("price_from") if facility.get("price_from") is not None else facility.get("priceFrom", 0))
    price_unit = str(facility.get("price_unit") or facility.get("priceUnit") or "month").strip()

    # 1. Care level match (35 points)
    if care_level and care_level in suitable_for:
        score += 35
        reasons.append(f"Phù hợp mức độ chăm sóc {care_level}")
    elif care_level:
        missing.append(f"Chưa ghi nhận nhóm chăm sóc {care_level}")

    # 2. Support tags match (30 points)
    req_tags = [t.strip() for t in (required_tags or []) if t and t.strip()]
    if req_tags:
        matched_tags = [t for t in req_tags if t in support_tags]
        missing_tags = [t for t in req_tags if t not in support_tags]
        tag_points = round(30 * (len(matched_tags) / len(req_tags)))
        score += tag_points
        if matched_tags:
            labels = ", ".join(TAG_LABELS_VI.get(t, t) for t in matched_tags)
            reasons.append(
                f"Đáp ứng {len(matched_tags)}/{len(req_tags)} nhu cầu hỗ trợ ({labels})"
            )
        if missing_tags:
            labels = ", ".join(TAG_LABELS_VI.get(t, t) for t in missing_tags)
            missing.append(f"Thiếu hạng mục hỗ trợ: {labels}")
    else:
        score += 30
        reasons.append("Đáp ứng nhu cầu chăm sóc cơ bản")

    # 3. Location / distance match (15 points)
    pref_dist = (preferred_district or "").strip()
    max_dist = float(max_distance_km or 0.0)
    dist_matched = False
    if pref_dist and fac_district.lower() == pref_dist.lower():
        dist_matched = True
        reasons.append(f"Nằm tại khu vực ưu tiên ({fac_district})")
    elif max_dist > 0 and fac_distance <= max_dist:
        dist_matched = True
        reasons.append(f"Khoảng cách {fac_distance:.1f} km nằm trong bán kính {max_dist:.0f} km")
    elif not pref_dist and max_dist <= 0:
        dist_matched = True
        reasons.append(f"Khoảng cách di chuyển {fac_distance:.1f} km")

    if dist_matched:
        score += 15
    else:
        if pref_dist and fac_district.lower() != pref_dist.lower():
            missing.append(f"Khác khu vực ưu tiên ({fac_district})")
        if max_dist > 0 and fac_distance > max_dist:
            missing.append(f"Khoảng cách {fac_distance:.1f} km vượt mức {max_dist:.0f} km")

    # 4. Budget & price unit check (15 points)
    # Price 0 or unit 'contact' means unpublished price — never treat as free!
    if price_from <= 0 or price_unit == "contact":
        missing.append("Chưa công bố giá (cần liên hệ trực tiếp cơ sở)")
    elif budget_max > 0:
        if price_unit != budget_unit:
            missing.append(
                f"Đơn vị tính giá ({price_unit}) khác ngân sách ({budget_unit}) nên không so sánh trực tiếp"
            )
        elif price_from <= budget_max:
            score += 15
            reasons.append(
                f"Chi phí khởi điểm ({price_from:,}đ/{price_unit}) phù hợp ngân sách"
            )
        else:
            missing.append(
                f"Chi phí khởi điểm ({price_from:,}đ/{price_unit}) vượt ngân sách dự kiến"
            )
    else:
        score += 15
        reasons.append(f"Có bảng giá công khai từ {price_from:,}đ/{price_unit}")

    # 5. Preferred facility type (5 points)
    pref_type = (preferred_type or "").strip()
    if not pref_type or pref_type == "ALL" or fac_type == pref_type:
        score += 5
        if pref_type and pref_type != "ALL":
            reasons.append("Đúng loại hình cơ sở mong muốn")
    else:
        missing.append("Khác loại hình cơ sở ưu tiên")

    facility_id = str(facility.get("id") or "")
    return {
        "facility_id": facility_id,
        "facilityId": facility_id,
        "score": min(100, max(0, int(score))),
        "reasons": reasons,
        "missing": missing,
        "rules_version": RECOMMEND_RULES_VERSION,
        "rulesVersion": RECOMMEND_RULES_VERSION,
        "_distance_km": fac_distance,
    }


def rank_facilities(
    facilities: list[dict[str, Any]],
    *,
    care_level: str,
    required_tags: list[str] | None = None,
    preferred_district: str = "",
    max_distance_km: float = 0.0,
    budget_max: int = 0,
    budget_unit: str = "month",
    preferred_type: str = "",
) -> list[dict[str, Any]]:
    """Score and sort facilities deterministically by `(-score, distance_km, id)`."""
    scored = [
        score_facility(
            fac,
            care_level=care_level,
            required_tags=required_tags,
            preferred_district=preferred_district,
            max_distance_km=max_distance_km,
            budget_max=budget_max,
            budget_unit=budget_unit,
            preferred_type=preferred_type,
        )
        for fac in facilities
    ]
    scored.sort(key=lambda item: (-item["score"], item["_distance_km"], item["facility_id"]))
    for item in scored:
        item.pop("_distance_km", None)
    return scored
