"""Unit tests for Care Connect explainable recommendation engine (4.3.2)."""

import unittest

from backend.core.features.care_connect.recommend import (
    RECOMMEND_RULES_VERSION,
    rank_facilities,
    score_facility,
)
from backend.core.features.care_connect.store import DEFAULT_FACILITIES_SEED


class TestCareConnectRecommend(unittest.TestCase):
    def test_perfect_match_scores_100(self):
        an_nhien = DEFAULT_FACILITIES_SEED[0]
        res = score_facility(
            an_nhien,
            care_level="L2",
            required_tags=["dementia", "night_monitoring"],
            preferred_district="Quận 7, TP.HCM",
            max_distance_km=5.0,
            budget_max=15000000,
            budget_unit="month",
            preferred_type="nursing_home",
        )
        self.assertEqual(res["score"], 100)
        self.assertEqual(res["rules_version"], RECOMMEND_RULES_VERSION)
        self.assertEqual(res["missing"], [])
        self.assertTrue(len(res["reasons"]) >= 4)

    def test_unpublished_price_zero_is_flagged_as_missing_not_free(self):
        unpublished_fac = {
            **DEFAULT_FACILITIES_SEED[0],
            "id": "fac-unpub",
            "price_from": 0,
            "price_unit": "contact",
        }
        res = score_facility(
            unpublished_fac,
            care_level="L2",
            required_tags=["dementia"],
            budget_max=20000000,
            budget_unit="month",
        )
        self.assertEqual(res["score"], 85)
        self.assertTrue(any("Chưa công bố giá" in m for m in res["missing"]))

    def test_mismatched_price_unit_is_not_compared_numerically(self):
        binh_an = DEFAULT_FACILITIES_SEED[1]  # price_unit = 'day', price_from = 450000
        res = score_facility(
            binh_an,
            care_level="L1",
            required_tags=["companionship"],
            budget_max=10000000,
            budget_unit="month",
        )
        self.assertTrue(any("Đơn vị tính giá" in m for m in res["missing"]))

    def test_rank_facilities_sorts_by_score_then_distance(self):
        ranked = rank_facilities(
            DEFAULT_FACILITIES_SEED,
            care_level="L3",
            required_tags=["stroke_rehab", "physiotherapy"],
            budget_max=15000000,
            budget_unit="month",
            preferred_type="rehab",
        )
        self.assertEqual(len(ranked), 4)
        self.assertEqual(ranked[0]["facility_id"], "phuoc-loc")
        self.assertGreater(ranked[0]["score"], ranked[-1]["score"])


if __name__ == "__main__":
    unittest.main()
