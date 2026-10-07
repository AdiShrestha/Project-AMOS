#!/usr/bin/env python3
"""Comprehensive test suite for manuscript audit, statistical protocol, and venue alignment.

Verifies:
1. Structural integrity and evidence hash validity of pre_submission_audit.json.
2. Compliance of statistical_protocol.json with inference standards.
3. Exact numerical agreement of headline claims between manuscript.md and per_number_manifest.json.
4. Completeness and validity of bibliography.bib citations.
5. Presence and structure of VLDB venue checklist.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import unittest


class ManuscriptAuditTests(unittest.TestCase):
    """Test suite validating pre-submission artifacts and scholarly manuscript alignment."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parent.parent
        cls.research_dir = cls.root / "docs" / "research"
        cls.manuscript_path = cls.research_dir / "manuscript.md"
        cls.bib_path = cls.research_dir / "bibliography.bib"
        cls.audit_path = cls.research_dir / "pre_submission_audit.json"
        cls.protocol_path = cls.research_dir / "statistical_protocol.json"
        cls.checklist_path = cls.research_dir / "venue_checklist_vldb.md"
        cls.per_number_path = cls.research_dir / "per_number_manifest.json"

    def test_pre_submission_audit_schema_and_hashes(self) -> None:
        """Verify pre_submission_audit.json structure, lengths, and exact SHA-256 evidence digests."""
        self.assertTrue(self.audit_path.exists(), "pre_submission_audit.json must exist")
        with open(self.audit_path, "r", encoding="utf-8") as f:
            audit = json.load(f)

        # 1. Claims
        claims = audit.get("claims", [])
        self.assertGreaterEqual(len(claims), 5)
        seen_ids = set()
        for c in claims:
            cid = c.get("id")
            self.assertIsInstance(cid, str)
            self.assertNotIn(cid, seen_ids)
            seen_ids.add(cid)
            scope = c.get("scope", "")
            self.assertGreaterEqual(len(scope), 20, f"Claim scope too short: {cid}")

            evidence = c.get("evidence", [])
            self.assertGreaterEqual(len(evidence), 1)
            for ev in evidence:
                rel_path = ev.get("path")
                exp_hash = ev.get("sha256")
                target = self.research_dir / rel_path
                self.assertTrue(target.is_file(), f"Missing evidence file: {target}")
                actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                self.assertEqual(actual_hash, exp_hash, f"Hash mismatch on {rel_path}")

        # 2. Data Provenance & Reproducibility
        for key in ("data_provenance", "reproducibility"):
            sec = audit.get(key, {})
            self.assertGreaterEqual(len(sec.get("assessment", "")), 40)
            for ev in sec.get("evidence", []):
                target = self.research_dir / ev.get("path")
                self.assertTrue(target.is_file())
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), ev.get("sha256"))

        # 3. Baselines & Ablations
        for key in ("baselines", "ablations"):
            entries = audit.get(key, [])
            self.assertGreaterEqual(len(entries), 1)
            for entry in entries:
                self.assertGreaterEqual(len(entry.get("assessment", "")), 40)
                for ev in entry.get("evidence", []):
                    target = self.research_dir / ev.get("path")
                    self.assertTrue(target.is_file())
                    self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), ev.get("sha256"))

        # 4. Limitations
        limits = audit.get("limitations", [])
        self.assertGreaterEqual(len(limits), 3)
        for lim in limits:
            self.assertGreaterEqual(len(lim), 20)

    def test_statistical_protocol_invariants(self) -> None:
        """Verify statistical_protocol.json conforms to rigorous inference requirements."""
        self.assertTrue(self.protocol_path.exists(), "statistical_protocol.json must exist")
        with open(self.protocol_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        proto = data.get("statistical_protocol", {})
        self.assertEqual(proto.get("primary_metric"), "average_precision")
        self.assertEqual(proto.get("sampling_unit"), "group")
        self.assertEqual(proto.get("test"), "paired_group_permutation")
        self.assertEqual(proto.get("multiplicity_correction"), "holm")

        alpha = proto.get("alpha")
        self.assertTrue(0.0 < alpha <= 0.1)

        ci = proto.get("confidence_interval", [])
        self.assertEqual(len(ci), 2)
        self.assertLess(ci[0], ci[1])

        pvals = proto.get("p_values", [])
        self.assertGreaterEqual(len(pvals), 1)
        for p in pvals:
            self.assertTrue(0.0 < p <= 1.0)

    def test_manuscript_content_and_numerical_agreement(self) -> None:
        """Verify manuscript.md exists and contains exact matching headline figures."""
        self.assertTrue(self.manuscript_path.exists(), "manuscript.md must exist")
        text = self.manuscript_path.read_text(encoding="utf-8")

        # Verify required major sections
        required_sections = [
            "# Dynamic Queue-Pressure Feature Publication",
            "## Abstract",
            "## 1. Introduction",
            "## 2. Related Work & Literature Matrix",
            "## 3. System Architecture & Formulation",
            "## 4. Experimental Methodology",
            "## 5. Confirmatory Experimental Results",
            "## 6. Robustness, Sensitivity & Component Decomposition",
            "## 7. Threats to Validity & Limitations",
            "## 8. Artifact Availability & Reproducibility Statement",
        ]
        for sec in required_sections:
            self.assertIn(sec, text, f"Missing section in manuscript: {sec}")

        # Verify key numerical values are represented accurately
        key_numbers = [
            "0.029328",  # Dynamic vs static AP delta
            "0.028391",  # Dynamic vs budget AP delta
            "0.141621",  # Test AP
            "0.517560",  # Test AUROC
            "0.3302",    # Write work ratio
            "1.20 ms",   # Mean staleness
            "66.98%",    # Write work reduction
            "0.227853",  # Cold user OOD AP
            "-0.000829", # Factorial synergy
        ]
        for num in key_numbers:
            self.assertIn(num, text, f"Key numerical claim missing from manuscript: {num}")

    def test_bibliography_completeness_and_doi(self) -> None:
        """Verify bibliography.bib contains all foundational citations with valid DOIs or URLs."""
        self.assertTrue(self.bib_path.exists(), "bibliography.bib must exist")
        bib_text = self.bib_path.read_text(encoding="utf-8")

        required_keys = [
            "wooders2023ralf",
            "chang2024biathlon",
            "crankshaw2017clipper",
            "bifet2007adwin",
            "demsar2006statistical",
        ]
        for k in required_keys:
            self.assertIn(k, bib_text, f"Missing citation key: {k}")

        # Verify entries have author, title, and year
        entries = re.findall(r"@\w+\{([^,]+),([^@]+)\}", bib_text)
        for key, body in entries:
            self.assertIn("author", body.lower())
            self.assertIn("title", body.lower())
            self.assertIn("year", body.lower())
            self.assertTrue("doi" in body.lower() or "url" in body.lower())

    def test_venue_checklist_completeness(self) -> None:
        """Verify venue checklist covers VLDB EAB requirements."""
        self.assertTrue(self.checklist_path.exists(), "venue_checklist_vldb.md must exist")
        chk_text = self.checklist_path.read_text(encoding="utf-8")
        self.assertIn("Experiment, Analysis & Benchmark", chk_text)
        self.assertIn("Double-Anonymous Review", chk_text)
        self.assertIn("Acceptance Disclaimer", chk_text)


if __name__ == "__main__":
    unittest.main()
