"""Unit tests for Care Connect validation helpers (future slot, phone, reason length)."""

import unittest
from datetime import datetime, timedelta, timezone

from backend.core.features.care_connect.validation import (
    validate_phone,
    validate_reason,
    validate_slot_is_future,
)


class TestCareConnectValidation(unittest.TestCase):
    def test_validate_slot_is_future(self):
        now = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)
        future_iso = (now + timedelta(hours=2)).isoformat()
        past_iso = (now - timedelta(hours=2)).isoformat()
        within_grace = (now - timedelta(seconds=30)).isoformat()

        self.assertTrue(validate_slot_is_future(future_iso, now=now))
        self.assertTrue(validate_slot_is_future(within_grace, now=now, grace_seconds=60))
        self.assertFalse(validate_slot_is_future(past_iso, now=now))
        self.assertFalse(validate_slot_is_future("not-a-date", now=now))
        self.assertFalse(validate_slot_is_future("", now=now))

    def test_validate_phone(self):
        self.assertTrue(validate_phone("0903 123 456"))
        self.assertTrue(validate_phone("+84 912-345-678"))
        self.assertTrue(validate_phone("028 3876 5412"))
        self.assertFalse(validate_phone("12345"))
        self.assertFalse(validate_phone("abc"))
        self.assertFalse(validate_phone(""))

    def test_validate_reason(self):
        for act in ("propose_slot", "reject", "cancel"):
            self.assertFalse(validate_reason(act, ""))
            self.assertFalse(validate_reason(act, "1234"))
            self.assertTrue(validate_reason(act, "Bác sĩ bận đột xuất"))

        for act in ("confirm", "complete", "accept_slot"):
            self.assertTrue(validate_reason(act, ""))


if __name__ == "__main__":
    unittest.main()
