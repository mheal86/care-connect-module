"""Unit tests for Care Connect state machine transitions and role permissions."""

import unittest

from backend.core.features.care_connect.model import (
    ALLOWED_TRANSITIONS,
    CAREGIVER_ACTIONS,
    STAFF_ACTIONS,
    TERMINAL_STATUSES,
    resolve_transition,
)


class TestCareConnectModel(unittest.TestCase):
    def test_valid_staff_transitions(self):
        self.assertEqual(resolve_transition("PENDING", "confirm", "staff"), ("CONFIRMED", None))
        self.assertEqual(
            resolve_transition("PENDING", "propose_slot", "staff"),
            ("RESCHEDULE_PROPOSED", None),
        )
        self.assertEqual(resolve_transition("PENDING", "reject", "staff"), ("REJECTED", None))
        self.assertEqual(resolve_transition("CONFIRMED", "complete", "staff"), ("COMPLETED", None))
        self.assertEqual(
            resolve_transition("CONFIRMED", "propose_slot", "staff"),
            ("RESCHEDULE_PROPOSED", None),
        )
        self.assertEqual(
            resolve_transition("RESCHEDULE_PROPOSED", "propose_slot", "staff"),
            ("RESCHEDULE_PROPOSED", None),
        )
        self.assertEqual(
            resolve_transition("RESCHEDULE_PROPOSED", "reject", "staff"),
            ("REJECTED", None),
        )

    def test_valid_caregiver_transitions(self):
        self.assertEqual(resolve_transition("PENDING", "cancel", "caregiver"), ("CANCELLED", None))
        self.assertEqual(
            resolve_transition("RESCHEDULE_PROPOSED", "accept_slot", "caregiver"),
            ("CONFIRMED", None),
        )
        self.assertEqual(
            resolve_transition("RESCHEDULE_PROPOSED", "cancel", "caregiver"),
            ("CANCELLED", None),
        )
        self.assertEqual(
            resolve_transition("CONFIRMED", "cancel", "caregiver"),
            ("CANCELLED", None),
        )

    def test_cross_role_actions_are_rejected(self):
        for action in STAFF_ACTIONS:
            next_st, err = resolve_transition("PENDING", action, "caregiver")
            self.assertIsNone(next_st)
            self.assertEqual(err, "ACTION")

        for action in CAREGIVER_ACTIONS:
            next_st, err = resolve_transition("RESCHEDULE_PROPOSED", action, "staff")
            self.assertIsNone(next_st)
            self.assertEqual(err, "ACTION")

    def test_terminal_statuses_reject_all_actions(self):
        all_actions = list(STAFF_ACTIONS | CAREGIVER_ACTIONS)
        for status in TERMINAL_STATUSES:
            for role in ("staff", "caregiver"):
                for act in all_actions:
                    next_st, err = resolve_transition(status, act, role)
                    self.assertIsNone(next_st)
                    self.assertEqual(err, "ACTION")


if __name__ == "__main__":
    unittest.main()
