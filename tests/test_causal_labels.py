"""Targeted unit, property, and regression tests for causal label generation and cohort splitting.

Acceptance Gates Verified:
1. No Current-Event Leakage: Zero positive labels caused by a buy at t_j = t_i.
2. Witness Integrity: 100% of positive labels have a valid positive_witness_seq pointing to a
   strictly future buy event for that exact user_id within (t_i, t_i + H].
3. Censoring Invariance: Zero events in the final 2 hours of Day 9 receive a valid label;
   all have censored == 1, label_valid == 0, and label is None.
4. Embargo Invariance: Zero label windows from the train split reach across the embargo into
   the validation split; zero validation windows reach into test.
5. Group Floor: Test split contains >= 30 independent groups (group_id), with >= 10 positive and
   >= 10 negative instances per group.
6. Cold OOD Disjointness: Complete user_id disjointness between ood and train/validation.
7. Schema Compatibility: data/cohort.csv complies with required schema specification.
"""

from collections import Counter, defaultdict
import csv
import json
import os
from pathlib import Path
import tempfile
import unittest

from source.preprocessing.labels import future_purchase_labels
from tools.generate_causal_labels import (
    DEFAULT_CAMPAIGN_END_SEC,
    DEFAULT_CAMPAIGN_START_SEC,
    DEFAULT_HORIZON_SEC,
    generate_causal_labels_from_events,
    stream_causal_labels,
)
from tools.generate_cohort_splits import (
    CAMPAIGN_END_SEC,
    CAMPAIGN_START_SEC,
    EMBARGO_1_END_SEC,
    EMBARGO_2_END_SEC,
    TEST_END_SEC,
    TEST_START_SEC,
    TRAIN_END_SEC,
    VAL_END_SEC,
    VAL_START_SEC,
    assign_split_and_group,
    generate_cohort_splits,
    is_ood_user,
)


class CausalLabelAndSplitTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def _make_event(self, seq, ts_sec, user_id, behavior_code, item_id=1, category_id=1):
        return {
            "seq": seq,
            "source_id": str(seq),
            "event_ts_ns": ts_sec * 1_000_000_000,
            "key": user_id,
            "user_id": user_id,
            "item_id": item_id,
            "category_id": category_id,
            "behavior_code": behavior_code,
        }

    def _write_canonical_csv(self, path, events):
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("seq,event_ts_ns,key,item_id,category_id,behavior_code\n")
            for e in events:
                f.write(f"{e['seq']},{e['event_ts_ns']},{e['key']},{e['item_id']},{e['category_id']},{e['behavior_code']}\n")

    # -------------------------------------------------------------------------
    # Gate 1: No Current-Event / Contemporaneous Leakage
    # -------------------------------------------------------------------------
    def test_zero_contemporaneous_leakage_single_and_concurrent(self):
        """Buys occurring at t_j = t_i must never cause Y_i = 1."""
        h_sec = 7200
        h_ns = h_sec * 1_000_000_000
        obs_end_ns = 1512316799 * 1_000_000_000

        # Case A: Buy event itself must not witness itself
        events_a = [self._make_event(0, 1511539200, 101, 3)]  # buy
        labels_a = generate_causal_labels_from_events(events_a, h_ns, obs_end_ns)
        self.assertEqual(labels_a[0]["label"], 0)
        self.assertIsNone(labels_a[0]["positive_witness_seq"])

        # Case B: Concurrent pv and buy for same user at exact same second
        events_b = [
            self._make_event(0, 1511539200, 101, 0),  # pv
            self._make_event(1, 1511539200, 101, 3),  # buy at same second
        ]
        labels_b = generate_causal_labels_from_events(events_b, h_ns, obs_end_ns)
        self.assertEqual(labels_b[0]["label"], 0, "Same-time buy leaked to contemporaneous event")
        self.assertEqual(labels_b[1]["label"], 0, "Same-time buy self-witnessed")

        # Case C: Same-time buy present, but ALSO a genuine future buy within horizon
        events_c = [
            self._make_event(0, 1511539200, 101, 0),  # pv at t
            self._make_event(1, 1511539200, 101, 3),  # buy at t
            self._make_event(2, 1511539200 + 100, 101, 3),  # buy at t + 100s
        ]
        labels_c = generate_causal_labels_from_events(events_c, h_ns, obs_end_ns)
        self.assertEqual(labels_c[0]["label"], 1)
        self.assertEqual(labels_c[0]["positive_witness_seq"], 2, "Witness must be future buy (seq=2), not same-time buy (seq=1)")
        self.assertEqual(labels_c[1]["label"], 1)
        self.assertEqual(labels_c[1]["positive_witness_seq"], 2, "Witness must be future buy (seq=2)")
        self.assertEqual(labels_c[2]["label"], 0)

    # -------------------------------------------------------------------------
    # Gate 2: Positive Witness Integrity
    # -------------------------------------------------------------------------
    def test_positive_witness_integrity_100_percent(self):
        """100% of positive labels must point to a valid strictly future buy for that user."""
        canon_file = self.root / "witness_test_canon.csv"
        labels_file = self.root / "witness_test_labels.csv"
        manifest_file = self.root / "witness_manifest.json"

        events = []
        seq = 0
        t0 = CAMPAIGN_START_SEC

        # 5 distinct users, alternating actions and purchases
        for u in range(1, 6):
            for step in range(20):
                t = t0 + step * 600
                beh = 3 if step in (5, 12) else (step % 3)
                events.append(self._make_event(seq, t, u, beh))
                seq += 1

        events.sort(key=lambda e: (e["event_ts_ns"], e["seq"]))
        # Re-assign seq to reflect global order
        for idx, e in enumerate(events):
            e["seq"] = idx
            e["source_id"] = str(idx)

        self._write_canonical_csv(canon_file, events)

        stats = stream_causal_labels(
            input_path=canon_file,
            output_path=labels_file,
            manifest_path=manifest_file,
            horizon_sec=7200,
            campaign_end_sec=CAMPAIGN_END_SEC,
        )

        self.assertTrue(stats["zero_contemporaneous_leakage_verified"])
        self.assertTrue(stats["witness_integrity_verified"])
        self.assertEqual(stats["positive_labels"], stats["positive_witness_count"])
        self.assertGreater(stats["positive_labels"], 0)

        # Independently audit witness references directly from output CSV
        events_by_seq = {e["seq"]: e for e in events}
        with open(labels_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s = int(row["seq"])
                label = row["label"]
                wit = row["positive_witness_seq"]

                if label == "1":
                    self.assertTrue(wit and wit.isdigit(), f"Positive label missing witness: {row}")
                    w_seq = int(wit)
                    self.assertIn(w_seq, events_by_seq)
                    witness_event = events_by_seq[w_seq]

                    current_event = events_by_seq[s]
                    self.assertEqual(witness_event["user_id"], current_event["user_id"], "Witness user mismatch")
                    self.assertEqual(witness_event["behavior_code"], 3, "Witness is not a buy event")
                    self.assertGreater(witness_event["event_ts_ns"], current_event["event_ts_ns"], "Witness not strictly future")
                    self.assertLessEqual(
                        witness_event["event_ts_ns"],
                        current_event["event_ts_ns"] + 7200 * 1_000_000_000,
                        "Witness exceeds 2h horizon",
                    )
                else:
                    self.assertEqual(wit, "", "Negative or censored row has witness")

    # -------------------------------------------------------------------------
    # Gate 3: Censoring Invariance
    # -------------------------------------------------------------------------
    def test_tail_censoring_invariance(self):
        """Zero events in the final 2 hours of Day 9 receive a valid label; all have censored == 1 and label == None."""
        t_end = CAMPAIGN_END_SEC
        h_sec = 7200
        censor_threshold = t_end - h_sec  # 1512309599

        canon_file = self.root / "censor_test_canon.csv"
        labels_file = self.root / "censor_test_labels.csv"

        events = [
            # 1 second before censor threshold (should be evaluated)
            self._make_event(0, censor_threshold - 1, 100, 0),
            # Exactly on censor threshold (should be evaluated)
            self._make_event(1, censor_threshold, 100, 0),
            # 1 second after censor threshold (must be censored)
            self._make_event(2, censor_threshold + 1, 100, 0),
            # In tail window with a subsequent buy (must STILL be censored)
            self._make_event(3, censor_threshold + 10, 100, 0),
            self._make_event(4, censor_threshold + 100, 100, 3),  # buy in tail
            # Exactly at campaign end (must be censored)
            self._make_event(5, t_end, 100, 0),
        ]
        self._write_canonical_csv(canon_file, events)

        stream_causal_labels(
            input_path=canon_file,
            output_path=labels_file,
            horizon_sec=h_sec,
            campaign_end_sec=t_end,
        )

        with open(labels_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = {int(r["seq"]): r for r in reader}

        # Evaluated boundary rows (t <= censor_threshold) legitimately witness the buy at seq=4
        self.assertEqual(rows[0]["censored"], "0")
        self.assertEqual(rows[0]["label_valid"], "1")
        self.assertEqual(rows[0]["label"], "1")
        self.assertEqual(rows[0]["positive_witness_seq"], "4")

        self.assertEqual(rows[1]["censored"], "0")
        self.assertEqual(rows[1]["label_valid"], "1")
        self.assertEqual(rows[1]["label"], "1")
        self.assertEqual(rows[1]["positive_witness_seq"], "4")

        # Censored tail rows (t > censor_threshold) must NEVER receive valid labels,
        # even if a buy (seq=4) occurs later in the tail window
        for seq in (2, 3, 4, 5):
            self.assertEqual(rows[seq]["censored"], "1", f"Tail event {seq} not censored")
            self.assertEqual(rows[seq]["label_valid"], "0", f"Tail event {seq} marked valid")
            self.assertEqual(rows[seq]["label"], "", f"Tail event {seq} has label")
            self.assertEqual(rows[seq]["positive_witness_seq"], "", f"Tail event {seq} has witness")

    # -------------------------------------------------------------------------
    # Gate 4: Embargo Window Isolation
    # -------------------------------------------------------------------------
    def test_embargo_window_isolation_and_no_cross_boundary_leakage(self):
        """Assert label windows in train do not cross into validation; validation does not cross into test."""
        # Train window end: 1512050399. Horizon: 7200s. Window reaches up to 1512057599.
        # Validation starts at: 1512057600.
        train_latest_horizon = TRAIN_END_SEC + DEFAULT_HORIZON_SEC
        self.assertLess(
            train_latest_horizon,
            VAL_START_SEC,
            f"Train label window reaches into validation: {train_latest_horizon} >= {VAL_START_SEC}",
        )
        self.assertEqual(train_latest_horizon, EMBARGO_1_END_SEC)

        # Validation window end: 1512136799. Horizon: 7200s. Window reaches up to 1512143999.
        # Test starts at: 1512144000.
        val_latest_horizon = VAL_END_SEC + DEFAULT_HORIZON_SEC
        self.assertLess(
            val_latest_horizon,
            TEST_START_SEC,
            f"Validation label window reaches into test: {val_latest_horizon} >= {TEST_START_SEC}",
        )
        self.assertEqual(val_latest_horizon, EMBARGO_2_END_SEC)

        # Verify on synthesized boundary scenario
        canon_file = self.root / "embargo_canon.csv"
        cohort_file = self.root / "embargo_cohort.csv"

        # User 99 (non-OOD):
        # Event in Train right before embargo: t = 1512050399
        # Buy event in Validation at start of validation: t = 1512057600
        # Time delta: 7201 seconds (> 7200s). Thus, the buy CANNOT trigger Y=1 for the train event!
        u_non_ood = 99
        while is_ood_user(u_non_ood):
            u_non_ood += 1

        events = [
            self._make_event(0, TRAIN_END_SEC, u_non_ood, 0),        # train event
            self._make_event(1, VAL_START_SEC, u_non_ood, 3),        # validation buy
        ]
        self._write_canonical_csv(canon_file, events)

        generate_cohort_splits(
            canonical_input_path=canon_file,
            output_cohort_path=cohort_file,
            horizon_sec=7200,
            campaign_end_sec=CAMPAIGN_END_SEC,
        )

        with open(cohort_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = {int(r["seq"]): r for r in reader}

        self.assertEqual(rows[0]["split"], "train")
        self.assertEqual(rows[0]["label"], "0", "Train event crossed into validation to see buy")
        self.assertEqual(rows[1]["split"], "validation")

    # -------------------------------------------------------------------------
    # Gate 5: Group Floor (>= 30 test groups, >= 10 per class)
    # -------------------------------------------------------------------------
    def test_group_floor_and_test_clusters(self):
        """Test split contains 46 hourly clusters satisfying min_test_groups >= 30 and class floor >= 10."""
        canon_file = self.root / "group_floor_canon.csv"
        cohort_file = self.root / "group_floor_cohort.csv"
        manifest_file = self.root / "group_floor_manifest.json"

        # Construct a synthetic dataset covering all 46 test hours with >= 10 pos and >= 10 neg per hour
        events = []
        seq = 0
        user_base = 200

        for h in range(46):
            hour_ts = TEST_START_SEC + h * 3600
            for i in range(15):
                # 15 positive instances
                uid = user_base + i
                while is_ood_user(uid):
                    uid += 1000
                events.append(self._make_event(seq, hour_ts + i * 10, uid, 0))
                seq += 1
                events.append(self._make_event(seq, hour_ts + i * 10 + 60, uid, 3))  # buy in same hour
                seq += 1

                # 15 negative instances
                uid_neg = user_base + 50 + i
                while is_ood_user(uid_neg):
                    uid_neg += 1000
                events.append(self._make_event(seq, hour_ts + i * 10 + 5, uid_neg, 0))
                seq += 1

        events.sort(key=lambda e: (e["event_ts_ns"], e["seq"]))
        for idx, e in enumerate(events):
            e["seq"] = idx

        self._write_canonical_csv(canon_file, events)

        manifest = generate_cohort_splits(
            canonical_input_path=canon_file,
            output_cohort_path=cohort_file,
            manifest_path=manifest_file,
            horizon_sec=7200,
            campaign_end_sec=CAMPAIGN_END_SEC,
        )

        self.assertGreaterEqual(manifest["test_group_count"], 30)
        self.assertEqual(manifest["test_group_count"], 46)
        self.assertTrue(manifest["acceptance_verifications"]["test_groups_floor_satisfied"])

        # Check every test hour group has >= 10 pos and >= 10 neg
        test_labels_by_group = defaultdict(Counter)
        with open(cohort_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["split"] == "test":
                    test_labels_by_group[row["group_id"]][row["label"]] += 1

        self.assertEqual(len(test_labels_by_group), 46)
        for gid, counts in test_labels_by_group.items():
            self.assertGreaterEqual(counts["0"], 10, f"Group {gid} has < 10 negatives")
            self.assertGreaterEqual(counts["1"], 10, f"Group {gid} has < 10 positives")

    # -------------------------------------------------------------------------
    # Gate 6: Cold OOD Disjointness
    # -------------------------------------------------------------------------
    def test_cold_ood_disjointness_complete(self):
        """Assert zero overlap between OOD user IDs and train / validation user IDs."""
        canon_file = self.root / "ood_canon.csv"
        cohort_file = self.root / "ood_cohort.csv"
        manifest_file = self.root / "ood_manifest.json"

        # Generate mix of OOD and non-OOD users across all days
        events = []
        seq = 0
        for uid in range(1, 201):
            for day in range(9):
                ts = CAMPAIGN_START_SEC + day * 86400 + (uid % 3600)
                events.append(self._make_event(seq, ts, uid, (uid + day) % 4))
                seq += 1

        events.sort(key=lambda e: (e["event_ts_ns"], e["seq"]))
        for idx, e in enumerate(events):
            e["seq"] = idx

        self._write_canonical_csv(canon_file, events)

        manifest = generate_cohort_splits(
            canonical_input_path=canon_file,
            output_cohort_path=cohort_file,
            manifest_path=manifest_file,
        )

        self.assertTrue(manifest["acceptance_verifications"]["cold_ood_disjointness"])

        users_by_split = defaultdict(set)
        with open(cohort_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                users_by_split[row["split"]].add(int(row["user_id"]))

        ood_users = users_by_split["ood"]
        train_users = users_by_split["train"]
        val_users = users_by_split["validation"]
        test_users = users_by_split["test"]

        self.assertGreater(len(ood_users), 0, "No OOD users generated")
        self.assertEqual(len(ood_users & train_users), 0, "OOD leakage into train")
        self.assertEqual(len(ood_users & val_users), 0, "OOD leakage into validation")
        self.assertEqual(len(ood_users & test_users), 0, "OOD leakage into test")

    # -------------------------------------------------------------------------
    # Gate 7: Schema and Test Group Floor Compatibility
    # -------------------------------------------------------------------------
    def test_cohort_schema_and_test_group_floor_compatibility(self):
        """Verify data/cohort.csv has required header and provides >= 30 test groups."""
        canon_file = self.root / "schema_canon.csv"
        cohort_file = self.root / "schema_cohort.csv"

        events = []
        seq = 0
        for h in range(46):
            ts = TEST_START_SEC + h * 3600
            for i in range(2):
                uid = 500 + i
                while is_ood_user(uid):
                    uid += 10
                events.append(self._make_event(seq, ts + i * 10, uid, 3 if i == 0 else 0))
                seq += 1

        events.sort(key=lambda e: (e["event_ts_ns"], e["seq"]))
        for idx, e in enumerate(events):
            e["seq"] = idx
        self._write_canonical_csv(canon_file, events)

        generate_cohort_splits(
            canonical_input_path=canon_file,
            output_cohort_path=cohort_file,
        )

        # 1. Assert exact column presence
        with open(cohort_file, "r", encoding="utf-8") as f:
            header = f.readline().strip().split(",")
            expected_cols = ["seq", "user_id", "event_ts_ns", "split", "group_id", "label", "censored"]
            self.assertEqual(header, expected_cols)

        # 2. Test reading cohort file and verifying independent test units >= 30
        with open(cohort_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            test_units = len({r["group_id"] for r in reader if r["split"] == "test" and r["group_id"]})
        self.assertEqual(test_units, 46)


if __name__ == "__main__":
    unittest.main()
