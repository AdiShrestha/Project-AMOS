"""FABRICATION-DISCLOSURE: tiny label-boundary fixtures, not observations."""
import unittest
from source.preprocessing.labels import future_purchase_labels


class LabelTests(unittest.TestCase):
    def event(self, identifier, time, key, behavior):
        return dict(source_id=identifier, event_ts_ns=time, key=key, behavior_code=behavior)

    def test_current_buy_and_same_time_buy_excluded(self):
        rows = [self.event("a", 0, 1, 3), self.event("b", 0, 1, 0)]
        self.assertEqual([r["label"] for r in future_purchase_labels(rows, 10, 20)], [0, 0])

    def test_future_endpoint_included_and_witness_preserved(self):
        rows = [self.event("a", 0, 1, 0), self.event("b", 10, 1, 3)]
        labels = future_purchase_labels(rows, 10, 20)
        self.assertEqual(labels[0]["label"], 1)
        self.assertEqual(labels[0]["positive_witness_source_id"], "b")
        self.assertEqual(labels[1]["label"], 0)

    def test_censored_label_is_unknown_even_when_buy_observed(self):
        rows = [self.event("a", 15, 1, 0), self.event("b", 19, 1, 3)]
        labels = future_purchase_labels(rows, 10, 20)
        self.assertIsNone(labels[0]["label"])
        self.assertEqual(labels[0]["censored"], 1)

    def test_no_cross_key_witness(self):
        rows = [self.event("a", 0, 1, 0), self.event("b", 10, 2, 3)]
        self.assertEqual(future_purchase_labels(rows, 10, 20)[0]["label"], 0)

    def test_generator_cohort_is_not_lost_between_passes(self):
        rows = (row for row in [self.event("a", 0, 1, 0), self.event("b", 10, 1, 3)])
        self.assertEqual(len(future_purchase_labels(rows, 10, 20)), 2)

    def test_duplicate_identity_rejected(self):
        with self.assertRaises(ValueError):
            future_purchase_labels([self.event("a", 0, 1, 0), self.event("a", 1, 1, 3)], 10, 20)

    def test_cross_key_global_time_regression_rejected(self):
        with self.assertRaises(ValueError):
            future_purchase_labels([self.event("a", 10, 1, 0), self.event("b", 0, 2, 3)], 10, 20)

    def test_empty_or_padded_source_identity_rejected(self):
        for identifier in (" ", " a", "a "):
            with self.assertRaises(ValueError):
                future_purchase_labels([self.event(identifier, 0, 1, 0)], 10, 20)


if __name__ == "__main__":
    unittest.main()
