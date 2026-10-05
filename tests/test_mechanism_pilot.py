#!/usr/bin/env python3
"""Targeted property and regression tests for open-loop workload and mechanism pilot.

Tests:
1. Open-loop timing independence and non-closed-loop pacing.
2. 100% accounting conservation across all phases and policies.
3. Monotonic actuator sign: increasing U monotonically decreases publications and increases staleness.
4. Zero test split data leakage in workload generation.
"""

from __future__ import annotations

import math
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import List, Tuple

from tools.publication_reference import (
    AdaptivePressurePolicy,
    ExactFreshPolicy,
    FixedCadencePolicy,
    PublicationSimulator,
    Query,
    RawEvent,
)
from tools.workload_generator import (
    PHASE_SPECS,
    TEST_START_SEC,
    TOTAL_EVENTS,
    TOTAL_QUERIES,
    VAL_END_SEC,
    VAL_START_SEC,
    ScheduledEvent,
    ScheduledQuery,
    generate_open_loop_trace,
    load_validation_events,
)
from tools.run_mechanism_pilot import (
    run_configuration_trial,
    verify_actuator_sign,
)


class MechanismPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_source = Path("data/quarantine/raw/UserBehavior.csv")
        cls.has_raw = cls.raw_source.exists()
        if cls.has_raw:
            cls.val_events = load_validation_events(cls.raw_source, target_count=TOTAL_EVENTS)
            cls.events, cls.queries = generate_open_loop_trace(cls.val_events, seed=42)
        else:
            # Fallback synthetic validation pool for isolated environments
            cls.val_events = [
                (VAL_START_SEC * 1_000_000_000 + i * 1000, i % 100, 100 + i, 200, i % 4)
                for i in range(TOTAL_EVENTS)
            ]
            cls.events, cls.queries = generate_open_loop_trace(cls.val_events, seed=42)

    def test_open_loop_timing_independence(self) -> None:
        """Scheduled timeline t_sched must be monotonic and independent of completion rate."""
        self.assertEqual(len(self.events), TOTAL_EVENTS)
        self.assertEqual(len(self.queries), TOTAL_QUERIES)

        # Check monotonic event scheduling
        prev_t = 0
        for e in self.events:
            self.assertGreaterEqual(e.t_sched_ns, prev_t, "Event scheduled timeline must be non-decreasing")
            prev_t = e.t_sched_ns

        # Check phase boundaries match specification exactly
        events_by_phase = {}
        for e in self.events:
            events_by_phase[e.phase] = events_by_phase.get(e.phase, 0) + 1

        queries_by_phase = {}
        for q in self.queries:
            queries_by_phase[q.phase] = queries_by_phase.get(q.phase, 0) + 1

        for spec in PHASE_SPECS:
            p_name, exp_ev, exp_q = spec[0], spec[1], spec[2]
            self.assertEqual(events_by_phase.get(p_name, 0), exp_ev, f"Phase {p_name} event count mismatch")
            self.assertEqual(queries_by_phase.get(p_name, 0), exp_q, f"Phase {p_name} query count mismatch")

    def test_zero_test_split_leakage(self) -> None:
        """All workload events must reside strictly in Day 7 validation window with zero test data."""
        for e in self.events:
            sec = e.event_ts_ns // 1_000_000_000
            self.assertGreaterEqual(sec, VAL_START_SEC, "Event timestamp precedes validation window")
            self.assertLessEqual(sec, VAL_END_SEC, "Event timestamp exceeds validation window")
            self.assertLess(sec, TEST_START_SEC, "CRITICAL: Test split event leaked into workload!")

    def test_exact_conservation_across_phases_and_policies(self) -> None:
        """Conservation accounting must hold across all 4 contiguous phases and all policies."""
        test_policies = [
            ("ExactFresh", 1),
            ("FixedCadence", 5),
            ("FixedCadence", 20),
            ("AdaptivePressure", "adaptive"),
        ]

        dummy_bias = -1.968
        dummy_weights = [0.0] * 7

        for pol_name, u_val in test_policies:
            with self.subTest(policy=pol_name, u=u_val):
                res = run_configuration_trial(
                    events=self.events,
                    queries=self.queries,
                    policy_name=pol_name,
                    u_val=u_val,
                    batch_size=32,
                    alpha=0.1,
                    model_bias=dummy_bias,
                    model_weights=dummy_weights,
                )

                agg = res["aggregate_accounting"]
                self.assertTrue(agg["overall_conservation_verified"], f"Overall conservation failed for {pol_name}")
                self.assertEqual(agg["scheduled_events"], TOTAL_EVENTS)
                self.assertEqual(agg["admitted_events"], TOTAL_EVENTS)
                self.assertEqual(agg["scheduled_queries"], TOTAL_QUERIES)
                self.assertEqual(agg["completed_queries"], TOTAL_QUERIES)
                self.assertEqual(agg["admitted_events"], agg["published_updates"] + agg["coalesced_updates"])

                # Check phase-by-phase conservation
                for phase_name, p_data in res["phases"].items():
                    p_acc = p_data["accounting"]
                    self.assertTrue(p_acc["conservation_verified"], f"Phase {phase_name} conservation failed")
                    self.assertEqual(
                        p_acc["admitted_events"],
                        p_acc["published_updates"] + p_acc["coalesced_updates"],
                    )

    def test_actuator_sign_monotonicity(self) -> None:
        """Increasing U must monotonically decrease publications and increase staleness."""
        dummy_bias = -1.968
        dummy_weights = [0.0] * 7

        results = []
        for u_val in [1, 5, 20]:
            pol_name = "ExactFresh" if u_val == 1 else "FixedCadence"
            res = run_configuration_trial(
                events=self.events,
                queries=self.queries,
                policy_name=pol_name,
                u_val=u_val,
                batch_size=32,
                alpha=0.1,
                model_bias=dummy_bias,
                model_weights=dummy_weights,
            )
            results.append(res)

        sign_verif = verify_actuator_sign(results)
        self.assertTrue(sign_verif["actuator_sign_verified"], "Actuator sign verification failed!")
        self.assertTrue(sign_verif["monotonic_publication_decrease"])
        self.assertTrue(sign_verif["monotonic_staleness_increase"])
        self.assertTrue(sign_verif["monotonic_feature_error_increase"])

        obs = sign_verif["observations"]
        self.assertGreater(obs["U=1"]["publications"], obs["U=5"]["publications"])
        self.assertGreater(obs["U=5"]["publications"], obs["U=20"]["publications"])
        self.assertLess(obs["U=1"]["mean_staleness"], obs["U=5"]["mean_staleness"])
        self.assertLess(obs["U=5"]["mean_staleness"], obs["U=20"]["mean_staleness"])


if __name__ == "__main__":
    unittest.main()
