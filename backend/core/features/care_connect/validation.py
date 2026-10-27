"""Validation helpers for Care Connect requests and actions."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from backend.core.features.care_connect.model import REASON_REQUIRED_ACTIONS

_PHONE_RE = re.compile(r"^(0|\+84)[0-9]{8,10}$")
MIN_REASON_LEN = 5


def parse_iso_datetime(value: Union[str, datetime, None]) -> Optional[datetime]:
    """Parse an ISO-8601 string or datetime into an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_slot_is_future(
    slot: Union[str, datetime, None],
    now: Optional[datetime] = None,
    grace_seconds: int = 60,
) -> bool:
    """Return True if `slot` parses as a valid datetime and is not in the past
    (allowing `grace_seconds` of clock skew).
    """
    dt = parse_iso_datetime(slot)
    if dt is None:
        return False
    ref = parse_iso_datetime(now) if now is not None else datetime.now(timezone.utc)
    if ref is None:
        ref = datetime.now(timezone.utc)
    return dt >= (ref - timedelta(seconds=grace_seconds))


def validate_phone(phone: Optional[str]) -> bool:
    """Validate Vietnamese phone number format after stripping spaces, dots, and dashes."""
    if not phone:
        return False
    cleaned = re.sub(r"[\s.\-()]+", "", str(phone).strip())
    return bool(_PHONE_RE.match(cleaned))


def validate_reason(action: str, note: Optional[str]) -> bool:
    """Return True if `action` does not require a reason or `note` has >= 5 chars."""
    if action not in REASON_REQUIRED_ACTIONS:
        return True
    cleaned = (note or "").strip()
    return len(cleaned) >= MIN_REASON_LEN
