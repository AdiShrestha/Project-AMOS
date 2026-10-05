#!/usr/bin/env python3
"""Targeted unit, property, and cross-runtime parity tests for publication core.

Tests:
1. ExactFresh (U=1) zero feature error and zero staleness on warm queries.
2. Exact conservation accounting (processed == published + coalesced) across policies.
3. Cold-key query safety and correct cold_start tagging.
4. Fixed-cadence update coalescing and staleness tracking.
5. Cross-runtime numerical and accounting parity between Python simulator and native C++ cache.
"""

from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tools.publication_reference import (
    AdaptivePressurePolicy,
    ElapsedThresholdPolicy,
    ExactFreshPolicy,
    FixedCadencePolicy,
    PublicationSimulator,
    Query,
    QueryResult,
    RawEvent,
    VersionedCache,
    FEATURE_DIMENSION,
)


class PublicationCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_pub_core_")
        self.root = Path(self.temp_dir)
        self.cache_binary = self._find_cache_tool()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _find_cache_tool(self) -> Optional[str]:
        env_tool = os.environ.get("BPFEAT_CACHE_TOOL")
        if env_tool and Path(env_tool).exists() and os.access(env_tool, os.X_OK):
            return str(Path(env_tool).resolve())
        candidates = [
            Path("build/debug/bpfeat_cache_tool"),
            Path("build/release/bpfeat_cache_tool"),
            Path("build/bpfeat_cache_tool"),
        ]
        for c in candidates:
            if c.exists() and os.access(c, os.X_OK):
                return str(c.resolve())
        return None

    def test_exact_fresh_zero_feature_error(self) -> None:
        """Under ExactFresh (U=1), feature error and staleness must be 0 for all warm queries."""
        sim = PublicationSimulator(policy=ExactFreshPolicy(), alpha=0.1)

        t0 = 1511539200000000000
        # Ingest 50 events across 5 keys
        for i in range(50):
            ev = RawEvent(
                seq=i,
                event_ts_ns=t0 + i * 1000000000,
                key=i % 5,
                item_id=100 + (i % 20),
                category_id=500 + (i % 10),
                behavior_code=i % 4,
            )
            sim.process_event(ev)

        # Query all keys
        for k in range(5):
            q = Query(query_id=k, key=k, query_ts_ns=t0 + 60 * 1000000000)
            res = sim.query(q)
            self.assertEqual(res.cold_start, 0)
            self.assertGreater(res.version_id, 0)
            self.assertEqual(res.update_staleness, 0)
            self.assertAlmostEqual(res.feature_error, 0.0, places=12)

        acc = sim.get_accounting()
        self.assertEqual(acc["processed_updates"], 50)
        self.assertEqual(acc["published_updates"], 50)
        self.assertEqual(acc["coalesced_updates"], 0)
        self.assertTrue(acc["conservation_valid"])

    def test_exact_conservation_accounting(self) -> None:
        """Conservation invariant (processed == published + coalesced) must hold across all policies."""
        policies = [
            ExactFreshPolicy(),
            FixedCadencePolicy(cadence=1),
            FixedCadencePolicy(cadence=3),
            FixedCadencePolicy(cadence=8),
            ElapsedThresholdPolicy(delta_t_ns=5000000000),
            AdaptivePressurePolicy(k_min=1, k_max=16),
        ]

        t0 = 1511539200000000000
        for policy in policies:
            with self.subTest(policy=type(policy).__name__):
                sim = PublicationSimulator(policy=policy, alpha=0.15)
                for i in range(100):
                    ev = RawEvent(
                        seq=i,
                        event_ts_ns=t0 + i * 1000000000,
                        key=i % 7,
                        item_id=1000 + i,
                        category_id=200,
                        behavior_code=i % 4,
                    )
                    pressure = (i % 10) / 10.0
                    sim.process_event(ev, pressure=pressure)

                acc = sim.get_accounting()
                self.assertEqual(acc["processed_updates"], 100)
                self.assertEqual(
                    acc["processed_updates"],
                    acc["published_updates"] + acc["coalesced_updates"],
                )
                self.assertTrue(acc["conservation_valid"])

    def test_cold_key_query_safety(self) -> None:
        """Unseen keys and un-published keys must return cold_start=1 and never crash or throw."""
        sim = PublicationSimulator(policy=FixedCadencePolicy(cadence=5), alpha=0.1)

        # 1. Query completely unseen key
        q_unseen = Query(query_id=1, key=999, query_ts_ns=1000000000)
        res_unseen = sim.query(q_unseen)
        self.assertEqual(res_unseen.cold_start, 1)
        self.assertEqual(res_unseen.version_id, 0)
        self.assertEqual(res_unseen.latest_included_seq, 0)
        self.assertEqual(res_unseen.latest_event_ts_ns, 0)
        self.assertEqual(res_unseen.cached_features, (0.0,) * FEATURE_DIMENSION)
        self.assertEqual(res_unseen.fresh_features, (0.0,) * FEATURE_DIMENSION)
        self.assertEqual(res_unseen.update_staleness, 0)
        self.assertAlmostEqual(res_unseen.feature_error, 0.0, places=12)

        # 2. Ingest 3 updates for key 42 (not reaching cadence 5 -> not published)
        t0 = 1511539200000000000
        for i in range(3):
            ev = RawEvent(seq=i, event_ts_ns=t0 + i * 1000, key=42, item_id=10, category_id=20, behavior_code=0)
            sim.process_event(ev)

        q_pending = Query(query_id=2, key=42, query_ts_ns=t0 + 5000)
        res_pending = sim.query(q_pending)
        self.assertEqual(res_pending.cold_start, 1)
        self.assertEqual(res_pending.version_id, 0)
        self.assertEqual(res_pending.cached_features, (0.0,) * FEATURE_DIMENSION)
        self.assertEqual(res_pending.update_staleness, 3)
        self.assertGreater(res_pending.feature_error, 0.0)

    def test_fixed_cadence_coalescing_and_staleness(self) -> None:
        """Fixed cadence U=4 must coalesce updates 1..3 and publish at update 4."""
        sim = PublicationSimulator(policy=FixedCadencePolicy(cadence=4), alpha=0.1)
        t0 = 1511539200000000000

        # Updates 1, 2, 3: coalesced
        for i in range(3):
            ev = RawEvent(seq=i, event_ts_ns=t0 + i * 1000000, key=1, item_id=10, category_id=20, behavior_code=0)
            published, ver = sim.process_event(ev)
            self.assertFalse(published)
            self.assertIsNone(ver)

        acc = sim.get_accounting()
        self.assertEqual(acc["processed_updates"], 3)
        self.assertEqual(acc["published_updates"], 0)
        self.assertEqual(acc["coalesced_updates"], 3)

        q3 = sim.query(Query(query_id=1, key=1, query_ts_ns=t0 + 3000000))
        self.assertEqual(q3.cold_start, 1)
        self.assertEqual(q3.update_staleness, 3)

        # Update 4: publishes
        ev4 = RawEvent(seq=3, event_ts_ns=t0 + 3000000, key=1, item_id=10, category_id=20, behavior_code=0)
        published, ver = sim.process_event(ev4)
        self.assertTrue(published)
        self.assertIsNotNone(ver)
        self.assertEqual(ver.version_id, 1)

        acc = sim.get_accounting()
        self.assertEqual(acc["processed_updates"], 4)
        self.assertEqual(acc["published_updates"], 1)
        self.assertEqual(acc["coalesced_updates"], 3)

        q4 = sim.query(Query(query_id=2, key=1, query_ts_ns=t0 + 4000000))
        self.assertEqual(q4.cold_start, 0)
        self.assertEqual(q4.version_id, 1)
        self.assertEqual(q4.update_staleness, 0)
        self.assertAlmostEqual(q4.feature_error, 0.0, places=12)

    def test_cross_runtime_parity_with_native_cpp_cache(self) -> None:
        """Cross-runtime parity between Python reference simulator and native C++ bpfeat_cache_tool."""
        if not self.cache_binary:
            self.skipTest("C++ cache tool binary not available for cross-runtime testing")

        events_file = self.root / "events.csv"
        queries_file = self.root / "queries.csv"
        py_out_queries = self.root / "py_queries.csv"
        cpp_out_queries = self.root / "cpp_queries.csv"
        cpp_out_acc = self.root / "cpp_acc.json"

        # Generate 200 diverse events across 10 keys
        t0 = 1511539200000000000
        event_rows = ["seq,event_ts_ns,key,item_id,category_id,behavior_code"]
        events: List[RawEvent] = []
        for i in range(200):
            seq = i
            ts = t0 + i * 500000000
            k = i % 10
            item = 100 + (i % 30)
            cat = 500 + (i % 15)
            beh = i % 4
            event_rows.append(f"{seq},{ts},{k},{item},{cat},{beh}")
            events.append(RawEvent(seq, ts, k, item, cat, beh))
        events_file.write_text("\n".join(event_rows) + "\n")

        # Generate 50 queries interleaving warm, cold, and pending keys
        query_rows = ["query_id,key,query_ts_ns"]
        queries: List[Query] = []
        for qid in range(50):
            # Query existing keys, or cold key 999
            k = 999 if qid % 10 == 0 else (qid % 10)
            qts = t0 + (qid * 2 + 50) * 500000000
            query_rows.append(f"{qid},{k},{qts}")
            queries.append(Query(qid, k, qts))
        queries_file.write_text("\n".join(query_rows) + "\n")

        for policy_name, cadence, delta_t in [
            ("ExactFresh", 1, 0),
            ("FixedCadence", 4, 0),
            ("ElapsedThreshold", 1, 5000000000),
        ]:
            with self.subTest(policy=policy_name):
                # Run C++ tool
                cmd = [
                    self.cache_binary,
                    "--events", str(events_file),
                    "--queries", str(queries_file),
                    "--out-queries", str(cpp_out_queries),
                    "--out-accounting", str(cpp_out_acc),
                    "--policy", policy_name,
                    "--cadence", str(cadence),
                    "--delta-t-ns", str(delta_t),
                    "--alpha", "0.1",
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                self.assertEqual(proc.returncode, 0, f"C++ tool failed: {proc.stderr}")

                cpp_acc = json.loads(cpp_out_acc.read_text())

                # Run Python simulator
                if policy_name == "ExactFresh":
                    pol = ExactFreshPolicy()
                elif policy_name == "FixedCadence":
                    pol = FixedCadencePolicy(cadence=cadence)
                else:
                    pol = ElapsedThresholdPolicy(delta_t_ns=delta_t)

                sim = PublicationSimulator(policy=pol, alpha=0.1)
                for ev in events:
                    sim.process_event(ev)

                py_results = [sim.query(q) for q in queries]
                py_acc = sim.get_accounting()

                # 1. Assert exact accounting agreement
                self.assertEqual(cpp_acc["processed_updates"], py_acc["processed_updates"])
                self.assertEqual(cpp_acc["published_updates"], py_acc["published_updates"])
                self.assertEqual(cpp_acc["coalesced_updates"], py_acc["coalesced_updates"])
                self.assertEqual(cpp_acc["queries_served"], py_acc["queries_served"])
                self.assertEqual(cpp_acc["cold_queries"], py_acc["cold_queries"])
                self.assertEqual(cpp_acc["warm_queries"], py_acc["warm_queries"])
                self.assertEqual(cpp_acc["conservation_valid"], py_acc["conservation_valid"])

                # 2. Assert query-by-query parity
                with open(cpp_out_queries, "r", encoding="utf-8") as f:
                    reader = list(csv.DictReader(f))

                self.assertEqual(len(reader), len(py_results))
                for row, py_res in zip(reader, py_results):
                    self.assertEqual(int(row["query_id"]), py_res.query_id)
                    self.assertEqual(int(row["key"]), py_res.key)
                    self.assertEqual(int(row["query_ts_ns"]), py_res.query_ts_ns)
                    self.assertEqual(int(row["cold_start"]), py_res.cold_start)
                    self.assertEqual(int(row["version_id"]), py_res.version_id)
                    self.assertEqual(int(row["latest_included_seq"]), py_res.latest_included_seq)
                    self.assertEqual(int(row["latest_event_ts_ns"]), py_res.latest_event_ts_ns)
                    self.assertEqual(int(row["event_time_age_ns"]), py_res.event_time_age_ns)
                    self.assertEqual(int(row["update_staleness"]), py_res.update_staleness)

                    # Feature error parity
                    cpp_err = float(row["feature_error"])
                    self.assertLess(
                        abs(cpp_err - py_res.feature_error),
                        1e-12,
                        f"feature_error discrepancy: {cpp_err} vs {py_res.feature_error}",
                    )

                    # 7-feature vectors parity
                    for d in range(FEATURE_DIMENSION):
                        cpp_c = float(row[f"cached_x{d}"])
                        py_c = py_res.cached_features[d]
                        self.assertLess(
                            abs(cpp_c - py_c),
                            1e-12,
                            f"cached_x{d} discrepancy: {cpp_c} vs {py_c}",
                        )

                        cpp_f = float(row[f"fresh_x{d}"])
                        py_f = py_res.fresh_features[d]
                        self.assertLess(
                            abs(cpp_f - py_f),
                            1e-12,
                            f"fresh_x{d} discrepancy: {cpp_f} vs {py_f}",
                        )


if __name__ == "__main__":
    unittest.main()
