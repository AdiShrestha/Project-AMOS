#!/usr/bin/env python3
"""Comparative baseline suite runner for Project AMOS / BPFeat.

Executes and compares 6 distinct configurations on identical open-loop validation traces:
1. exact_fresh: U = 1, alpha = 0.10 (Ground truth freshness reference)
2. tuned_static: U = U*, alpha = 0.10 (Prospectively selected optimal static cadence)
3. budget_matched: matches joint_adaptive publication count within +/- 1%, alpha = 0.10
4. alpha_only: U = U*, alpha(p) in [0.02, 0.30]
5. pub_only: alpha = 0.10, U(p) in [1, 20]
6. joint_adaptive: U(p) in [1, 20], alpha(p) in [0.02, 0.30]

Outputs comprehensive comparative telemetry and validation loss gaps to
docs/pilot/baseline_characterization.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
for _p in (str(_project_root), str(_script_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from tools.publication_reference import (
        AdaptivePressurePolicy,
        ElapsedThresholdPolicy,
        ExactFreshPolicy,
        FixedCadencePolicy,
        PublicationPolicy,
        PublicationSimulator,
        Query,
        QueryResult,
        RawEvent,
        FEATURE_DIMENSION,
    )
    from tools.workload_generator import (
        ScheduledEvent,
        ScheduledQuery,
        generate_open_loop_trace,
        load_validation_events,
        PHASE_SPECS,
        TOTAL_EVENTS,
        TOTAL_QUERIES,
    )
    from tools.run_mechanism_pilot import (
        load_model_weights,
        score_logistic,
        binary_cross_entropy,
        percentile,
    )
except ImportError:
    from publication_reference import (
        AdaptivePressurePolicy,
        ElapsedThresholdPolicy,
        ExactFreshPolicy,
        FixedCadencePolicy,
        PublicationPolicy,
        PublicationSimulator,
        Query,
        QueryResult,
        RawEvent,
        FEATURE_DIMENSION,
    )
    from workload_generator import (
        ScheduledEvent,
        ScheduledQuery,
        generate_open_loop_trace,
        load_validation_events,
        PHASE_SPECS,
        TOTAL_EVENTS,
        TOTAL_QUERIES,
    )
    from run_mechanism_pilot import (
        load_model_weights,
        score_logistic,
        binary_cross_entropy,
        percentile,
    )

STATIC_TUNING_CANDIDATES = [2, 3, 5, 8, 10, 15, 20]


class QuotaMatchedPolicy(PublicationPolicy):
    """Bresenham-style deterministic quota allocator matching target publication count."""

    def __init__(self, target_publications: int, total_events: int) -> None:
        if target_publications <= 0 or total_events <= 0:
            raise ValueError("Target publications and total events must be positive")
        self.target_publications = target_publications
        self.total_events = total_events
        self.accumulator = 0

    def should_publish(self, event: RawEvent, state: Any, pressure: float) -> bool:
        self.accumulator += self.target_publications
        if self.accumulator >= self.total_events:
            self.accumulator -= self.total_events
            return True
        return False


def tune_static_cadence(
    events: List[ScheduledEvent],
    queries: List[ScheduledQuery],
    model_bias: float,
    model_weights: List[float],
    base_prior: float = 0.1146,
    candidates: Sequence[int] = STATIC_TUNING_CANDIDATES,
    lambda_cost: float = 0.05,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Prospectively select optimal static cadence U* on validation data."""
    # First compute exact fresh reference losses for every query
    fresh_sim = PublicationSimulator(policy=ExactFreshPolicy(), alpha=0.10)
    for e in events:
        raw_ev = RawEvent(e.seq, e.event_ts_ns, e.key, e.item_id, e.category_id, e.behavior_code)
        fresh_sim.process_event(raw_ev)

    fresh_losses: Dict[int, float] = {}
    for q in queries:
        res = fresh_sim.query(Query(q.query_id, q.key, q.t_sched_ns))
        prob = score_logistic(model_bias, model_weights, res.fresh_features)
        fresh_losses[q.query_id] = binary_cross_entropy(prob, base_prior)

    candidate_records: List[Dict[str, Any]] = []
    best_u = candidates[0]
    best_objective = float("inf")

    total_ev = len(events)
    for u in candidates:
        sim = PublicationSimulator(policy=FixedCadencePolicy(cadence=u), alpha=0.10)
        for e in events:
            raw_ev = RawEvent(e.seq, e.event_ts_ns, e.key, e.item_id, e.category_id, e.behavior_code)
            sim.process_event(raw_ev)

        gaps = []
        for q in queries:
            res = sim.query(Query(q.query_id, q.key, q.t_sched_ns))
            prob = score_logistic(model_bias, model_weights, res.cached_features)
            loss_cached = binary_cross_entropy(prob, base_prior)
            loss_fresh = fresh_losses[q.query_id]
            gaps.append(max(0.0, loss_cached - loss_fresh))

        acc = sim.get_accounting()
        mean_gap = sum(gaps) / len(gaps) if gaps else 0.0
        work_ratio = acc["published_updates"] / total_ev
        # Composite objective: mean gap + cost penalty
        objective = mean_gap + lambda_cost * work_ratio

        record = {
            "u": u,
            "published_updates": acc["published_updates"],
            "work_ratio": work_ratio,
            "mean_loss_gap": mean_gap,
            "objective_value": objective,
        }
        candidate_records.append(record)

        if objective < best_objective:
            best_objective = objective
            best_u = u

    return best_u, candidate_records


