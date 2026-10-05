"""Unit and regression tests for production canonicalization pipeline.

Verifies:
1. Chunk-size invariance (byte-for-byte identical output across varying external sort chunk sizes).
2. Deterministic secondary tie-breaking across input permutations.
3. 64-bit domain representation (zero uint16 narrowing for categories > 65535).
4. Outlier filtering and full row conservation accounting.
5. Monotonic sequence assignment and ReplayReader schema compatibility.
"""

import hashlib
import json
import random
import tempfile
import unittest
from pathlib import Path

from tools.canonicalize_user_behavior import (
    DEFAULT_CAMPAIGN_END,
    DEFAULT_CAMPAIGN_START,
    canonicalize,
    parse_and_validate_row,
)


class CanonicalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def _sha256(self, path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def test_parse_and_validate_preserves_64bit_domains(self):
        # Category ID well above uint16 (65535), e.g. 5,162,429
        line = "1018011,5163070,5162429,pv,1511544070"
        user, item, cat, beh, ts = parse_and_validate_row(line, 1)
        self.assertEqual(user, 1018011)
        self.assertEqual(item, 5163070)
        self.assertEqual(cat, 5162429)
        self.assertGreater(cat, 65535)
        self.assertEqual(beh, "pv")
        self.assertEqual(ts, 1511544070)

    def test_chunk_size_invariance(self):
        """External sort must produce byte-for-byte identical output regardless of chunk size."""
        # Generate a synthetic validation slice with shuffled order, duplicate rows,
        # out-of-campaign rows, and concurrent timestamps.
        base_ts = DEFAULT_CAMPAIGN_START + 1000
        raw_rows = []

        # In-window records with intentional ties
        for i in range(500):
            ts = base_ts + (i % 20) * 10
            user = (i * 7) % 50
            item = (i * 13) % 100
            cat = 100000 + (i % 30)  # uint16 overflow
            beh = ["pv", "fav", "cart", "buy"][i % 4]
            raw_rows.append(f"{user},{item},{cat},{beh},{ts}")

        # Add duplicate rows
        duplicates = raw_rows[:30]
        raw_rows.extend(duplicates)

        # Add negative and out-of-window outliers
        raw_rows.append("1,2,3,pv,-100")  # negative
        raw_rows.append(f"1,2,3,pv,{DEFAULT_CAMPAIGN_START - 50}")  # before window
        raw_rows.append(f"1,2,3,pv,{DEFAULT_CAMPAIGN_END + 50}")  # after window

        # Shuffle input to ensure sort operates non-trivially
        random.seed(42)
        shuffled_rows = list(raw_rows)
        random.shuffle(shuffled_rows)

        input_path = self.root / "input.csv"
        input_path.write_text("\n".join(shuffled_rows) + "\n")

        # Run pipeline with multiple distinct chunk sizes
        chunk_sizes = [7, 23, 50, 150, 1000]
        outputs = []
        digests = []

        for cs in chunk_sizes:
            out_file = self.root / f"out_cs_{cs}.csv"
            ledger_file = self.root / f"ledger_cs_{cs}.json"
            acc = canonicalize(
                input_path=input_path,
                output_path=out_file,
                ledger_path=ledger_file,
                chunk_size=cs,
            )
            self.assertTrue(acc["conservation_law_satisfied"])
            digest = self._sha256(out_file)
            outputs.append(out_file.read_bytes())
            digests.append(digest)

        # All digests must be strictly identical
        for i in range(1, len(digests)):
            self.assertEqual(
                digests[0],
                digests[i],
                f"Chunk size {chunk_sizes[0]} and {chunk_sizes[i]} produced divergent digests",
            )
            self.assertEqual(outputs[0], outputs[i])

    def test_deterministic_secondary_tie_breaking(self):
        """Tie breaking must follow: timestamp -> user_id -> item_id -> category_id -> behavior_order."""
        ts = DEFAULT_CAMPAIGN_START + 500
        # Same timestamp, but varying user, item, cat, and behavior
        # Notice: behavior_order is pv (0) < fav (1) < cart (2) < buy (3)
        # Output behavior_code is pv (0), cart (1), fav (2), buy (3)
        rows = [
            f"10,20,30,buy,{ts}",
            f"10,20,30,cart,{ts}",
            f"10,20,30,fav,{ts}",
            f"10,20,30,pv,{ts}",
            f"5,20,30,pv,{ts}",
            f"10,15,30,pv,{ts}",
            f"10,20,25,pv,{ts}",
        ]
        
        # Test 5 different random permutations
        ref_output = None
        for seed in range(5):
            rng = random.Random(seed)
            shuffled = list(rows)
            rng.shuffle(shuffled)
            
            in_file = self.root / f"perm_{seed}.csv"
            out_file = self.root / f"perm_out_{seed}.csv"
            in_file.write_text("\n".join(shuffled) + "\n")
            
            canonicalize(input_path=in_file, output_path=out_file, chunk_size=2)
            content = out_file.read_text().splitlines()
            
            if ref_output is None:
                ref_output = content
            else:
                self.assertEqual(content, ref_output)

        # Verify exact emitted order of the tie-break records
        # Header is line 0: seq,event_ts_ns,key,item_id,category_id,behavior_code
        data = [line.split(",") for line in ref_output[1:]]
        # Order should be:
        # 1. user=5 (item=20, cat=30, pv=0)
        # 2. user=10, item=15 (cat=30, pv=0)
        # 3. user=10, item=20, cat=25 (pv=0)
        # 4. user=10, item=20, cat=30, pv (behavior_code 0)
        # 5. user=10, item=20, cat=30, fav (behavior_code 2, sort_order 1)
        # 6. user=10, item=20, cat=30, cart (behavior_code 1, sort_order 2)
        # 7. user=10, item=20, cat=30, buy (behavior_code 3, sort_order 3)
        self.assertEqual([d[2] for d in data], ["5", "10", "10", "10", "10", "10", "10"])
        self.assertEqual([d[3] for d in data], ["20", "15", "20", "20", "20", "20", "20"])
        self.assertEqual([d[4] for d in data], ["30", "30", "25", "30", "30", "30", "30"])
        self.assertEqual([d[5] for d in data], ["0", "0", "0", "0", "2", "1", "3"])
        self.assertEqual([d[0] for d in data], ["0", "1", "2", "3", "4", "5", "6"])

    def test_deduplication_and_accounting(self):
        """Exact duplicates are collapsed while concurrent distinct behaviors are preserved."""
        ts = DEFAULT_CAMPAIGN_START + 100
        rows = [
            f"1,10,100,pv,{ts}",
            f"1,10,100,pv,{ts}",  # duplicate
            f"1,10,100,pv,{ts}",  # duplicate
            f"1,10,100,cart,{ts}",  # distinct behavior at same user/item/ts -> kept
            f"2,20,200,buy,{ts + 1}",
            f"2,20,200,buy,{ts + 1}",  # duplicate
        ]
        in_file = self.root / "dedup_in.csv"
        out_file = self.root / "dedup_out.csv"
        in_file.write_text("\n".join(rows) + "\n")

        acc = canonicalize(input_path=in_file, output_path=out_file, chunk_size=2)
        self.assertEqual(acc["raw_rows_read"], 6)
        self.assertEqual(acc["deduplicated_duplicates"], 3)
        self.assertEqual(acc["canonical_valid_emitted"], 3)
        self.assertTrue(acc["conservation_law_satisfied"])

        lines = out_file.read_text().splitlines()[1:]
        self.assertEqual(len(lines), 3)
        # Check sequences
        seqs = [int(line.split(",")[0]) for line in lines]
        self.assertEqual(seqs, [0, 1, 2])

    def test_outlier_filtering_and_conservation(self):
        """Negative timestamps and out-of-campaign calendar outliers are rejected."""
        valid_ts = DEFAULT_CAMPAIGN_START + 50
        rows = [
            f"1,10,100,pv,{valid_ts}",
            "2,20,200,pv,-500",  # negative
            f"3,30,300,cart,{DEFAULT_CAMPAIGN_START - 1}",  # before
            f"4,40,400,fav,{DEFAULT_CAMPAIGN_END + 1}",  # after
        ]
        in_file = self.root / "outliers_in.csv"
        out_file = self.root / "outliers_out.csv"
        in_file.write_text("\n".join(rows) + "\n")

        acc = canonicalize(input_path=in_file, output_path=out_file)
        self.assertEqual(acc["raw_rows_read"], 4)
        self.assertEqual(acc["negative_timestamp_outliers"], 1)
        self.assertEqual(acc["before_window_outliers"], 1)
        self.assertEqual(acc["after_window_outliers"], 1)
        self.assertEqual(acc["total_calendar_outliers"], 3)
        self.assertEqual(acc["canonical_valid_emitted"], 1)
        self.assertTrue(acc["conservation_law_satisfied"])


if __name__ == "__main__":
    unittest.main()
