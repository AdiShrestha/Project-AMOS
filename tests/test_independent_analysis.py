"""Property and regression test suite for independent analysis and statistical inference.

Verifies:
1. Rejection of duplicate query IDs with EvidenceError.
2. Rejection of phantom prediction IDs with EvidenceError.
3. Rejection of label tampering / disagreement with EvidenceError.
4. Rejection of user key / entity mismatch with EvidenceError.
5. Rejection of missing queries (completeness invariant) with EvidenceError.
6. Rejection of non-finite, boolean, and out-of-domain probabilities with EvidenceError.
7. Closed-form analytical mathematical fixture verification for all 6 metrics.
8. Multiplicity control invariants (Holm-Bonferroni monotonicity and bounds).
9. Paired sign-flip and group-swapped permutation tests distinguishing null vs non-null contrasts.
10. Floating-point parity between recomputed metrics and exact reference definitions.
"""

from __future__ import annotations

import math
from pathlib import Path
import random
import sys
import unittest

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
for _p in (str(_project_root), str(_script_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.independent_analysis import (
    CohortRecord,
    EvidenceError,
    binary_metrics,
    holm,
    paired_group_inference,
    paired_inference,
    reconcile_predictions,
    student_t_critical,
)


class TestCohortReconciliationInvariants(unittest.TestCase):
    """Test full cohort left-join reconciliation and integrity gates."""

    def setUp(self):
        # Build standard 5-row test cohort
        self.cohort = {
            101: CohortRecord(seq=101, user_id=1001, event_ts_ns=1000, split="validation", group_id="g1", label=0.0, censored=0),
            102: CohortRecord(seq=102, user_id=1002, event_ts_ns=2000, split="validation", group_id="g1", label=1.0, censored=0),
            103: CohortRecord(seq=103, user_id=1003, event_ts_ns=3000, split="validation", group_id="g2", label=0.0, censored=0),
            104: CohortRecord(seq=104, user_id=1004, event_ts_ns=4000, split="validation", group_id="g2", label=1.0, censored=0),
            105: CohortRecord(seq=105, user_id=1005, event_ts_ns=5000, split="validation", group_id="g2", label=0.0, censored=0),
        }
        self.valid_preds = [
            {"seq": 101, "user_id": 1001, "score": 0.15, "label": 0.0},
            {"seq": 102, "user_id": 1002, "score": 0.85, "label": 1.0},
            {"seq": 103, "user_id": 1003, "score": 0.25, "label": 0.0},
            {"seq": 104, "user_id": 1004, "score": 0.75, "label": 1.0},
            {"seq": 105, "user_id": 1005, "score": 0.35, "label": 0.0},
        ]

    def test_valid_reconciliation_passes(self):
        rec = reconcile_predictions(self.cohort, self.valid_preds)
        self.assertEqual(rec["total_queries"], 5)
        self.assertEqual(rec["aligned_seqs"], [101, 102, 103, 104, 105])
        self.assertEqual(rec["aligned_labels"], [0.0, 1.0, 0.0, 1.0, 0.0])
        self.assertEqual(rec["aligned_scores"], [0.15, 0.85, 0.25, 0.75, 0.35])

    def test_duplicate_query_id_rejected(self):
        duplicate_preds = list(self.valid_preds)
        duplicate_preds.append({"seq": 101, "user_id": 1001, "score": 0.20})
        with self.assertRaisesRegex(EvidenceError, "duplicate prediction id"):
            reconcile_predictions(self.cohort, duplicate_preds)

    def test_phantom_query_id_rejected(self):
        phantom_preds = list(self.valid_preds)
        phantom_preds[4] = {"seq": 999, "user_id": 1005, "score": 0.35}
        with self.assertRaisesRegex(EvidenceError, "phantom prediction id"):
            reconcile_predictions(self.cohort, phantom_preds)

    def test_label_tampering_rejected(self):
        tampered_preds = list(self.valid_preds)
        # Flip label of query 101 from 0.0 to 1.0
        tampered_preds[0] = {"seq": 101, "user_id": 1001, "score": 0.15, "label": 1.0}
        with self.assertRaisesRegex(EvidenceError, "prediction label disagrees with source cohort"):
            reconcile_predictions(self.cohort, tampered_preds)

    def test_user_key_mismatch_rejected(self):
        mismatched_preds = list(self.valid_preds)
        # Change user_id of query 101
        mismatched_preds[0] = {"seq": 101, "user_id": 9999, "score": 0.15}
        with self.assertRaisesRegex(EvidenceError, "user key mismatch"):
            reconcile_predictions(self.cohort, mismatched_preds)

    def test_missing_query_rejected(self):
        # Drop the last query
        incomplete_preds = self.valid_preds[:4]
        with self.assertRaisesRegex(EvidenceError, "missing evaluation rows"):
            reconcile_predictions(self.cohort, incomplete_preds)

    def test_non_finite_and_out_of_domain_scores_rejected(self):
        # NaN
        p_nan = list(self.valid_preds)
        p_nan[0] = {"seq": 101, "score": float("nan")}
        with self.assertRaisesRegex(EvidenceError, "non-finite measurement"):
            reconcile_predictions(self.cohort, p_nan)

        # Infinity
        p_inf = list(self.valid_preds)
        p_inf[0] = {"seq": 101, "score": float("inf")}
        with self.assertRaisesRegex(EvidenceError, "non-finite measurement"):
            reconcile_predictions(self.cohort, p_inf)

        # Boolean
        p_bool = list(self.valid_preds)
        p_bool[0] = {"seq": 101, "score": True}
        with self.assertRaisesRegex(EvidenceError, "boolean is not a numeric measurement"):
            reconcile_predictions(self.cohort, p_bool)

        # Greater than 1.0
        p_high = list(self.valid_preds)
        p_high[0] = {"seq": 101, "score": 1.05}
        with self.assertRaisesRegex(EvidenceError, "prediction probability outside"):
            reconcile_predictions(self.cohort, p_high)

        # Less than 0.0
        p_low = list(self.valid_preds)
        p_low[0] = {"seq": 101, "score": -0.01}
        with self.assertRaisesRegex(EvidenceError, "prediction probability outside"):
            reconcile_predictions(self.cohort, p_low)


class TestMathematicalMetricFixtures(unittest.TestCase):
    """Test metric computation against closed-form analytical mathematical fixtures."""

    def test_perfect_ranking_auroc_and_ap(self):
        labels = [0, 0, 1, 1]
        scores = [0.1, 0.2, 0.8, 0.9]
        m = binary_metrics(labels, scores, threshold=0.5)
        self.assertAlmostEqual(m["auroc"], 1.0, places=12)
        self.assertAlmostEqual(m["average_precision"], 1.0, places=12)
        self.assertAlmostEqual(m["accuracy"], 1.0, places=12)
        self.assertAlmostEqual(m["f1"], 1.0, places=12)

    def test_inverted_ranking_auroc(self):
        labels = [0, 0, 1, 1]
        scores = [0.9, 0.8, 0.2, 0.1]
        m = binary_metrics(labels, scores, threshold=0.5)
        self.assertAlmostEqual(m["auroc"], 0.0, places=12)

    def test_tied_ranks_mann_whitney_auroc(self):
        # 1 negative and 1 positive with identical score
        labels = [0, 1]
        scores = [0.5, 0.5]
        m = binary_metrics(labels, scores, threshold=0.5)
        self.assertAlmostEqual(m["auroc"], 0.5, places=12)

    def test_known_brier_score(self):
        labels = [1, 0]
        scores = [0.8, 0.2]
        # Brier = ((1 - 0.8)^2 + (0 - 0.2)^2) / 2 = (0.04 + 0.04) / 2 = 0.04
        m = binary_metrics(labels, scores)
        self.assertAlmostEqual(m["brier"], 0.04, places=12)

    def test_known_log_loss(self):
        labels = [1, 0]
        scores = [0.5, 0.5]
        # Log loss = - (1 * ln(0.5) + 1 * ln(0.5)) / 2 = - ln(0.5) = ln(2)
        m = binary_metrics(labels, scores)
        self.assertAlmostEqual(m["log_loss"], math.log(2.0), places=12)

    def test_student_t_critical_values(self):
        # Test standard known two-sided critical values at alpha = 0.05
        # df = 1: t_crit = 12.7062047364
        t_df1 = student_t_critical(0.05, 1)
        self.assertAlmostEqual(t_df1, 12.7062, places=3)
        # df = 4: t_crit = 2.7764451052
        t_df4 = student_t_critical(0.05, 4)
        self.assertAlmostEqual(t_df4, 2.7764, places=3)
        # df = 30: t_crit = 2.0422724563
        t_df30 = student_t_critical(0.05, 30)
        self.assertAlmostEqual(t_df30, 2.0423, places=3)


class TestMultiplicityControlInvariants(unittest.TestCase):
    """Test family-wise multiplicity control and step-down Holm monotonicity."""

    def test_holm_monotonicity_and_bounds(self):
        raw_p = [0.005, 0.01, 0.03, 0.04]
        adj_p = holm(raw_p)
        # Monotonicity with respect to rank
        for r_p, a_p in zip(raw_p, adj_p):
            self.assertGreaterEqual(a_p, r_p, "Adjusted p-value must be >= raw p-value")
            self.assertLessEqual(a_p, 1.0, "Adjusted p-value must be <= 1.0")

        # Explicit closed-form values:
        # rank 0 (p=0.005): 0.005 * 4 = 0.02
        # rank 1 (p=0.01): 0.01 * 3 = 0.03
        # rank 2 (p=0.03): 0.03 * 2 = 0.06
        # rank 3 (p=0.04): 0.04 * 1 = 0.04 -> prior=0.06 -> max(0.06, 0.04) = 0.06
        self.assertAlmostEqual(adj_p[0], 0.02, places=12)
        self.assertAlmostEqual(adj_p[1], 0.03, places=12)
        self.assertAlmostEqual(adj_p[2], 0.06, places=12)
        self.assertAlmostEqual(adj_p[3], 0.06, places=12)

    def test_holm_preserves_input_ordering(self):
        # Unsorted inputs
        raw_p = [0.04, 0.005, 0.03, 0.01]
        adj_p = holm(raw_p)
        self.assertAlmostEqual(adj_p[0], 0.06, places=12)
        self.assertAlmostEqual(adj_p[1], 0.02, places=12)
        self.assertAlmostEqual(adj_p[2], 0.06, places=12)
        self.assertAlmostEqual(adj_p[3], 0.03, places=12)


class TestStatisticalInferenceContrasts(unittest.TestCase):
    """Test paired sign-flip and cluster permutation tests under null vs non-null scenarios."""

    def test_paired_inference_null_contrast(self):
        # Identical vectors: differences are zero
        a = [0.25, 0.30, 0.45, 0.20, 0.35]
        b = [0.25, 0.30, 0.45, 0.20, 0.35]
        inf = paired_inference(a, b, seed=42)
        self.assertEqual(inf["effect"], 0.0)
        self.assertEqual(inf["p_raw"], 1.0)
        self.assertTrue(inf["degenerate_variance"])

    def test_paired_inference_non_null_contrast(self):
        # Strongly separated vectors: A strictly higher loss than B
        a = [0.55, 0.60, 0.65, 0.50, 0.58, 0.62, 0.59, 0.61]
        b = [0.15, 0.20, 0.25, 0.10, 0.18, 0.22, 0.19, 0.21]
        inf = paired_inference(a, b, seed=42)
        self.assertGreater(inf["effect"], 0.35)
        # Exact sign-flip on 8 strictly positive differences has p = 2 / 2^8 = 2 / 256 = 0.0078125
        self.assertAlmostEqual(inf["p_raw"], 2.0 / 256.0, places=6)
        self.assertLess(inf["p_raw"], 0.05)

    def test_paired_group_inference_null_contrast(self):
        labels = [0.0, 1.0, 0.0, 1.0] * 3
        groups = ["g1", "g1", "g2", "g2", "g3", "g3", "g4", "g4", "g5", "g5", "g6", "g6"]
        scores_a = [0.2, 0.8, 0.3, 0.7, 0.2, 0.8, 0.3, 0.7, 0.2, 0.8, 0.3, 0.7]
        scores_b = list(scores_a)
        res = paired_group_inference(labels, [(scores_a, scores_b)], groups, metric="log_loss", draws=1000, seed=42)
        self.assertEqual(res["effect"], 0.0)
        self.assertEqual(res["p_raw"], 1.0)


if __name__ == "__main__":
    unittest.main()