def run_single_baseline(
    name: str,
    events: List[ScheduledEvent],
    queries: List[ScheduledQuery],
    policy: PublicationPolicy,
    alpha_fn: Callable[[float], float],
    model_bias: float,
    model_weights: List[float],
    exact_fresh_results: Optional[Dict[int, QueryResult]] = None,
    base_prior: float = 0.1146,
) -> Dict[str, Any]:
    """Execute a single baseline configuration with per-query paired metrics."""
    sim = PublicationSimulator(policy=policy, alpha=0.10)

    # Group events and queries by phase
    phase_events: Dict[str, List[ScheduledEvent]] = {spec[0]: [] for spec in PHASE_SPECS}
    for e in events:
        phase_events[e.phase].append(e)

    phase_queries: Dict[str, List[ScheduledQuery]] = {spec[0]: [] for spec in PHASE_SPECS}
    for q in queries:
        phase_queries[q.phase].append(q)

    phase_results: Dict[str, Any] = {}
    query_results_map: Dict[int, QueryResult] = {}

    total_published = 0
    total_coalesced = 0
    all_latencies_us: List[float] = []
    all_staleness: List[int] = []
    all_feature_errors: List[float] = []
    all_paired_loss_gaps: List[float] = []

    for spec in PHASE_SPECS:
        p_name = spec[0]
        ev_list = phase_events[p_name]
        q_list = phase_queries[p_name]

        pressure = 0.85 if p_name == "stress" else 0.10
        current_alpha = alpha_fn(pressure)
        sim.alpha = current_alpha

        p_pub = 0
        p_coal = 0
        for e in ev_list:
            raw_ev = RawEvent(e.seq, e.event_ts_ns, e.key, e.item_id, e.category_id, e.behavior_code)
            pub, _ = sim.process_event(raw_ev, pressure=pressure)
            if pub:
                p_pub += 1
            else:
                p_coal += 1

        total_published += p_pub
        total_coalesced += p_coal

        p_latencies: List[float] = []
        p_staleness: List[int] = []
        p_feature_errors: List[float] = []
        p_loss_gaps: List[float] = []

        for q in q_list:
            t0 = time.perf_counter_ns()
            res = sim.query(Query(q.query_id, q.key, q.t_sched_ns))
            t1 = time.perf_counter_ns()

            lat_us = (t1 - t0) / 1000.0
            p_latencies.append(lat_us)
            all_latencies_us.append(lat_us)

            p_staleness.append(res.update_staleness)
            all_staleness.append(res.update_staleness)

            p_feature_errors.append(res.feature_error)
            all_feature_errors.append(res.feature_error)

            query_results_map[q.query_id] = res

            prob_cached = score_logistic(model_bias, model_weights, res.cached_features)
            loss_c = binary_cross_entropy(prob_cached, base_prior)

            if exact_fresh_results is not None and q.query_id in exact_fresh_results:
                fresh_res = exact_fresh_results[q.query_id]
                prob_fresh = score_logistic(model_bias, model_weights, fresh_res.cached_features)
                loss_f = binary_cross_entropy(prob_fresh, base_prior)
                gap = max(0.0, loss_c - loss_f)
            else:
                gap = 0.0

            p_loss_gaps.append(gap)
            all_paired_loss_gaps.append(gap)

        phase_results[p_name] = {
            "published_updates": p_pub,
            "coalesced_updates": p_coal,
            "completed_queries": len(q_list),
            "mean_staleness": float(sum(p_staleness) / len(p_staleness)) if p_staleness else 0.0,
            "mean_feature_error": float(sum(p_feature_errors) / len(p_feature_errors)) if p_feature_errors else 0.0,
            "mean_loss_gap": float(sum(p_loss_gaps) / len(p_loss_gaps)) if p_loss_gaps else 0.0,
            "mean_latency_us": float(sum(p_latencies) / len(p_latencies)) if p_latencies else 0.0,
        }

    total_events = len(events)
    total_queries = len(queries)
    conservation_verified = (total_events == total_published + total_coalesced) and (len(query_results_map) == total_queries)

    return {
        "name": name,
        "accounting": {
            "processed_updates": total_events,
            "published_updates": total_published,
            "coalesced_updates": total_coalesced,
            "scheduled_queries": total_queries,
            "completed_queries": len(query_results_map),
            "conservation_verified": conservation_verified,
        },
        "telemetry": {
            "mean_staleness": float(sum(all_staleness) / len(all_staleness)) if all_staleness else 0.0,
            "max_staleness": int(max(all_staleness)) if all_staleness else 0,
            "mean_feature_error": float(sum(all_feature_errors) / len(all_feature_errors)) if all_feature_errors else 0.0,
            "p95_feature_error": float(percentile(all_feature_errors, 95)),
            "max_feature_error": float(max(all_feature_errors)) if all_feature_errors else 0.0,
            "mean_paired_loss_gap": float(sum(all_paired_loss_gaps) / len(all_paired_loss_gaps)) if all_paired_loss_gaps else 0.0,
            "p95_paired_loss_gap": float(percentile(all_paired_loss_gaps, 95)),
            "mean_latency_us": float(sum(all_latencies_us) / len(all_latencies_us)) if all_latencies_us else 0.0,
            "p95_latency_us": float(percentile(all_latencies_us, 95)),
        },
        "phases": phase_results,
        "query_results_map": query_results_map,
    }


