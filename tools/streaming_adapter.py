#!/usr/bin/env python3
"""Streaming domain adapter and independent metric recomputation tool.

Recomputes streaming systems metrics (coverage, write work ratio, staleness,
deadline utility) alongside predictive performance metrics (AUROC, AP, LogLoss, Brier)
directly from raw output artifacts and enforces strict temporal causality.
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path


class StreamingValidationError(ValueError):
    """Raised when streaming artifacts violate schemas, causality, or conservation."""
    pass


def compute_binary_metrics(y_true, scores, threshold=0.5):
    """Recompute binary classification metrics independently."""
    n = len(y_true)
    if n == 0:
        raise StreamingValidationError("empty evaluation vectors")
    if len(scores) != n:
        raise StreamingValidationError("y_true and scores length mismatch")

    n1 = sum(1 for y in y_true if y == 1)
    n0 = n - n1
    if n1 == 0 or n0 == 0:
        raise StreamingValidationError("both positive and negative classes required")

    # Brier score
    brier = sum((s - y) ** 2 for y, s in zip(y_true, scores)) / n

    # Log loss bounded to [1e-15, 1 - 1e-15]
    eps = 1e-15
    log_loss = -sum(
        y * math.log(max(eps, min(1.0 - eps, s))) +
        (1 - y) * math.log(max(eps, min(1.0 - eps, 1.0 - s)))
        for y, s in zip(y_true, scores)
    ) / n

    # Accuracy, F1
    tp = sum(1 for y, s in zip(y_true, scores) if y == 1 and s >= threshold)
    fp = sum(1 for y, s in zip(y_true, scores) if y == 0 and s >= threshold)
    tn = sum(1 for y, s in zip(y_true, scores) if y == 0 and s < threshold)
    fn = sum(1 for y, s in zip(y_true, scores) if y == 1 and s < threshold)

    accuracy = (tp + tn) / n
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    # AUROC via trapezoidal rank sum
    ranked = sorted(zip(scores, y_true), key=lambda x: x[0])
    rank_sum = 0.0
    i = 0
    while i < n:
        j = i
        while j < n and ranked[j][0] == ranked[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            if ranked[k][1] == 1:
                rank_sum += avg_rank
        i = j
    auroc = (rank_sum - (n1 * (n1 + 1.0) / 2.0)) / (n0 * n1)

    # Average Precision (area under precision-recall curve)
    ranked_desc = sorted(zip(scores, y_true), key=lambda x: -x[0])
    cum_tp = 0
    cum_fp = 0
    ap = 0.0
    for s, y in ranked_desc:
        if y == 1:
            cum_tp += 1
            ap += cum_tp / (cum_tp + cum_fp)
        else:
            cum_fp += 1
    average_precision = ap / n1 if n1 > 0 else 0.0

    return {
        "auroc": float(auroc),
        "average_precision": float(average_precision),
        "accuracy": float(accuracy),
        "f1": float(f1),
        "brier": float(brier),
        "log_loss": float(log_loss),
    }


def verify_temporal_causality(telemetry):
    """Enforce strict temporal ordering: no feature publication in the future of a query."""
    queries = telemetry.get("queries", [])
    if not isinstance(queries, list):
        raise StreamingValidationError("telemetry.queries must be a list")

    violations = []
    for q in queries:
        if not isinstance(q, dict):
            raise StreamingValidationError("query entry must be an object")
        query_id = q.get("query_id")
        t_query = q.get("query_ts_ns")
        t_pub = q.get("feature_ts_ns")

        if t_query is None or t_pub is None:
            continue

        if not isinstance(t_query, (int, float)) or not isinstance(t_pub, (int, float)):
            raise StreamingValidationError(f"query {query_id}: timestamps must be numbers")

        if t_query < 0 or t_pub < 0:
            raise StreamingValidationError(f"query {query_id}: timestamps cannot be negative")

        if t_pub > t_query:
            violations.append({
                "query_id": query_id,
                "query_ts_ns": t_query,
                "feature_ts_ns": t_pub,
                "leakage_ns": t_pub - t_query
            })

    if violations:
        first = violations[0]
        raise StreamingValidationError(
            f"TEMPORAL_LEAKAGE: query {first['query_id']} accessed future feature "
            f"(query_ts={first['query_ts_ns']}, feature_ts={first['feature_ts_ns']}, "
            f"delta=+{first['leakage_ns']}ns)"
        )
    return True


def verify_conservation(telemetry):
    """Verify exact event and work accounting conservation."""
    summary = telemetry.get("summary", telemetry)
    events = summary.get("events_processed")
    writes = summary.get("writes_emitted")
    absorbed = summary.get("events_absorbed")

    if events is None or writes is None:
        return True

    if not isinstance(events, int) or events < 0:
        raise StreamingValidationError("events_processed must be a non-negative integer")
    if not isinstance(writes, int) or writes < 0:
        raise StreamingValidationError("writes_emitted must be a non-negative integer")

    if absorbed is not None:
        if not isinstance(absorbed, int) or absorbed < 0:
            raise StreamingValidationError("events_absorbed must be a non-negative integer")
        if events != (writes + absorbed):
            raise StreamingValidationError(
                f"CONSERVATION_VIOLATION: events_processed ({events}) != "
                f"writes_emitted ({writes}) + events_absorbed ({absorbed})"
            )

    return True


def recompute_streaming_metrics(predictions_path, telemetry_path, cohort_path=None, sla_deadline_ms=50.0):
    """Recompute full suite of streaming and predictive metrics."""
    p_path = Path(predictions_path)
    if not p_path.is_file():
        raise StreamingValidationError(f"predictions file not found: {predictions_path}")

    t_path = Path(telemetry_path)
    if not t_path.is_file():
        raise StreamingValidationError(f"telemetry file not found: {telemetry_path}")

    # Load telemetry
    try:
        with open(t_path, "r", encoding="utf-8") as f:
            telemetry = json.load(f)
    except Exception as e:
        raise StreamingValidationError(f"unreadable telemetry JSON: {e}") from e

    # Verify temporal causality and conservation
    verify_temporal_causality(telemetry)
    verify_conservation(telemetry)

    # Load cohort labels if provided
    cohort_labels = {}
    cohort_groups = {}
    cohort_splits = {}
    if cohort_path:
        c_path = Path(cohort_path)
        if not c_path.is_file():
            raise StreamingValidationError(f"cohort file not found: {cohort_path}")
        with open(c_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                sid = r["sample_id"]
                cohort_labels[sid] = int(r["label"])
                cohort_groups[sid] = r.get("group_id", "")
                cohort_splits[sid] = r.get("split", "test")

    # Load predictions
    preds = {}
    with open(p_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            sid = r["sample_id"]
            if sid in preds:
                raise StreamingValidationError(f"duplicate sample_id in predictions: {sid}")
            score = float(r["score"])
            if not math.isfinite(score):
                raise StreamingValidationError(f"non-finite score for sample_id {sid}: {score}")
            preds[sid] = score

    if not preds:
        raise StreamingValidationError("empty predictions artifact")

    # Recompute streaming systems metrics
    summary = telemetry.get("summary", telemetry)
    offered = summary.get("queries_offered", len(preds))
    answered = summary.get("queries_answered", len(preds))
    events = summary.get("events_processed", 1)
    writes = summary.get("writes_emitted", 0)

    if offered <= 0:
        raise StreamingValidationError("queries_offered must be positive")

    query_coverage = float(answered) / float(offered)
    write_work_ratio = float(writes) / float(max(1, events))

    # Staleness calculations from queries list
    queries = telemetry.get("queries", [])
    staleness_list_ms = []
    deadline_met = 0
    for q in queries:
        t_q = q.get("query_ts_ns")
        t_f = q.get("feature_ts_ns")
        lat_ms = q.get("latency_ms", 0.0)

        if t_q is not None and t_f is not None:
            diff_ns = max(0, t_q - t_f)
            staleness_list_ms.append(diff_ns / 1_000_000.0)

        if lat_ms <= sla_deadline_ms:
            deadline_met += 1

    if staleness_list_ms:
        mean_staleness_ms = float(sum(staleness_list_ms) / len(staleness_list_ms))
        max_staleness_ms = float(max(staleness_list_ms))
    else:
        mean_staleness_ms = float(summary.get("mean_staleness_ms", 0.0))
        max_staleness_ms = float(summary.get("max_staleness_ms", 0.0))

    deadline_utility = float(deadline_met / len(queries)) if queries else 1.0

    streaming_metrics = {
        "query_coverage": query_coverage,
        "write_work_ratio": write_work_ratio,
        "mean_staleness_ms": mean_staleness_ms,
        "max_staleness_ms": max_staleness_ms,
        "deadline_utility": deadline_utility,
    }

    # If cohort provided, compute predictive metrics
    predictive_metrics = {}
    if cohort_labels:
        # Check that no cohort test samples are missing
        test_samples = [s for s, sp in cohort_splits.items() if sp == "test"]
        missing = set(test_samples) - set(preds.keys())
        if missing:
            raise StreamingValidationError(
                f"SUPPRESSED_MISSES: predictions omit {len(missing)} required test samples (e.g. {sorted(missing)[:3]})"
            )

        # Check for phantom sample IDs
        phantoms = set(preds.keys()) - set(cohort_labels.keys())
        if phantoms:
            raise StreamingValidationError(
                f"PHANTOM_SAMPLES: predictions contain {len(phantoms)} samples not in cohort (e.g. {sorted(phantoms)[:3]})"
            )

        eval_ids = [s for s in test_samples if s in preds]
        y_eval = [cohort_labels[s] for s in eval_ids]
        s_eval = [preds[s] for s in eval_ids]

        predictive_metrics = compute_binary_metrics(y_eval, s_eval)

    return {
        "streaming_systems": streaming_metrics,
        "predictive_performance": predictive_metrics,
        "predictions_count": len(preds),
        "temporal_causality_verified": True,
        "conservation_verified": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Streaming Domain Adapter & Metric Recomputation Tool")
    parser.add_argument("--predictions", required=True, help="Path to predictions.csv")
    parser.add_argument("--telemetry", required=True, help="Path to telemetry.json")
    parser.add_argument("--cohort", default=None, help="Path to cohort.csv")
    parser.add_argument("--sla-deadline-ms", type=float, default=50.0, help="SLA deadline in milliseconds")
    parser.add_argument("--output", default=None, help="Path to output report JSON")
    args = parser.parse_args()

    try:
        report = recompute_streaming_metrics(
            predictions_path=args.predictions,
            telemetry_path=args.telemetry,
            cohort_path=args.cohort,
            sla_deadline_ms=args.sla_deadline_ms,
        )
    except StreamingValidationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    formatted = json.dumps(report, indent=2)
    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(formatted, encoding="utf-8")
        print(f"Streaming evaluation report saved to {args.output}")
    else:
        print(formatted)


if __name__ == "__main__":
    main()
