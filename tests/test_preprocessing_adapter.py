"""
tests/test_preprocessing_adapter.py - Unit tests for preprocessing/adapter.py.
"""

import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.abspath("."))
from preprocessing.adapter import DatasetAdapter, TAOBAO_SCHEMA_ID, ULB_SCHEMA_ID

class TestPreprocessingAdapter(unittest.TestCase):
    def test_unknown_schema_rejected(self):
        with self.assertRaises(ValueError):
            DatasetAdapter("unknown_schema_id")

    def test_taobao_adapter_success(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
            f.write("user_id,item_id,category_id,behavior,timestamp\n")
            f.write("1001,2001,301,pv,1511568000\n")
            f.write("1001,2002,301,cart,1511568001\n")
            f.write("1001,2003,302,buy,1511568002\n")
            f_name = f.name
        try:
            adapter = DatasetAdapter(TAOBAO_SCHEMA_ID)
            events = list(adapter.adapt_csv(f_name))
            self.assertEqual(len(events), 3)
            self.assertEqual(events[0].seq, 0)
            self.assertEqual(events[0].entity_id, 1001)
            self.assertEqual(events[0].behavior_code, 0)
            self.assertEqual(events[0].event_ts_ns, 1511568000 * 1_000_000_000)
            self.assertEqual(events[1].behavior_code, 1)
            self.assertEqual(events[2].behavior_code, 3)
            self.assertEqual(adapter.stats.offered, 3)
            self.assertEqual(adapter.stats.accepted, 3)
            self.assertEqual(adapter.stats.rejected, 0)
        finally:
            os.remove(f_name)

    def test_taobao_adapter_unknown_behavior_fails(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
            f.write("user_id,item_id,category_id,behavior,timestamp\n")
            f.write("1001,2001,301,invalid_code,1511568000\n")
            f_name = f.name
        try:
            adapter = DatasetAdapter(TAOBAO_SCHEMA_ID)
            with self.assertRaises(ValueError):
                list(adapter.adapt_csv(f_name))
        finally:
            os.remove(f_name)

    def test_ulb_adapter_success(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
            f.write("Time,Amount,Class\n")
            f.write("0.0,149.62,0\n")
            f.write("1.5,2.69,1\n")
            f_name = f.name
        try:
            adapter = DatasetAdapter(ULB_SCHEMA_ID)
            events = list(adapter.adapt_csv(f_name, run_origin_ns=1000))
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].entity_id, None)
            self.assertEqual(events[0].amount, 149.62)
            self.assertEqual(events[0].label, 0)
            self.assertEqual(events[0].label_valid, 1)
            self.assertEqual(events[1].amount, 2.69)
            self.assertEqual(events[1].label, 1)
            self.assertEqual(events[1].event_ts_ns, 1000 + 1_500_000_000)
            self.assertEqual(adapter.stats.accepted, 2)
            self.assertEqual(adapter.stats.censored, 0)
        finally:
            os.remove(f_name)

    def test_ulb_adapter_missing_column_fails(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
            f.write("Time,Amount\n")
            f.write("0.0,149.62\n")
            f_name = f.name
        try:
            adapter = DatasetAdapter(ULB_SCHEMA_ID)
            with self.assertRaises(ValueError):
                list(adapter.adapt_csv(f_name))
        finally:
            os.remove(f_name)

    def test_sequence_source_requires_declared_column(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
            f.write("user_id,item_id,category_id,behavior,timestamp\n")
            f.write("1001,2001,301,pv,1511568000\n")
            f_name = f.name
        try:
            adapter = DatasetAdapter(TAOBAO_SCHEMA_ID, sequence_source="source_column")
            with self.assertRaises(ValueError):
                list(adapter.adapt_csv(f_name))
            self.assertEqual(adapter.stats.rejected, 1)
        finally:
            os.remove(f_name)

    def test_tie_order_is_sequence_order_and_backward_time_fails(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
            f.write("user_id,item_id,category_id,behavior,timestamp\n")
            f.write("1001,2001,301,pv,1511568000\n")
            f.write("1001,2002,301,cart,1511568000\n")
            f_name = f.name
        try:
            events = list(DatasetAdapter(TAOBAO_SCHEMA_ID).adapt_csv(f_name))
            self.assertEqual([e.seq for e in events], [0, 1])
            self.assertEqual(events[0].event_ts_ns, events[1].event_ts_ns)
        finally:
            os.remove(f_name)

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
            f.write("user_id,item_id,category_id,behavior,timestamp\n")
            f.write("1001,2001,301,pv,1511568001\n")
            f.write("1001,2002,301,cart,1511568000\n")
            f_name = f.name
        try:
            with self.assertRaises(ValueError):
                list(DatasetAdapter(TAOBAO_SCHEMA_ID).adapt_csv(f_name))
        finally:
            os.remove(f_name)

    def test_horizon_marks_end_rows_censored(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
            f.write("Time,Amount,Class\n")
            f.write("0.0,1.0,0\n")
            f.write("1.5,2.0,1\n")
            f_name = f.name
        try:
            adapter = DatasetAdapter(
                ULB_SCHEMA_ID,
                prediction_horizon_ns=1_000_000_000,
                observation_end_ns=2_000_000_000,
            )
            events = list(adapter.adapt_csv(f_name))
            self.assertEqual(events[0].label_valid, 1)
            self.assertEqual(events[0].censored, 0)
            self.assertEqual(events[1].label_valid, 0)
            self.assertEqual(events[1].censored, 1)
            self.assertEqual(adapter.stats.censored, 1)
        finally:
            os.remove(f_name)

if __name__ == "__main__":
    unittest.main()
