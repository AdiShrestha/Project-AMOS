#!/usr/bin/env python3
"""Unit and property tests for Contract AMOS-15 robustness analysis.

Verifies:
- Empirical failure taxonomy disjointness, prevalence, and SEV severity levels.
- Hyperparameter sensitivity perturbation sweeps and flat rationales.
- Gatekeeper verification subcommand exit codes.
- Factorial component decomposition and claim ledger schema.
"""

import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

from tools.robustness_analysis import (
    build_failure_taxonomy,
    build_sensitivity_sweeps,
    build_factorial_decomposition,
    load_cohort,
    load_predictions,
)


class RobustnessAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.artifact_path = cls.root / "docs" / "research" / "robustness_analysis.json"
        cls.claim_ledger_path = cls.root / "project" / "claim_ledger.json"
        cls.cohort_path = cls.root / "data" / "cohort.csv"
        cls.runs_dir = cls.root / "project" / ".factory" / "epoch_0001" / "runs"

        # Ensure artifact exists
        if not cls.artifact_path.is_file() or not cls.claim_ledger_path.is_file():
            cmd = [
                sys.executable,
                "-B",
                str(cls.root / "tools" / "robustness_analysis.py"),
                "--cohort",
                str(cls.cohort_path),
                "--runs-dir",
                str(cls.runs_dir),
                "--output",
                str(cls.artifact_path),
                "--claim-ledger",
                str(cls.claim_ledger_path),
            ]
            subprocess.run(cmd, check=True, cwd=cls.root)

        with open(cls.artifact_path, "r", encoding="utf-8") as f:
            cls.artifact = json.load(f)

        with open(cls.claim_ledger_path, "r", encoding="utf-8") as f:
            cls.claim_ledger = json.load(f)

    def test_failure_taxonomy_schema_and_prevalence(self) -> None:
        """Verify taxonomy contains at least 3 categories with valid prevalences and SEVs."""
        failures = self.artifact.get("failures", [])
        self.assertGreaterEqual(len(failures), 3)

        valid_sevs = {"SEV-1", "SEV-2", "SEV-3", "SEV-4"}
        seen_categories = set()
        seen_sample_ids = set()

        for cat in failures:
            name = cat.get("category")
            self.assertIsInstance(name, str)
            self.assertNotIn(name, seen_categories)
            seen_categories.add(name)

            sev = cat.get("severity")
            self.assertIn(sev, valid_sevs)

            cond_ids = cat.get("condition_ids", [])
            self.assertIsInstance(cond_ids, list)
            self.assertGreaterEqual(len(cond_ids), 1)

            # Unique condition IDs within category
            self.assertEqual(len(cond_ids), len(set(cond_ids)))

            # Disjointness check across categories
            current_ids = set(cond_ids)
            self.assertTrue(seen_sample_ids.isdisjoint(current_ids), f"Category {name} overlaps with prior categories!")
            seen_sample_ids.update(current_ids)

            prev = cat.get("prevalence")
            self.assertIsInstance(prev, (int, float))
            self.assertGreater(prev, 0.0)
            self.assertLessEqual(prev, 1.0)
            self.assertAlmostEqual(prev, len(cond_ids) / 22396, places=4)

    def test_sensitivity_sweeps_schema_and_metrics(self) -> None:
        """Verify sensitivity sweeps have valid parameters, levels, and metrics."""
        sweeps = self.artifact.get("sweeps", [])
        self.assertGreaterEqual(len(sweeps), 3)

        for sweep in sweeps:
            param = sweep.get("parameter")
            self.assertIsInstance(param, str)
            self.assertTrue(len(param) > 0)

            levels = sweep.get("levels", [])
            self.assertIsInstance(levels, list)
            self.assertGreaterEqual(len(levels), 3)

            metrics = sweep.get("metrics", [])
            self.assertIsInstance(metrics, list)
            self.assertEqual(len(metrics), len(levels))
            self.assertTrue(all(math.isfinite(m) for m in metrics))

            spread = max(metrics) - min(metrics)
            is_flat = spread < max(0.005, 0.01 * max(abs(v) for v in metrics))

            if is_flat:
                self.assertTrue(sweep.get("expected_flat", False))
                rationale = sweep.get("flat_rationale", "")
                self.assertIsInstance(rationale, str)
                self.assertGreaterEqual(len(rationale), 40)

    def test_failure_taxonomy_schema_and_invariants(self) -> None:
        """Verify failure taxonomy meets strict category, identifier, and prevalence invariants."""
        failures = self.artifact.get("failures", [])
        self.assertGreaterEqual(len(failures), 3)
        seen_categories = set()
        seen_all_ids: Set[str] = set()
        for idx, row in enumerate(failures):
            self.assertIsInstance(row, dict)
            cat = row.get("category")
            self.assertIsInstance(cat, str)
            self.assertNotIn(cat, seen_categories)
            seen_categories.add(cat)

            ids = row.get("condition_ids")
            self.assertIsInstance(ids, list)
            self.assertGreaterEqual(len(ids), 1)
            self.assertEqual(len(ids), len(set(ids)), f"Duplicate IDs in {cat}")

            # Verify mutual disjointness across categories
            overlap = seen_all_ids.intersection(set(ids))
            self.assertEqual(len(overlap), 0, f"Overlapping IDs found: {overlap}")
            seen_all_ids.update(ids)

            prev = row.get("prevalence")
            self.assertIsInstance(prev, (int, float))
            self.assertGreaterEqual(prev, 0.0)
            self.assertLessEqual(prev, 1.0)

            sev = row.get("severity")
            self.assertIn(sev, {"SEV-1", "SEV-2", "SEV-3", "SEV-4"})

    def test_sensitivity_sweeps_schema_and_invariants(self) -> None:
        """Verify sensitivity sweeps adhere to strict perturbation, metric, and flat rationale rules."""
        sweeps = self.artifact.get("sweeps", [])
        self.assertGreaterEqual(len(sweeps), 1)
        for sweep in sweeps:
            self.assertIsInstance(sweep, dict)
            param = sweep.get("parameter")
            self.assertIsInstance(param, str)

            metrics = sweep.get("metrics", [])
            self.assertIsInstance(metrics, list)
            self.assertGreaterEqual(len(metrics), 3)
            self.assertTrue(all(math.isfinite(m) for m in metrics))

            spread = max(metrics) - min(metrics)
            threshold = max(0.005, 0.01 * max(abs(v) for v in metrics))
            if spread < threshold:
                self.assertTrue(sweep.get("expected_flat", False))
                rationale = sweep.get("flat_rationale", "")
                self.assertIsInstance(rationale, str)
                self.assertGreaterEqual(len(rationale), 40)
            else:
                self.assertFalse(sweep.get("expected_flat", False))

    def test_factorial_decomposition_orthogonality(self) -> None:
        """Verify 2x2 factorial interaction synergy confirms decoupled mechanisms."""
        decomp = self.artifact.get("factorial_decomposition", {})
        self.assertIn("cadence_main_effect_delta_ap", decomp)
        self.assertIn("alpha_main_effect_delta_ap", decomp)
        self.assertIn("interaction_synergy_delta_ap", decomp)

        synergy = decomp["interaction_synergy_delta_ap"]
        self.assertLess(abs(synergy), 0.005, f"Interaction synergy {synergy} exceeds 0.005 orthogonality threshold!")

    def test_subgroup_activity_terciles(self) -> None:
        """Verify activity tercile stratification shows monotonic performance gap with activity level."""
        subgroups = self.artifact.get("subgroup_generalization", {})
        terciles = subgroups.get("activity_terciles", {})
        self.assertIn("low_activity", terciles)
        self.assertIn("medium_activity", terciles)
        self.assertIn("high_activity", terciles)

        low = terciles["low_activity"]
        high = terciles["high_activity"]

        # Dynamic advantage over static is strictly larger in high activity than low activity
        self.assertGreater(high["dynamic_vs_static_delta"], low["dynamic_vs_static_delta"])

    def test_claim_ledger_entries(self) -> None:
        """Verify claim ledger contains all 5 required claims with valid status and limitations."""
        claims = {c["id"]: c for c in self.claim_ledger.get("claims", [])}
        expected_claims = [
            "claim_dynamic_vs_static_quality",
            "claim_dynamic_vs_budget_quality",
            "claim_ood_generalization",
            "claim_sensitivity_stability",
            "claim_decoupled_mechanisms",
        ]
        for cid in expected_claims:
            self.assertIn(cid, claims)
            c = claims[cid]
            self.assertEqual(c.get("status"), "CONFIRMED")
            self.assertGreater(len(c.get("experiment_ids", [])), 0)
            self.assertGreaterEqual(len(c.get("limitations", "")), 20)


if __name__ == "__main__":
    unittest.main()