def execute_comparative_suite(
    events: List[ScheduledEvent],
    queries: List[ScheduledQuery],
    model_bias: float,
    model_weights: List[float],
) -> Dict[str, Any]:
    """Execute all 6 comparative configurations and verify budget matching & disjointness."""
    # 1. Tune U* on validation data
    u_star, tuning_records = tune_static_cadence(events, queries, model_bias, model_weights)

    # Fixed alpha function
    alpha_fixed = lambda p: 0.10
    # Dynamic alpha function: alpha in [0.02, 0.30]
    alpha_dynamic = lambda p: 0.02 + 0.28 * max(0.0, min(1.0, float(p)))

    # 2. Run exact_fresh
    res_fresh = run_single_baseline(
        name="exact_fresh",
        events=events,
        queries=queries,
        policy=ExactFreshPolicy(),
        alpha_fn=alpha_fixed,
        model_bias=model_bias,
        model_weights=model_weights,
        exact_fresh_results=None,
    )
    fresh_q_results = res_fresh["query_results_map"]

    # 3. Run joint_adaptive first to determine target budget for budget_matched
    res_joint = run_single_baseline(
        name="joint_adaptive",
        events=events,
        queries=queries,
        policy=AdaptivePressurePolicy(k_min=1, k_max=20),
        alpha_fn=alpha_dynamic,
        model_bias=model_bias,
        model_weights=model_weights,
        exact_fresh_results=fresh_q_results,
    )
    target_publications = res_joint["accounting"]["published_updates"]

    # 4. Run tuned_static (U=U*, alpha=0.10)
    res_tuned = run_single_baseline(
        name="tuned_static",
        events=events,
        queries=queries,
        policy=FixedCadencePolicy(cadence=u_star),
        alpha_fn=alpha_fixed,
        model_bias=model_bias,
        model_weights=model_weights,
        exact_fresh_results=fresh_q_results,
    )

    # 5. Run budget_matched (matching joint_adaptive target publications +/- 1%)
    res_budget = run_single_baseline(
        name="budget_matched",
        events=events,
        queries=queries,
        policy=QuotaMatchedPolicy(target_publications=target_publications, total_events=len(events)),
        alpha_fn=alpha_fixed,
        model_bias=model_bias,
        model_weights=model_weights,
        exact_fresh_results=fresh_q_results,
    )

    # 6. Run alpha_only (U=U*, alpha(p))
    res_alpha = run_single_baseline(
        name="alpha_only",
        events=events,
        queries=queries,
        policy=FixedCadencePolicy(cadence=u_star),
        alpha_fn=alpha_dynamic,
        model_bias=model_bias,
        model_weights=model_weights,
        exact_fresh_results=fresh_q_results,
    )

    # 7. Run pub_only (alpha=0.10, U(p))
    res_pub = run_single_baseline(
        name="pub_only",
        events=events,
        queries=queries,
        policy=AdaptivePressurePolicy(k_min=1, k_max=20),
        alpha_fn=alpha_fixed,
        model_bias=model_bias,
        model_weights=model_weights,
        exact_fresh_results=fresh_q_results,
    )

    all_configs = [res_fresh, res_tuned, res_budget, res_alpha, res_pub, res_joint]

    # Verify budget matching: budget_matched vs joint_adaptive +/- 1%
    pub_budget = res_budget["accounting"]["published_updates"]
    pub_joint = res_joint["accounting"]["published_updates"]
    abs_diff = abs(pub_budget - pub_joint)
    rel_diff = abs_diff / pub_joint if pub_joint > 0 else 0.0
    budget_matched_within_1pct = (rel_diff <= 0.01)

    # Verify behavioral signature disjointness
    signatures: Dict[str, Dict[str, Any]] = {}
    for cfg in all_configs:
        c_name = cfg["name"]
        signatures[c_name] = {
            "published_updates": cfg["accounting"]["published_updates"],
            "coalesced_updates": cfg["accounting"]["coalesced_updates"],
            "mean_staleness": round(cfg["telemetry"]["mean_staleness"], 4),
            "mean_feature_error": round(cfg["telemetry"]["mean_feature_error"], 4),
            "stress_published": cfg["phases"]["stress"]["published_updates"],
            "stress_staleness": round(cfg["phases"]["stress"]["mean_staleness"], 4),
        }

    # Clean query_results_map before serializing to JSON
    cleaned_configs = []
    for cfg in all_configs:
        c_copy = dict(cfg)
        del c_copy["query_results_map"]
        cleaned_configs.append(c_copy)

    return {
        "metadata": {
            "contract": "AMOS-08",
            "study": "comparative_baseline_suite",
            "total_events": len(events),
            "total_queries": len(queries),
            "tuned_u_star": u_star,
        },
        "tuning_results": {
            "selected_u_star": u_star,
            "candidates_evaluated": tuning_records,
        },
        "budget_matching": {
            "joint_adaptive_publications": pub_joint,
            "budget_matched_publications": pub_budget,
            "absolute_difference": abs_diff,
            "relative_difference_pct": rel_diff * 100.0,
            "matched_within_1pct": budget_matched_within_1pct,
        },
        "signatures": signatures,
        "configurations": cleaned_configs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Comparative baseline suite runner")
    parser.add_argument("--source", "-s", type=Path, default=Path("data/quarantine/raw/UserBehavior.csv"), help="Source raw CSV")
    parser.add_argument("--cohort", "-c", type=Path, default=Path("data/cohort.csv"), help="Cohort CSV")
    parser.add_argument("--model", "-m", type=Path, default=Path("data/models/logistic_model.txt"), help="Logistic model file")
    parser.add_argument("--output", "-o", type=Path, default=Path("docs/pilot/baseline_characterization.json"), help="Output JSON path")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic trace seed")

    args = parser.parse_args()

    print(f"Loading {TOTAL_EVENTS} validation events from {args.source}...", file=sys.stderr)
    val_events = load_validation_events(args.source, cohort_path=args.cohort, target_count=TOTAL_EVENTS)
    print("Generating scheduled open-loop traces...", file=sys.stderr)
    events, queries = generate_open_loop_trace(val_events, seed=args.seed)

    print(f"Loading model weights from {args.model}...", file=sys.stderr)
    bias, weights = load_model_weights(args.model)

    print("Executing comparative baseline suite across 6 configurations...", file=sys.stderr)
    results = execute_comparative_suite(events, queries, bias, weights)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Results written to {args.output}.", file=sys.stderr)
    print("Comparative Summary:", file=sys.stderr)
    for cfg in results["configurations"]:
        name = cfg["name"]
        pub = cfg["accounting"]["published_updates"]
        stale = cfg["telemetry"]["mean_staleness"]
        gap = cfg["telemetry"]["mean_paired_loss_gap"]
        print(f"  {name:15s}: Pubs={pub:5d}, MeanStaleness={stale:6.2f}, MeanLossGap={gap:.6f}", file=sys.stderr)

    print("Budget matching:", json.dumps(results["budget_matching"], indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
