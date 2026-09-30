"""Strict future-purchase label reference. Independent of runtime features.

This function operates on an already admitted, canonically ordered cohort.
It does not download, authenticate, sample, deduplicate or split a dataset.
"""
from bisect import bisect_right
from collections import defaultdict


def future_purchase_labels(events, horizon_ns, observation_end_ns):
    """Return one record per input with y=1 iff a buy exists in (t, t+H].

    A censored outcome has label=None, never a negative label. The producing
    buy source ID is retained for every positive; current/same-time purchases
    are excluded even when source order differs. Per-key histories are checked.
    """
    if type(horizon_ns) is not int or horizon_ns <= 0:
        raise ValueError("positive integer horizon required")
    if type(observation_end_ns) is not int or observation_end_ns < 0:
        raise ValueError("nonnegative observation end required")
    events = list(events)  # Both passes see the same cohort, including generators.
    buys, previous, seen = defaultdict(list), {}, set()
    for event in events:
        identifier = event["source_id"]
        timestamp, key, behavior = event["event_ts_ns"], event["key"], event["behavior_code"]
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("missing or duplicate source identity")
        if type(timestamp) is not int or not 0 <= timestamp <= observation_end_ns:
            raise ValueError("invalid event timestamp")
        if type(key) is not int or key < 0 or type(behavior) is not int or behavior not in range(4):
            raise ValueError("invalid key/behavior")
        if key in previous and timestamp < previous[key]:
            raise ValueError("per-key time regression")
        seen.add(identifier)
        previous[key] = timestamp
        if behavior == 3:
            buys[key].append((timestamp, identifier))
    times = {key: [timestamp for timestamp, _ in records] for key, records in buys.items()}
    result = []
    for event in events:
        t, key = event["event_ts_ns"], event["key"]
        end = t + horizon_ns
        record = {"source_id": event["source_id"], "event_ts_ns": t, "label_window_end_ns": end,
                  "label": None, "label_valid": 0, "censored": 1, "positive_witness_source_id": None}
        if end <= observation_end_ns:
            index = bisect_right(times.get(key, []), t)
            positive = index < len(buys[key]) and buys[key][index][0] <= end
            record.update(label=int(positive), label_valid=1, censored=0,
                          positive_witness_source_id=buys[key][index][1] if positive else None)
        result.append(record)
    return result
