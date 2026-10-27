"""PostgreSQL store for Care Connect (facilities, requests, events, slots, feedback)."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Optional

import psycopg2.extras

from backend.core.db.connection import get_conn
from backend.core.errors import CodedHTTPException
from backend.core.features.care_connect.model import (
    CAREGIVER_ACTIONS,
    STAFF_ACTIONS,
    resolve_transition,
)
from backend.core.features.care_connect.validation import (
    parse_iso_datetime,
    validate_phone,
    validate_reason,
    validate_slot_is_future,
)

DEFAULT_FACILITIES_SEED: list[dict[str, Any]] = [
    {
        "id": "an-nhien",
        "amenities": ["nursing", "garden", "accessible", "family"],
        "name": "Trung tâm Dưỡng lão An Nhiên",
        "facility_type": "nursing_home",
        "district": "Quận 7, TP.HCM",
        "address": "128 Nguyễn Lương Bằng, Phú Mỹ Hưng, Quận 7, TP.HCM",
        "phone": "028 3876 5412",
        "hours": "07:30 - 19:00 (Thứ 2 - Chủ nhật)",
        "distance_km": 3.4,
        "lat": 10.7295,
        "lng": 106.7218,
        "geo_verified": False,
        "verified_badge": False,
        "price_from": 12000000,
        "price_to": 22000000,
        "price_unit": "month",
        "support_tags": [
            "dementia",
            "mobility_aid",
            "medication_mgmt",
            "night_monitoring",
            "nutrition_plan",
        ],
        "highlights": [
            "Điều dưỡng trực 24/7, theo dõi sinh hiệu mỗi ca",
            "Khu vườn đi bộ chống trượt và phòng sinh hoạt nhóm",
            "Báo cáo sức khỏe hàng tuần gửi trực tiếp qua ứng dụng",
        ],
        "suitable_for": ["L1", "L2", "L3"],
        "services": [
            {
                "id": "an-nhien-stay-30",
                "name": "Gói nội trú tiêu chuẩn 30 ngày",
                "category": "stay",
                "duration_label": "30 ngày",
                "price": 14500000,
                "price_unit": "month",
                "note": "Bao gồm phòng đôi, 4 bữa dinh dưỡng/ngày và theo dõi thuốc.",
            },
            {
                "id": "an-nhien-dementia",
                "name": "Gói chăm sóc trí nhớ chuyên biệt",
                "category": "medical",
                "duration_label": "Theo tháng",
                "price": 19500000,
                "price_unit": "month",
                "note": "Thiết kế cho người suy giảm trí nhớ mức vừa, có trị liệu nhận thức.",
            },
            {
                "id": "an-nhien-trial-7",
                "name": "Tuần trải nghiệm làm quen",
                "category": "stay",
                "duration_label": "7 ngày",
                "price": 4200000,
                "price_unit": "session",
                "note": "Phù hợp gia đình muốn đánh giá mức độ hòa nhập trước khi đăng ký dài hạn.",
            },
        ],
    },
    {
        "id": "binh-an",
        "amenities": ["accessible", "family"],
        "name": "CLB Bán trú Người cao tuổi Bình An",
        "facility_type": "day_care",
        "district": "Quận Bình Thạnh, TP.HCM",
        "address": "45 Điện Biên Phủ, Phường 15, Quận Bình Thạnh, TP.HCM",
        "phone": "028 3512 8890",
        "hours": "07:00 - 17:30 (Thứ 2 - Thứ 7)",
        "distance_km": 2.1,
        "lat": 10.7992,
        "lng": 106.7065,
        "geo_verified": False,
        "verified_badge": False,
        "price_from": 450000,
        "price_to": 8500000,
        "price_unit": "day",
        "support_tags": [
            "companionship",
            "medication_mgmt",
            "nutrition_plan",
            "mobility_aid",
        ],
        "highlights": [
            "Đón sáng - trả chiều, gia đình yên tâm đi làm",
            "Lịch vận động nhẹ, cờ tướng, âm nhạc và dưỡng sinh mỗi ngày",
            "Thực đơn giảm muối, kiểm soát đường huyết theo hồ sơ",
        ],
        "suitable_for": ["L1", "L2"],
        "services": [
            {
                "id": "binh-an-day-pass",
                "name": "Gói bán trú theo ngày",
                "category": "day",
                "duration_label": "07:30 - 17:00",
                "price": 450000,
                "price_unit": "day",
                "note": "Ăn trưa, ăn xế, nghỉ trưa và 2 khung hoạt động nhóm.",
            },
            {
                "id": "binh-an-month-22",
                "name": "Gói bán trú 22 ngày/tháng",
                "category": "day",
                "duration_label": "22 ngày",
                "price": 8200000,
                "price_unit": "month",
                "note": "Ưu đãi xe đưa đón trong bán kính 5km.",
            },
        ],
    },
    {
        "id": "phuoc-loc",
        "amenities": ["rehab", "accessible"],
        "name": "Viện Phục hồi Chức năng Phước Lộc",
        "facility_type": "rehab",
        "district": "TP. Thủ Đức, TP.HCM",
        "address": "210 Võ Văn Ngân, Phường Bình Thọ, TP. Thủ Đức, TP.HCM",
        "phone": "028 3722 1945",
        "hours": "07:30 - 18:00 (Thứ 2 - Chủ nhật)",
        "distance_km": 6.8,
        "lat": 10.8505,
        "lng": 106.7648,
        "geo_verified": False,
        "verified_badge": False,
        "price_from": 6800000,
        "price_to": 25000000,
        "price_unit": "month",
        "support_tags": [
            "stroke_rehab",
            "post_surgery",
            "physiotherapy",
            "mobility_aid",
            "night_monitoring",
        ],
        "highlights": [
            "Bác sĩ phục hồi chức năng lập phác đồ 1-1 sau tai biến, gãy xương",
            "Phòng tập robot hỗ trợ vận động và điện trị liệu",
            "Đánh giá tiến triển khả năng đi lại sau mỗi 2 tuần",
        ],
        "suitable_for": ["L2", "L3"],
        "services": [
            {
                "id": "phuoc-loc-stroke-10",
                "name": "Liệu trình phục hồi sau tai biến (10 buổi)",
                "category": "rehab",
                "duration_label": "10 buổi x 60 phút",
                "price": 6800000,
                "price_unit": "session",
                "note": "Vật lý trị liệu vận động + ngôn ngữ trị liệu cơ bản.",
            },
            {
                "id": "phuoc-loc-inpatient-30",
                "name": "Nội trú phục hồi tích cực 30 ngày",
                "category": "stay",
                "duration_label": "30 ngày",
                "price": 24000000,
                "price_unit": "month",
                "note": "Dành cho người cao tuổi cần hỗ trợ toàn phần giai đoạn sau xuất viện.",
            },
        ],
    },
    {
        "id": "tam-duc",
        "amenities": ["nursing", "family"],
        "name": "Dịch vụ Điều dưỡng Tại nhà Tâm Đức",
        "facility_type": "home_care",
        "district": "Quận 3, TP.HCM",
        "address": "88 Nam Kỳ Khởi Nghĩa, Phường Võ Thị Sáu, Quận 3, TP.HCM",
        "phone": "028 3930 4411",
        "hours": "06:30 - 21:00 (Hỗ trợ đặt ca linh hoạt)",
        "distance_km": 1.6,
        "lat": 10.7838,
        "lng": 106.6915,
        "geo_verified": False,
        "verified_badge": False,
        "price_from": 380000,
        "price_to": 16500000,
        "price_unit": "session",
        "support_tags": [
            "post_surgery",
            "medication_mgmt",
            "physiotherapy",
            "companionship",
        ],
        "highlights": [
            "Điều dưỡng viên có chứng chỉ hành nghề đến chăm sóc tại nhà",
            "Phù hợp người lớn tuổi không muốn thay đổi môi trường sống",
            "Bàn giao nhật ký ca trực trên hệ thống sau mỗi buổi",
        ],
        "suitable_for": ["L1", "L2", "L3"],
        "services": [
            {
                "id": "tam-duc-shift-4h",
                "name": "Ca chăm sóc tại nhà 4 giờ",
                "category": "medical",
                "duration_label": "4 giờ/ca",
                "price": 380000,
                "price_unit": "session",
                "note": "Vệ sinh cá nhân, đo huyết áp, đường huyết, hỗ trợ ăn uống và tập vận động nhẹ.",
            },
            {
                "id": "tam-duc-shift-24",
                "name": "Gói điều dưỡng đồng hành theo tháng",
                "category": "stay",
                "duration_label": "26 ngày/tháng",
                "price": 16500000,
                "price_unit": "month",
                "note": "Chăm sóc 8 giờ/ngày tại gia đình theo lịch cố định.",
            },
        ],
    },
]


def _iso_utc(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


class CareConnectStore:
    """Persistence layer for Care Connect using PostgreSQL."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seeded = False

    def ensure_seeded(self) -> None:
        """Seed the 4 canonical facilities and initial consultation slots if empty."""
        if self._seeded:
            return
        with self._lock:
            if self._seeded:
                return
            try:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) FROM care_facilities")
                        count = (cur.fetchone() or [0])[0]
                        if count == 0:
                            self._seed_facilities_in_tx(cur, DEFAULT_FACILITIES_SEED)
                    conn.commit()
                self._seeded = True
            except Exception as e:
                print(f"[CARE_CONNECT] ensure_seeded skipped/failed: {e}")

    def _seed_facilities_in_tx(self, cur, facilities: list[dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc)
        for fac in facilities:
            services = fac.get("services") or []
            cur.execute(
                """
                INSERT INTO care_facilities (
                    id, name, facility_type, district, address, phone, hours,
                    distance_km, lat, lng, geo_verified, verified_badge,
                    price_from, price_to, price_unit, support_tags,
                    highlights, suitable_for, services, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s::jsonb,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    facility_type = EXCLUDED.facility_type,
                    district = EXCLUDED.district,
                    address = EXCLUDED.address,
                    phone = EXCLUDED.phone,
                    hours = EXCLUDED.hours,
                    distance_km = EXCLUDED.distance_km,
                    lat = EXCLUDED.lat,
                    lng = EXCLUDED.lng,
                    geo_verified = EXCLUDED.geo_verified,
                    verified_badge = EXCLUDED.verified_badge,
                    price_from = EXCLUDED.price_from,
                    price_to = EXCLUDED.price_to,
                    price_unit = EXCLUDED.price_unit,
                    support_tags = EXCLUDED.support_tags,
                    highlights = EXCLUDED.highlights,
                    suitable_for = EXCLUDED.suitable_for,
                    services = EXCLUDED.services,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    fac["id"],
                    fac["name"],
                    fac["facility_type"],
                    fac["district"],
                    fac["address"],
                    fac["phone"],
                    fac["hours"],
                    fac["distance_km"],
                    fac.get("lat"),
                    fac.get("lng"),
                    bool(fac.get("geo_verified", False)),
                    bool(fac.get("verified_badge", True)),
                    int(fac.get("price_from", 0)),
                    int(fac.get("price_to", 0)),
                    fac.get("price_unit", "month"),
                    json.dumps(fac.get("support_tags") or []),
                    json.dumps(fac.get("highlights") or []),
                    json.dumps(fac.get("suitable_for") or []),
                    json.dumps(services),
                    now,
                ),
            )
            if "amenities" in fac:
                cur.execute("UPDATE care_facilities SET amenities=%s::jsonb WHERE id=%s", (json.dumps(fac["amenities"]), fac["id"]))
            for svc in services:
                cur.execute(
                    """
                    INSERT INTO care_facility_services (
                        id, facility_id, name, category, duration_label, price, price_unit, note
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        category = EXCLUDED.category,
                        duration_label = EXCLUDED.duration_label,
                        price = EXCLUDED.price,
                        price_unit = EXCLUDED.price_unit,
                        note = EXCLUDED.note
                    """,
                    (
                        svc["id"],
                        fac["id"],
                        svc["name"],
                        svc["category"],
                        svc.get("duration_label") or svc.get("durationLabel") or "",
                        int(svc.get("price", 0)),
                        svc.get("price_unit") or fac.get("price_unit", "month"),
                        svc.get("note", ""),
                    ),
                )
            # Seed default consultation capacity slots for the next 3 days
            for day_offset in (1, 2, 3):
                day_base = (now + timedelta(days=day_offset)).replace(
                    minute=0, second=0, microsecond=0
                )
                for hour, consult_type, cap in (
                    (9, "visit", 2),
                    (14, "phone", 3),
                    (16, "video", 2),
                ):
                    start_dt = day_base.replace(hour=hour)
                    end_dt = start_dt + timedelta(hours=1)
                    slot_id = f"slot-{fac['id']}-{start_dt.strftime('%Y%m%d%H')}-{consult_type}"
                    cur.execute(
                        """
                        INSERT INTO care_consult_slots (
                            id, facility_id, consult_type, starts_at, ends_at, capacity, booked_count
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, 0)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (slot_id, fac["id"], consult_type, start_dt, end_dt, cap),
                    )

    def seed_all(
        self,
        facilities: Optional[list[dict[str, Any]]] = None,
        staff_memberships: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, int]:
        """Explicitly seed facilities, services, slots, and optional staff memberships."""
        fac_list = facilities if facilities is not None else DEFAULT_FACILITIES_SEED
        with get_conn() as conn:
            with conn.cursor() as cur:
                self._seed_facilities_in_tx(cur, fac_list)
                member_count = 0
                for mem in staff_memberships or []:
                    cur.execute(
                        """
                        INSERT INTO care_facility_members (facility_id, user_id, member_role)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (facility_id, user_id) DO UPDATE SET
                            member_role = EXCLUDED.member_role
                        """,
                        (
                            mem["facility_id"],
                            mem["user_id"],
                            mem.get("member_role", "staff"),
                        ),
                    )
                    member_count += 1
            conn.commit()
        self._seeded = True
        return {"facilities": len(fac_list), "memberships": member_count}

    def add_facility_member(
        self, facility_id: str, user_id: str, member_role: str = "staff"
    ) -> None:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO care_facility_members (facility_id, user_id, member_role)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (facility_id, user_id) DO UPDATE SET
                        member_role = EXCLUDED.member_role
                    """,
                    (facility_id, user_id, member_role),
                )
            conn.commit()

    def get_member_facilities(self, user_id: str) -> list[dict[str, str]]:
        if not user_id:
            return []
        self.ensure_seeded()
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT facility_id, member_role
                      FROM care_facility_members
                     WHERE user_id = %s
                     ORDER BY facility_id
                    """,
                    (user_id,),
                )
                return [
                    {
                        "facility_id": str(r["facility_id"]),
                        "facilityId": str(r["facility_id"]),
                        "member_role": str(r["member_role"]),
                        "memberRole": str(r["member_role"]),
                    }
                    for r in cur.fetchall()
                ]

    def _facility_row_to_dict(
        self,
        row: dict[str, Any],
        services: Optional[list[dict[str, Any]]] = None,
        rating_stats: Optional[tuple[float, int]] = None,
    ) -> dict[str, Any]:
        raw_services = services if services is not None else (row.get("services") or [])
        norm_services = []
        for s in raw_services:
            dur = s.get("duration_label") or s.get("durationLabel") or ""
            p_unit = s.get("price_unit") or s.get("priceUnit") or row.get("price_unit") or "month"
            norm_services.append(
                {
                    "id": s["id"],
                    "name": s["name"],
                    "category": s["category"],
                    "duration_label": dur,
                    "durationLabel": dur,
                    "price": int(s.get("price", 0)),
                    "price_unit": p_unit,
                    "priceUnit": p_unit,
                    "note": s.get("note", ""),
                    "uiId": s.get("ui_id") or s.get("uiId") or {"stay": "longstay", "day": "daycare", "rehab": "rehab", "medical": "rehab"}.get(s["category"], "rehab"),
                    "accepting": bool(s.get("accepting", True)),
                }
            )
        avg_rating, fb_count = rating_stats or (0.0, 0)
        fac_type = str(row["facility_type"])
        dist_km = float(row["distance_km"])
        p_from = int(row["price_from"])
        p_to = int(row["price_to"])
        p_unit = str(row.get("price_unit") or "month")
        support_tags = list(row.get("support_tags") or [])
        suitable_for = list(row.get("suitable_for") or [])
        geo_ver = bool(row.get("geo_verified", False))
        ver_badge = bool(row.get("verified_badge", False))
        return {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "type": fac_type,
            "facility_type": fac_type,
            "district": str(row["district"]),
            "address": str(row["address"]),
            "phone": str(row["phone"]),
            "hours": str(row["hours"]),
            "distanceKm": dist_km,
            "distance_km": dist_km,
            "lat": float(row["lat"]) if row.get("lat") is not None else None,
            "lng": float(row["lng"]) if row.get("lng") is not None else None,
            "geoVerified": geo_ver,
            "geo_verified": geo_ver,
            "verifiedBadge": ver_badge,
            "verified_badge": ver_badge,
            "priceFrom": p_from,
            "price_from": p_from,
            "priceTo": p_to,
            "price_to": p_to,
            "priceUnit": p_unit,
            "price_unit": p_unit,
            "supportTags": support_tags,
            "support_tags": support_tags,
            "highlights": list(row.get("highlights") or []),
            "suitableFor": suitable_for,
            "suitable_for": suitable_for,
            "services": norm_services,
            "published": bool(row.get("published", True)),
            "region": str(row.get("region") or "hcm"),
            "description": str(row.get("description") or " ".join(row.get("highlights") or [])),
            "amenities": list(row.get("amenities") or []),
            "updatedAt": _iso_utc(row.get("updated_at")) or "",
            "averageRating": round(avg_rating, 2),
            "average_rating": round(avg_rating, 2),
            "feedbackCount": fb_count,
            "feedback_count": fb_count,
        }

    def list_facilities(
        self,
        type_filter: Optional[str] = None,
        level_filter: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        self.ensure_seeded()
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM care_facilities ORDER BY distance_km ASC, id ASC")
                rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT facility_id, AVG(rating)::float AS avg_r, COUNT(*)::int AS cnt
                      FROM care_feedback
                     WHERE moderation_status = 'approved'
                     GROUP BY facility_id
                    """
                )
                stats_map = {
                    str(r["facility_id"]): (float(r["avg_r"] or 0.0), int(r["cnt"] or 0))
                    for r in cur.fetchall()
                }
        out: list[dict[str, Any]] = []
        q = (search or "").strip().lower()
        for row in rows:
            fac = self._facility_row_to_dict(row, rating_stats=stats_map.get(str(row["id"])))
            if type_filter and type_filter != "ALL" and fac["facility_type"] != type_filter:
                continue
            if level_filter and level_filter != "ALL" and level_filter not in fac["suitable_for"]:
                continue
            if q:
                haystack = " ".join(
                    [
                        fac["name"],
                        fac["district"],
                        fac["address"],
                        " ".join(s["name"] for s in fac["services"]),
                    ]
                ).lower()
                if q not in haystack:
                    continue
            out.append(fac)
        return out

    def get_facility(self, facility_id: str) -> Optional[dict[str, Any]]:
        self.ensure_seeded()
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM care_facilities WHERE id = %s", (facility_id,))
                row = cur.fetchone()
                if not row:
                    return None
                cur.execute(
                    """
                    SELECT AVG(rating)::float AS avg_r, COUNT(*)::int AS cnt
                      FROM care_feedback
                     WHERE facility_id = %s AND moderation_status = 'approved'
                    """,
                    (facility_id,),
                )
                stat_row = cur.fetchone()
                stats = (
                    (float(stat_row["avg_r"] or 0.0), int(stat_row["cnt"] or 0))
                    if stat_row
                    else (0.0, 0)
                )
                return self._facility_row_to_dict(row, rating_stats=stats)

    def save_facility(self, facility_id: str, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist catalogue changes after checking manager permissions on the server."""
        self.ensure_seeded()
        existing = self.get_facility(facility_id)
        members = self.get_member_facilities(user_id)
        managers = [m["facility_id"] for m in members if m["member_role"] == "manager"]
        if (existing and facility_id not in managers) or (not existing and not managers):
            raise CodedHTTPException(403, "facility_forbidden", "A facility manager is required.")
        if payload.get("phone") and not validate_phone(payload["phone"]):
            raise CodedHTTPException(422, "PHONE", "Invalid facility contact phone.")
        services = [{**s, "duration_label": "", "note": ""} for s in payload["services"]]
        if len({s["ui_id"] for s in services}) != len(services):
            raise CodedHTTPException(422, "SERVICE", "Duplicate service categories.")
        # IDs are namespaced by the facility, so another catalogue cannot overwrite them.
        for service in services:
            service["id"] = f"{facility_id}-{service['ui_id']}"
        prices = [s["price"] for s in services if s["price"] > 0]
        facility = {
            **(existing or {}), **payload, "id": facility_id,
            "district": {"hcm": "TP.HCM", "hanoi": "Hà Nội", "danang": "Đà Nẵng"}[payload["region"]],
            "hours": (existing or {}).get("hours", "Liên hệ để thống nhất thời gian"),
            "distance_km": (existing or {}).get("distance_km", 0),
            "geo_verified": (existing or {}).get("geo_verified", False),
            "verified_badge": (existing or {}).get("verified_badge", False),
            "price_from": min(prices) if prices else 0,
            "price_to": max(prices) if prices else 0,
            "price_unit": services[0]["price_unit"], "services": services,
        }
        with get_conn() as conn:
            with conn.cursor() as cur:
                self._seed_facilities_in_tx(cur, [facility])
                cur.execute("UPDATE care_facilities SET published=%s, region=%s, description=%s, amenities=%s::jsonb WHERE id=%s", (payload["published"], payload["region"], payload["description"], json.dumps(payload["amenities"]), facility_id))
                if not existing:
                    cur.execute("INSERT INTO care_facility_members (facility_id, user_id, member_role) VALUES (%s, %s, 'manager')", (facility_id, user_id))
            conn.commit()
        return self.get_facility(facility_id) or {}

    def list_slots(
        self,
        facility_id: str,
        date_str: Optional[str] = None,
        consult_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        self.ensure_seeded()
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                sql = "SELECT * FROM care_consult_slots WHERE facility_id = %s AND starts_at > NOW()"
                params: list[Any] = [facility_id]
                if consult_type:
                    sql += " AND consult_type = %s"
                    params.append(consult_type)
                if date_str:
                    sql += " AND DATE(starts_at AT TIME ZONE 'UTC') = %s::date"
                    params.append(date_str)
                sql += " ORDER BY starts_at ASC"
                cur.execute(sql, params)
                rows = cur.fetchall()
        out = []
        for r in rows:
            cap = int(r["capacity"])
            booked = int(r["booked_count"])
            out.append(
                {
                    "id": str(r["id"]),
                    "facility_id": str(r["facility_id"]),
                    "facilityId": str(r["facility_id"]),
                    "consult_type": str(r["consult_type"]),
                    "consultType": str(r["consult_type"]),
                    "starts_at": _iso_utc(r["starts_at"]),
                    "startsAt": _iso_utc(r["starts_at"]),
                    "ends_at": _iso_utc(r["ends_at"]),
                    "endsAt": _iso_utc(r["ends_at"]),
                    "capacity": cap,
                    "booked_count": booked,
                    "bookedCount": booked,
                    "available": max(0, cap - booked),
                    "isFull": booked >= cap,
                }
            )
        return out

    def _event_row_to_dict(self, r: dict[str, Any]) -> dict[str, Any]:
        slot_iso = _iso_utc(r.get("slot")) if r.get("slot") else None
        event_dict: dict[str, Any] = {
            "id": f"ev-{r['id']}",
            "at": _iso_utc(r["at"]) or "",
            "actorRole": str(r["actor_role"]),
            "actor_role": str(r["actor_role"]),
            "actorName": str(r["actor_name"]),
            "actor_name": str(r["actor_name"]),
            "action": str(r["action"]),
            "fromStatus": str(r["from_status"]),
            "from_status": str(r["from_status"]),
            "toStatus": str(r["to_status"]),
            "to_status": str(r["to_status"]),
            "note": str(r.get("note") or ""),
        }
        if slot_iso:
            event_dict["slot"] = slot_iso
        return event_dict

    def _request_row_to_dict(
        self, row: dict[str, Any], events: list[dict[str, Any]]
    ) -> dict[str, Any]:
        pref_iso = _iso_utc(row["preferred_slot"]) or ""
        conf_iso = _iso_utc(row.get("confirmed_slot"))
        prop_iso = _iso_utc(row.get("proposed_slot"))
        created_iso = _iso_utc(row.get("created_at")) or ""
        updated_iso = _iso_utc(row.get("updated_at")) or ""
        return {
            "id": str(row["id"]),
            "code": str(row["code"]),
            "user_id": str(row["user_id"]),
            "profileId": str(row["profile_id"]),
            "profile_id": str(row["profile_id"]),
            "profileName": str(row["profile_name"]),
            "profile_name": str(row["profile_name"]),
            "profileAge": int(row["profile_age"]),
            "profile_age": int(row["profile_age"]),
            "careLevel": str(row["care_level"]),
            "care_level": str(row["care_level"]),
            "careNeeds": str(row.get("care_needs") or ""),
            "care_needs": str(row.get("care_needs") or ""),
            "facilityId": str(row["facility_id"]),
            "facility_id": str(row["facility_id"]),
            "facilityName": str(row["facility_name"]),
            "facility_name": str(row["facility_name"]),
            "serviceId": str(row["service_id"]),
            "service_id": str(row["service_id"]),
            "serviceName": str(row["service_name"]),
            "service_name": str(row["service_name"]),
            "consultType": str(row["consult_type"]),
            "consult_type": str(row["consult_type"]),
            "preferredSlot": pref_iso,
            "preferred_slot": pref_iso,
            "confirmedSlot": conf_iso,
            "confirmed_slot": conf_iso,
            "proposedSlot": prop_iso,
            "proposed_slot": prop_iso,
            "slotId": row.get("slot_id"),
            "slot_id": row.get("slot_id"),
            "contactName": str(row["contact_name"]),
            "contact_name": str(row["contact_name"]),
            "contactPhone": str(row["contact_phone"]),
            "contact_phone": str(row["contact_phone"]),
            "note": str(row.get("note") or ""),
            "status": str(row["status"]),
            "version": int(row["version"]),
            "lastReason": str(row.get("last_reason") or ""),
            "last_reason": str(row.get("last_reason") or ""),
            "reminderOptIn": bool(row.get("reminder_opt_in", False)),
            "reminder_opt_in": bool(row.get("reminder_opt_in", False)),
            "reminderId": row.get("reminder_id"),
            "reminder_id": row.get("reminder_id"),
            "createdAt": created_iso,
            "created_at": created_iso,
            "updatedAt": updated_iso,
            "updated_at": updated_iso,
            "events": events,
        }

    def _load_events_map(
        self, cur, request_ids: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        if not request_ids:
            return {}
        cur.execute(
            """
            SELECT * FROM care_request_events
             WHERE request_id = ANY(%s)
             ORDER BY id ASC
            """,
            (request_ids,),
        )
        out: dict[str, list[dict[str, Any]]] = {rid: [] for rid in request_ids}
        for r in cur.fetchall():
            out.setdefault(str(r["request_id"]), []).append(self._event_row_to_dict(r))
        return out

    def create_request(
        self,
        user_id: str,
        payload: dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> tuple[dict[str, Any], bool]:
        """Create a new care request or return existing on matching `idempotency_key`.

        Returns `(request_dict, created_new)`.
        """
        self.ensure_seeded()
        idem_key = (idempotency_key or "").strip() or None
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()

        if idem_key:
            with get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT * FROM care_requests
                         WHERE user_id = %s AND idempotency_key = %s
                        """,
                        (user_id, idem_key),
                    )
                    existing = cur.fetchone()
                    if existing:
                        if existing.get("idempotency_hash") and existing["idempotency_hash"] != payload_hash:
                            raise CodedHTTPException(409, "IDEMPOTENCY", "This key was already used with different content.")
                        ev_map = self._load_events_map(cur, [str(existing["id"])])
                        return (
                            self._request_row_to_dict(
                                existing, ev_map.get(str(existing["id"]), [])
                            ),
                            False,
                        )

        preferred_slot_raw = payload.get("preferred_slot") or payload.get("preferredSlot")
        if not validate_slot_is_future(preferred_slot_raw):
            raise CodedHTTPException(
                422,
                "FUTURE",
                "Preferred consultation slot must be in the future.",
            )
        preferred_dt = parse_iso_datetime(preferred_slot_raw)

        contact_phone = str(
            payload.get("contact_phone") or payload.get("contactPhone") or ""
        ).strip()
        if not validate_phone(contact_phone):
            raise CodedHTTPException(
                422,
                "PHONE",
                "Invalid contact phone number.",
            )

        facility_id = str(
            payload.get("facility_id") or payload.get("facilityId") or ""
        ).strip()
        service_id = str(
            payload.get("service_id") or payload.get("serviceId") or ""
        ).strip()
        facility = self.get_facility(facility_id)
        if not facility:
            raise CodedHTTPException(
                404, "facility_not_found", f"Facility {facility_id!r} not found."
            )
        if not facility.get("published", True):
            raise CodedHTTPException(409, "UNAVAILABLE", "Facility is not accepting public requests.")
        service = next(
            (s for s in facility["services"] if s["id"] == service_id), None
        )
        if not service:
            raise CodedHTTPException(
                404, "service_not_found", f"Service {service_id!r} not found."
            )
        if not service.get("accepting", True):
            raise CodedHTTPException(409, "UNAVAILABLE", "Service is not accepting new requests.")

        req_id = f"req-{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        contact_name = str(
            payload.get("contact_name") or payload.get("contactName") or user_id
        ).strip()
        note = str(payload.get("note") or "").strip()
        slot_id = payload.get("slot_id") or payload.get("slotId") or None
        if slot_id:
            slots = self.list_slots(facility_id)
            chosen_slot = next((s for s in slots if s["id"] == slot_id), None)
            if not chosen_slot or parse_iso_datetime(chosen_slot["startsAt"]) != preferred_dt or chosen_slot["isFull"]:
                raise CodedHTTPException(409, "SLOT_FULL", "The selected slot is unavailable or does not match the requested time.")
        reminder_opt_in = bool(
            payload.get("reminder_opt_in")
            if payload.get("reminder_opt_in") is not None
            else payload.get("reminderOptIn", False)
        )

        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Re-check idempotency inside transaction
                if idem_key:
                    cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (user_id + ":" + idem_key,))
                    cur.execute(
                        """
                        SELECT * FROM care_requests
                         WHERE user_id = %s AND idempotency_key = %s
                        """,
                        (user_id, idem_key),
                    )
                    existing = cur.fetchone()
                    if existing:
                        if existing.get("idempotency_hash") and existing["idempotency_hash"] != payload_hash:
                            raise CodedHTTPException(409, "IDEMPOTENCY", "This key was already used with different content.")
                        ev_map = self._load_events_map(cur, [str(existing["id"])])
                        return (
                            self._request_row_to_dict(
                                existing, ev_map.get(str(existing["id"]), [])
                            ),
                            False,
                        )

                cur.execute("SELECT COUNT(*) AS cnt FROM care_requests")
                seq = int((cur.fetchone() or {"cnt": 0})["cnt"]) + 101
                code = f"CC-2026-{seq:04d}-{uuid.uuid4().hex[:3].upper()}"

                cur.execute(
                    """
                    INSERT INTO care_requests (
                        id, code, user_id, profile_id, profile_name, profile_age,
                        care_level, care_needs, facility_id, facility_name,
                        service_id, service_name, consult_type, preferred_slot,
                        slot_id, contact_name, contact_phone, note,
                        status, version, last_reason, idempotency_key,
                        reminder_opt_in, created_at, updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        'PENDING', 1, '', %s,
                        %s, %s, %s
                    )
                    RETURNING *
                    """,
                    (
                        req_id,
                        code,
                        user_id,
                        str(payload.get("profile_id") or payload.get("profileId") or "elder-1"),
                        str(payload.get("profile_name") or payload.get("profileName") or "Người cao tuổi"),
                        int(payload.get("profile_age") if payload.get("profile_age") is not None else payload.get("profileAge", 70)),
                        str(payload.get("care_level") or payload.get("careLevel") or "L1"),
                        str(payload.get("care_needs") or payload.get("careNeeds") or ""),
                        facility["id"],
                        facility["name"],
                        service["id"],
                        service["name"],
                        str(payload.get("consult_type") or payload.get("consultType") or "visit"),
                        preferred_dt,
                        slot_id,
                        contact_name,
                        contact_phone,
                        note,
                        idem_key,
                        reminder_opt_in,
                        now,
                        now,
                    ),
                )
                row = cur.fetchone()
                if idem_key:
                    cur.execute("UPDATE care_requests SET idempotency_hash = %s WHERE id = %s", (payload_hash, req_id))
                cur.execute(
                    """
                    INSERT INTO care_request_events (
                        request_id, at, actor_role, actor_name, action,
                        from_status, to_status, note, slot
                    )
                    VALUES (%s, %s, 'caregiver', %s, 'create', 'PENDING', 'PENDING', %s, %s)
                    RETURNING *
                    """,
                    (
                        req_id,
                        now,
                        contact_name,
                        note or "Gửi yêu cầu đặt lịch tư vấn mới.",
                        preferred_dt,
                    ),
                )
                ev_row = cur.fetchone()
            conn.commit()

        return self._request_row_to_dict(row, [self._event_row_to_dict(ev_row)]), True

    def is_facility_member(
        self, user_id: str, facility_id: str, require_manager: bool = False
    ) -> bool:
        if not user_id or not facility_id:
            return False
        with get_conn() as conn:
            with conn.cursor() as cur:
                if require_manager:
                    cur.execute(
                        """
                        SELECT 1 FROM care_facility_members
                         WHERE facility_id = %s AND user_id = %s AND member_role = 'manager'
                        """,
                        (facility_id, user_id),
                    )
                else:
                    cur.execute(
                        """
                        SELECT 1 FROM care_facility_members
                         WHERE facility_id = %s AND user_id = %s
                        """,
                        (facility_id, user_id),
                    )
                return cur.fetchone() is not None

    def list_requests(
        self,
        user_id: str,
        scope: str = "mine",
        facility_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        self.ensure_seeded()
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if scope == "facility":
                    target_fac = (facility_id or "").strip()
                    if not target_fac:
                        memberships = self.get_member_facilities(user_id)
                        if not memberships:
                            raise CodedHTTPException(
                                403,
                                "facility_forbidden",
                                "You are not a staff member of any facility.",
                            )
                        target_fac = memberships[0]["facility_id"]
                    elif not self.is_facility_member(user_id, target_fac):
                        raise CodedHTTPException(
                            403,
                            "facility_forbidden",
                            "You are not a staff member of this facility.",
                        )
                    sql = "SELECT * FROM care_requests WHERE facility_id = %s"
                    params: list[Any] = [target_fac]
                else:
                    sql = "SELECT * FROM care_requests WHERE user_id = %s"
                    params = [user_id]

                if status and status != "ALL":
                    sql += " AND status = %s"
                    params.append(status)

                sql += " ORDER BY updated_at DESC, created_at DESC"
                cur.execute(sql, params)
                rows = cur.fetchall()
                ev_map = self._load_events_map(cur, [str(r["id"]) for r in rows])

        return [
            self._request_row_to_dict(r, ev_map.get(str(r["id"]), [])) for r in rows
        ]

    def get_request(self, request_id: str, user_id: str) -> dict[str, Any]:
        self.ensure_seeded()
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM care_requests WHERE id = %s", (request_id,))
                row = cur.fetchone()
                if not row:
                    raise CodedHTTPException(
                        404, "request_not_found", f"Request {request_id!r} not found."
                    )
                is_owner = str(row["user_id"]) == user_id
                is_staff = self.is_facility_member(user_id, str(row["facility_id"]))
                if not is_owner and not is_staff:
                    raise CodedHTTPException(
                        403,
                        "request_forbidden",
                        "You do not have permission to view this care request.",
                    )
                ev_map = self._load_events_map(cur, [request_id])
                return self._request_row_to_dict(row, ev_map.get(request_id, []))

    def apply_action(
        self,
        request_id: str,
        user_id: str,
        action: str,
        expected_version: int,
        note: str = "",
        proposed_slot: Optional[str] = None,
        slot_id: Optional[str] = None,
        actor_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute a state transition with server-side RBAC, reason/slot checks, and 409 conflict lock."""
        self.ensure_seeded()
        cleaned_note = (note or "").strip()

        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM care_requests WHERE id = %s FOR UPDATE",
                    (request_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise CodedHTTPException(
                        404, "request_not_found", f"Request {request_id!r} not found."
                    )

                # Determine actor role from server-side membership / ownership
                if action in STAFF_ACTIONS:
                    cur.execute(
                        """
                        SELECT member_role FROM care_facility_members
                         WHERE facility_id = %s AND user_id = %s
                        """,
                        (row["facility_id"], user_id),
                    )
                    if not cur.fetchone():
                        raise CodedHTTPException(
                            403,
                            "facility_forbidden",
                            "Only staff of this facility can perform this action.",
                        )
                    actor_role = "staff"
                    resolved_actor_name = (
                        actor_name or f"Điều phối viên {row['facility_name']}"
                    )
                elif action in CAREGIVER_ACTIONS:
                    if str(row["user_id"]) != user_id:
                        raise CodedHTTPException(
                            403,
                            "not_request_owner",
                            "Only the creator of this request can perform this action.",
                        )
                    actor_role = "caregiver"
                    resolved_actor_name = actor_name or str(row["contact_name"])
                else:
                    raise CodedHTTPException(409, "ACTION", f"Unsupported action: {action}")

                # Check optimistic version before or alongside state transition
                if int(row["version"]) != int(expected_version):
                    raise CodedHTTPException(
                        409,
                        "CONFLICT",
                        "Request version mismatch; the record was modified by another session.",
                        {"current_version": int(row["version"])},
                    )

                next_status, err_code = resolve_transition(
                    str(row["status"]), action, actor_role
                )
                if err_code or not next_status:
                    raise CodedHTTPException(
                        409,
                        "ACTION",
                        f"Action {action!r} is not allowed from status {row['status']!r} for role {actor_role!r}.",
                    )

                if not validate_reason(action, cleaned_note):
                    raise CodedHTTPException(
                        422,
                        "REASON",
                        "A reason of at least 5 characters is required for this action.",
                    )

                proposed_dt = None
                if action == "propose_slot":
                    if not validate_slot_is_future(proposed_slot):
                        raise CodedHTTPException(
                            422,
                            "FUTURE",
                            "Proposed consultation slot must be in the future.",
                        )
                    proposed_dt = parse_iso_datetime(proposed_slot)

                now = datetime.now(timezone.utc)
                confirmed_dt = row.get("confirmed_slot")
                new_proposed_dt = row.get("proposed_slot")
                event_slot_dt = None
                effective_slot_id = slot_id or row.get("slot_id")

                if action == "confirm":
                    confirmed_dt = row.get("proposed_slot") or row["preferred_slot"]
                    new_proposed_dt = None
                    event_slot_dt = confirmed_dt
                elif action == "accept_slot":
                    confirmed_dt = row.get("proposed_slot") or row["preferred_slot"]
                    new_proposed_dt = None
                    event_slot_dt = confirmed_dt
                elif action == "propose_slot":
                    new_proposed_dt = proposed_dt
                    event_slot_dt = proposed_dt
                    confirmed_dt = None
                    effective_slot_id = slot_id

                if next_status == "CONFIRMED" and (not confirmed_dt or confirmed_dt <= now):
                    raise CodedHTTPException(422, "FUTURE", "The confirmed slot must be in the future.")
                if action == "complete" and (not confirmed_dt or confirmed_dt > now):
                    raise CodedHTTPException(409, "FUTURE", "Consultation cannot be completed before its scheduled time.")

                # Handle capacity slot booking / release
                if next_status == "CONFIRMED" and effective_slot_id and str(row["status"]) != "CONFIRMED":
                    cur.execute(
                        """
                        UPDATE care_consult_slots
                           SET booked_count = booked_count + 1
                         WHERE id = %s AND facility_id = %s AND booked_count < capacity
                        RETURNING starts_at
                        """,
                        (effective_slot_id, row["facility_id"]),
                    )
                    booked_slot = cur.fetchone()
                    if not booked_slot:
                        raise CodedHTTPException(
                            409,
                            "SLOT_FULL",
                            "Selected consultation slot is full or unavailable.",
                        )
                    confirmed_dt = booked_slot["starts_at"]
                    event_slot_dt = confirmed_dt
                elif (
                    next_status in ("CANCELLED", "REJECTED", "RESCHEDULE_PROPOSED")
                    and str(row["status"]) == "CONFIRMED"
                    and row.get("slot_id")
                ):
                    cur.execute(
                        """
                        UPDATE care_consult_slots
                           SET booked_count = GREATEST(0, booked_count - 1)
                         WHERE id = %s
                        """,
                        (row["slot_id"],),
                    )

                last_reason = (
                    cleaned_note
                    if action in ("propose_slot", "reject", "cancel", "staff_cancel")
                    else str(row.get("last_reason") or "")
                )

                cur.execute(
                    """
                    UPDATE care_requests
                       SET status = %s,
                           version = version + 1,
                           confirmed_slot = %s,
                           proposed_slot = %s,
                           slot_id = %s,
                           last_reason = %s,
                           updated_at = %s
                     WHERE id = %s AND version = %s
                    RETURNING *
                    """,
                    (
                        next_status,
                        confirmed_dt,
                        new_proposed_dt,
                        effective_slot_id,
                        last_reason,
                        now,
                        request_id,
                        expected_version,
                    ),
                )
                updated_row = cur.fetchone()
                if not updated_row:
                    raise CodedHTTPException(
                        409,
                        "CONFLICT",
                        "Request version mismatch during update.",
                    )

                # Store the opted-in reminder in the same transaction as the
                # confirmed request. A deterministic ID prevents duplicate reminders.
                reminder_id = str(row.get("reminder_id") or f"care-{request_id}")
                if next_status == "CONFIRMED" and row.get("reminder_opt_in"):
                    local_slot = confirmed_dt.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
                    cur.execute("""INSERT INTO one_time_reminders(id,user_id,date,time,title,type,details,status,is_active,created_at)
                        VALUES (%s,%s,%s,%s,%s,'appointment',%s,'waiting',TRUE,%s)
                        ON CONFLICT(id) DO UPDATE SET date=EXCLUDED.date,time=EXCLUDED.time,status='waiting',is_active=TRUE""",
                        (reminder_id,row["user_id"],local_slot.date(),local_slot.strftime("%H:%M"),f"Tư vấn: {row['facility_name']}",row["code"],now))
                    cur.execute("UPDATE care_requests SET reminder_id=%s WHERE id=%s", (reminder_id,request_id))
                    updated_row["reminder_id"] = reminder_id
                elif next_status in ("CANCELLED", "REJECTED", "RESCHEDULE_PROPOSED") and row.get("reminder_id"):
                    cur.execute("DELETE FROM one_time_reminders WHERE id=%s AND user_id=%s", (reminder_id,row["user_id"]))
                    cur.execute("UPDATE care_requests SET reminder_id=NULL WHERE id=%s", (request_id,))
                    updated_row["reminder_id"] = None

                default_notes = {
                    "start_review": "Cơ sở bắt đầu xem xét yêu cầu.",
                    "staff_cancel": "Cơ sở hủy yêu cầu tư vấn.",
                    "confirm": "Cơ sở xác nhận tiếp nhận lịch tư vấn.",
                    "propose_slot": "Cơ sở đề xuất khung giờ tư vấn mới.",
                    "reject": "Cơ sở từ chối yêu cầu.",
                    "complete": "Hoàn tất buổi tư vấn.",
                    "accept_slot": "Gia đình đồng ý khung giờ mới.",
                    "cancel": "Gia đình hủy yêu cầu.",
                }
                cur.execute(
                    """
                    INSERT INTO care_request_events (
                        request_id, at, actor_role, actor_name, action,
                        from_status, to_status, note, slot
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        request_id,
                        now,
                        actor_role,
                        resolved_actor_name,
                        action,
                        row["status"],
                        next_status,
                        cleaned_note or default_notes.get(action, ""),
                        event_slot_dt,
                    ),
                )
                ev_map = self._load_events_map(cur, [request_id])
            conn.commit()

        return self._request_row_to_dict(updated_row, ev_map.get(request_id, []))

    def set_request_reminder_id(self, request_id: str, reminder_id: str) -> None:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE care_requests SET reminder_id = %s WHERE id = %s",
                    (reminder_id, request_id),
                )
            conn.commit()

    def create_feedback(
        self,
        request_id: str,
        user_id: str,
        rating: int,
        tags: list[str],
        comment: str,
    ) -> dict[str, Any]:
        """Submit post-consultation feedback (only allowed when request is COMPLETED)."""
        if not 1 <= int(rating) <= 5:
            raise CodedHTTPException(422, "INVALID_RATING", "Rating must be between 1 and 5.")
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM care_requests WHERE id = %s",
                    (request_id,),
                )
                req = cur.fetchone()
                if not req:
                    raise CodedHTTPException(404, "request_not_found", "Care request not found.")
                if str(req["user_id"]) != user_id:
                    raise CodedHTTPException(
                        403, "not_request_owner", "Only the request creator can leave feedback."
                    )
                if str(req["status"]) != "COMPLETED":
                    raise CodedHTTPException(
                        409,
                        "FEEDBACK_NOT_COMPLETED",
                        "Feedback can only be submitted after consultation is COMPLETED.",
                    )
                cur.execute(
                    "SELECT id FROM care_feedback WHERE request_id = %s",
                    (request_id,),
                )
                if cur.fetchone():
                    raise CodedHTTPException(
                        409,
                        "FEEDBACK_EXISTS",
                        "Feedback has already been submitted for this request.",
                    )
                fb_id = f"fb-{uuid.uuid4().hex[:10]}"
                now = datetime.now(timezone.utc)
                cur.execute(
                    """
                    INSERT INTO care_feedback (
                        id, request_id, facility_id, user_id, rating, tags, comment,
                        moderation_status, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, 'pending', %s)
                    RETURNING *
                    """,
                    (
                        fb_id,
                        request_id,
                        req["facility_id"],
                        user_id,
                        int(rating),
                        json.dumps(tags or []),
                        (comment or "").strip(),
                        now,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return self._feedback_row_to_dict(row)

    def _feedback_row_to_dict(self, r: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(r["id"]),
            "request_id": str(r["request_id"]),
            "requestId": str(r["request_id"]),
            "facility_id": str(r["facility_id"]),
            "facilityId": str(r["facility_id"]),
            "user_id": str(r["user_id"]),
            "userId": str(r["user_id"]),
            "rating": int(r["rating"]),
            "tags": list(r.get("tags") or []),
            "comment": str(r.get("comment") or ""),
            "moderation_status": str(r["moderation_status"]),
            "moderationStatus": str(r["moderation_status"]),
            "moderated_by": r.get("moderated_by"),
            "moderatedBy": r.get("moderated_by"),
            "moderated_at": _iso_utc(r.get("moderated_at")),
            "moderatedAt": _iso_utc(r.get("moderated_at")),
            "created_at": _iso_utc(r.get("created_at")) or "",
            "createdAt": _iso_utc(r.get("created_at")) or "",
        }

    def list_facility_feedback(
        self, facility_id: str, include_unapproved: bool = False, owner_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if include_unapproved:
                    cur.execute(
                        """
                        SELECT * FROM care_feedback
                         WHERE facility_id = %s
                         ORDER BY created_at DESC
                        """,
                        (facility_id,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT * FROM care_feedback
                         WHERE facility_id = %s AND (moderation_status = 'approved' OR user_id = %s)
                         ORDER BY created_at DESC
                        """,
                        (facility_id, owner_id),
                    )
                return [self._feedback_row_to_dict(r) for r in cur.fetchall()]

    def moderate_feedback(
        self, feedback_id: str, user_id: str, moderation_status: str
    ) -> dict[str, Any]:
        if moderation_status not in ("approved", "rejected", "pending"):
            raise CodedHTTPException(
                422, "INVALID_MODERATION_STATUS", "Invalid moderation status."
            )
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM care_feedback WHERE id = %s",
                    (feedback_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise CodedHTTPException(404, "feedback_not_found", "Feedback not found.")
                if not self.is_facility_member(
                    user_id, str(row["facility_id"]), require_manager=True
                ):
                    raise CodedHTTPException(
                        403,
                        "manager_only",
                        "Only a facility manager can moderate consultation feedback.",
                    )
                now = datetime.now(timezone.utc)
                cur.execute(
                    """
                    UPDATE care_feedback
                       SET moderation_status = %s,
                           moderated_by = %s,
                           moderated_at = %s
                     WHERE id = %s
                    RETURNING *
                    """,
                    (moderation_status, user_id, now, feedback_id),
                )
                updated = cur.fetchone()
            conn.commit()
        return self._feedback_row_to_dict(updated)


_care_connect_store: Optional[CareConnectStore] = None
_store_lock = threading.Lock()


def get_care_connect_store() -> CareConnectStore:
    global _care_connect_store
    if _care_connect_store is None:
        with _store_lock:
            if _care_connect_store is None:
                _care_connect_store = CareConnectStore()
    return _care_connect_store


def reset_care_connect_store() -> None:
    """Reset singleton between tests (registered in conftest._SINGLETON_RESETS)."""
    global _care_connect_store
    with _store_lock:
        _care_connect_store = None
