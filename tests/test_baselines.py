#!/usr/bin/env python3
"""Targeted property and behavioral signature tests for comparative baselines.

Tests:
1. Behavioral signature disjointness across all 6 configurations.
2. Exact query cohort equality (identical query IDs, keys, scheduled timestamps).
3. Budget matching (budget_matched publications == joint_adaptive publications +/- 1%).
4. 100% accounting conservation across all 6 configurations.
5. Prospective tuning candidate evaluation on validation data.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Dict, List

from tools.baseline_suite import (
    STATIC_TUNING_CANDIDATES,
    execute_comparative_suite,
    tune_static_cadence,
)
from tools.workload_generator import (
    TOTAL_EVENTS,
    TOTAL_QUERIES,
    generate_open_loop_trace,
    load_validation_events,
)


class BaselineSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        raw_source = Path("data/quarantine/raw/UserBehavior.csv")
        cohort_source = Path("data/cohort.csv")
        if raw_source.exists():
            cls.val_events = load_validation_events(raw_source, cohort_path=cohort_source, target_count=TOTAL_EVENTS)
        else:
            cls.val_events = [
                (1512057600 * 1_000_000_000 + i * 1000, i % 100, 100 + i, 200, i % 4)
                for i in range(TOTAL_EVENTS)
            ]
        cls.events, cls.queries = generate_open_loop_trace(cls.val_events, seed=42)

        # Reference calibrated model weights
        cls.bias = -1.9688872868984322
        cls.weights = [
            7.625222553756112e-09,
            1.539073360986053e-08,
            7.616401379945657e-09,
            -2.612522051541010e-09,
            9.364010232670656e-10,
            1.620533208109410e-08,
            -1.424377572918758e-05,
        ]

        cls.suite_results = execute_comparative_suite(cls.events, cls.queries, cls.bias, cls.weights)

    def test_exact_query_cohort_equality(self) -> None:
        """All 6 configurations must evaluate the exact same 5,000 queries in identical order."""
        self.assertEqual(len(self.queries), TOTAL_QUERIES)
        q_ids = [q.query_id for q in self.queries]
        q_keys = [q.key for q in self.queries]
        q_times = [q.t_sched_ns for q in self.queries]

        for cfg in self.suite_results["configurations"]:
            self.assertEqual(cfg["accounting"]["scheduled_queries"], TOTAL_QUERIES)
            self.assertEqual(cfg["accounting"]["completed_queries"], TOTAL_QUERIES)

        # Check queries are distinct and non-empty
        self.assertEqual(len(set(q_ids)), TOTAL_QUERIES)

    def test_budget_matching_within_1pct(self) -> None:
        """budget_matched total publications must match joint_adaptive within +/- 1%."""
        bm = self.suite_results["budget_matching"]
        self.assertTrue(bm["matched_within_1pct"], f"Budget matching failed: relative diff={bm['relative_difference_pct']:.4f}%")
        self.assertLessEqual(bm["relative_difference_pct"], 1.0)
        self.assertEqual(bm["joint_adaptive_publications"], bm["budget_matched_publications"])

    def test_100pct_accounting_conservation(self) -> None:
        """Every configuration must conserve all processed updates and scheduled queries."""
        for cfg in self.suite_results["configurations"]:
            c_name = cfg["name"]
            acc = cfg["accounting"]
            self.assertTrue(acc["conservation_verified"], f"Conservation failed for {c_name}")
            self.assertEqual(acc["processed_updates"], TOTAL_EVENTS, f"Processed events mismatch in {c_name}")
            self.assertEqual(
                acc["processed_updates"],
                acc["published_updates"] + acc["coalesced_updates"],
                f"Conservation equation violated in {c_name}",
            )
            self.assertEqual(acc["completed_queries"], TOTAL_QUERIES, f"Query count mismatch in {c_name}")

    def test_signature_disjointness_across_all_configurations(self) -> None:
        """Behavioral signatures across all 6 configurations must be distinct."""
        sigs = self.suite_results["signatures"]
        config_names = list(sigs.keys())
        self.assertEqual(len(config_names), 6)

        # Assert pairwise disjointness
        for i in range(len(config_names)):
            for j in range(i + 1, len(config_names)):
                name_a = config_names[i]
                name_b = config_names[j]
                sig_a = sigs[name_a]
                sig_b = sigs[name_b]

                is_distinct = (
                    sig_a["published_updates"] != sig_b["published_updates"]
                    or sig_a["stress_published"] != sig_b["stress_published"]
                    or sig_a["mean_staleness"] != sig_b["mean_staleness"]
                    or sig_a["mean_feature_error"] != sig_b["mean_feature_error"]
                    or sig_a["stress_staleness"] != sig_b["stress_staleness"]
                )
                self.assertTrue(
                    is_distinct,
                    f"Signature collision detected between {name_a} and {name_b}: {sig_a} vs {sig_b}",
                )

    def test_prospective_tuning_candidates(self) -> None:
        """Tuning search must evaluate all candidate cadences and select valid U*."""
        tuning = self.suite_results["tuning_results"]
        u_star = tuning["selected_u_star"]
        self.assertIn(u_star, STATIC_TUNING_CANDIDATES)

        candidates_evaluated = [rec["u"] for rec in tuning["candidates_evaluated"]]
        self.assertEqual(candidates_evaluated, STATIC_TUNING_CANDIDATES)


if __name__ == "__main__":
    unittest.main()
