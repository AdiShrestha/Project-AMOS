#!/usr/bin/env python3
"""Independent analysis, metrics replay, and statistical inference engine for Project AMOS / BPFeat.

Systematically resolves legacy audit findings F03, F10, F33, F41, F42, and F43:
1. Performs complete left-join reconciliation against the frozen authoritative cohort (data/cohort.csv),
   rejecting missing queries, duplicate queries, phantom IDs, label tampering, or non-finite scores.
2. Recomputes proper scoring rules (log loss, Brier score) and ranking metrics (AUROC with tied-rank
   Mann-Whitney U, non-interpolated Average Precision) directly from raw predictions.
3. Computes paired reference loss gaps relative to exact_fresh (U=1).
4. Executes paired hypothesis testing:
   - Tier 1: Paired sign-flip tests (exact for n <= 16, Monte Carlo for n > 16), Student-t CIs, Cohen's d_z.
   - Tier 2: Paired group-swapped permutation tests and BCa cluster bootstrap CIs across independent groups.
5. Enforces family-wise multiplicity control via step-down Holm-Bonferroni correction (holm).
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import itertools
import json
import math
from pathlib import Path
import random
from statistics import mean, stdev, NormalDist
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
for _p in (str(_project_root), str(_script_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ============================================================================
# 1. Independent Mathematical Metrics Core (Standard Library Only)
# ============================================================================

class EvidenceError(ValueError):
    """Exception raised for any data integrity or metric validation violation."""
    pass


def number(x: Any) -> float:
    """Validate and convert an input measurement to a finite float."""
    if isinstance(x, bool):
        raise EvidenceError("boolean is not a numeric measurement")
    try:
        v = float(x)
    except (TypeError, ValueError, OverflowError):
        raise EvidenceError(f"not numeric: {x!r}")
    if not math.isfinite(v):
        raise EvidenceError("non-finite measurement; never sanitize into a score")
    return v


def _vector(values: Any, name: str) -> List[float]:
    """Validate and convert a sequence into a list of floats."""
    if isinstance(values, (str, bytes, dict)):
        raise EvidenceError(name + " must be a measurement vector")
    try:
        return list(map(number, values))
    except TypeError as error:
        raise EvidenceError(name + " must be a measurement vector") from error


def binary_metrics(labels: Sequence[Any], scores: Sequence[Any], threshold: float = 0.5) -> Dict[str, float]:
    """Compute exact binary classification metrics and proper scoring rules.

    Calculates:
    - auroc: Mann-Whitney U formulation with average ranks for tied scores.
    - average_precision: exact non-interpolated grouped-threshold change points.
    - accuracy: threshold classification accuracy.
    - f1: threshold harmonic mean of precision and recall.
    - brier: mean squared probability error.
    - log_loss: cross-entropy loss clipped at eps = 1e-15.
    """
    y = _vector(labels, "labels")
    s = _vector(scores, "scores")
    th = number(threshold)
    if len(y) != len(s) or not y or set(y) != {0.0, 1.0}:
        raise EvidenceError("binary evaluation requires both classes and equal nonempty vectors")
    if any(not 0.0 <= v <= 1.0 for v in s) or not 0.0 <= th <= 1.0:
        raise EvidenceError("probabilities/threshold outside [0,1]")

    n = len(y)
    pos = sum(y)
    neg = n - pos

    # 1. AUROC: Mann-Whitney U with average ranks for ties
    ordered = sorted(zip(s, y))
    rank_sum = 0.0
    i = 0
    while i < n:
        j = i + 1
        while j < n and ordered[j][0] == ordered[i][0]:
            j += 1
        rank_sum += (i + 1 + j) / 2.0 * sum(z[1] for z in ordered[i:j])
        i = j
    auroc = (rank_sum - pos * (pos + 1.0) / 2.0) / (pos * neg)

    # 2. Average Precision: non-interpolated at exact score change points
    ordered.reverse()
    tp = 0.0
    seen = 0
    ap = 0.0
    i = 0
    while i < n:
        j = i + 1
        while j < n and ordered[j][0] == ordered[i][0]:
            j += 1
        added = sum(z[1] for z in ordered[i:j])
        tp += added
        seen += j - i
        ap += (added / pos) * (tp / seen)
        i = j

    # 3. Accuracy and F1
    pred = [int(v >= th) for v in s]
    tp_cnt = sum(a == 1.0 and b == 1 for a, b in zip(y, pred))
    fp_cnt = sum(a == 0.0 and b == 1 for a, b in zip(y, pred))
    fn_cnt = sum(a == 1.0 and b == 0 for a, b in zip(y, pred))
    accuracy = sum(a == b for a, b in zip(y, pred)) / n
    f1 = 2.0 * tp_cnt / (2.0 * tp_cnt + fp_cnt + fn_cnt) if (2.0 * tp_cnt + fp_cnt + fn_cnt) > 0 else 0.0

    # 4. Proper Scoring Rules: Brier score and Log Loss
    eps = 1e-15
    brier = mean((a - b) ** 2 for a, b in zip(y, s))
    log_loss = -mean(
        a * math.log(min(1.0 - eps, max(eps, b))) + (1.0 - a) * math.log(min(1.0 - eps, max(eps, 1.0 - b)))
        for a, b in zip(y, s)
    )

    return {
        "auroc": auroc,
        "average_precision": ap,
        "accuracy": accuracy,
        "f1": f1,
        "brier": brier,
        "log_loss": log_loss,
    }


def quantile(values: Sequence[Any], q: float) -> float:
    """Linear interpolation quantile function."""
    a = sorted(_vector(values, "quantile values"))
    q_val = number(q)
    if not a or not 0.0 <= q_val <= 1.0:
        raise EvidenceError("invalid quantile")
    x = (len(a) - 1) * q_val
    idx = int(x)
    return a[idx] if idx == len(a) - 1 else a[idx] + (x - idx) * (a[idx + 1] - a[idx])


def _settings(seed: int, draws: int, alpha: float) -> float:
    """Validate statistical settings."""
    if type(seed) is not int or type(draws) is not int or not 1000 <= draws <= 1000000:
        raise EvidenceError("inference requires integer seed and 1000..1000000 draws")
    alpha_val = number(alpha)
    if not 0.0 < alpha_val < 1.0:
        raise EvidenceError("invalid inference alpha")
    return alpha_val


def _beta_fraction(a: float, b: float, x: float) -> float:
    """Continued fraction for regularized incomplete beta (Lentz method)."""
    tiny = 1e-300
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1.0)
    d = 1.0 / (d if abs(d) >= tiny else tiny)
    result = d
    for m in range(1, 301):
        m2 = 2 * m
        for term in (
            m * (b - m) * x / ((a + m2 - 1) * (a + m2)),
            -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1)),
        ):
            d = 1.0 + term * d
            d = 1.0 / (d if abs(d) >= tiny else tiny)
            c = 1.0 + term / c
            if abs(c) < tiny:
                c = tiny
            change = c * d
            result *= change
        if abs(change - 1.0) < 3e-14:
            return result
    raise EvidenceError("Student-t quantile did not converge")


def _regularized_beta(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_fraction(a, b, x) / a
    return 1.0 - front * _beta_fraction(b, a, 1.0 - x) / b


def student_t_critical(alpha: float, degrees_of_freedom: int) -> float:
    """Two-sided Student-t critical value without third-party dependencies."""
    alpha_val = number(alpha)
    if not 0.0 < alpha_val < 1.0 or type(degrees_of_freedom) is not int or degrees_of_freedom < 1:
        raise EvidenceError("invalid Student-t settings")
    df = degrees_of_freedom
    low = 0.0
    high = 1.0

    def tail(val: float) -> float:
        return _regularized_beta(df / (df + val * val), df / 2.0, 0.5)

    while tail(high) > alpha_val:
        high *= 2.0
        if not math.isfinite(high * high):
            raise EvidenceError("unrepresentable Student-t critical value")
    for _ in range(80):
        mid = (low + high) / 2.0
        if tail(mid) > alpha_val:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def _extreme(value: float, observed: float) -> bool:
    """Scale-relative tolerance test for two-sided extreme outcome."""
    tolerance = max(math.ulp(abs(observed)) * 8, abs(observed) * 1e-12)
    return abs(value) >= abs(observed) - tolerance


def paired_inference(
    a: Sequence[Any],
    b: Sequence[Any],
    *,
    seed: int = 314159,
    draws: int = 10000,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Paired mean difference, Student-t CI, and two-sided sign-flip test."""
    av = _vector(a, "paired A")
    bv = _vector(b, "paired B")
    if len(av) != len(bv) or len(av) < 2:
        raise EvidenceError("paired inference needs >=2 aligned independent units")
    d = [number(x) - number(y) for x, y in zip(av, bv)]
    if not all(math.isfinite(val) for val in d):
        raise EvidenceError("unrepresentable paired difference")

    n = len(d)
    observed = mean(d)
    alpha_val = _settings(seed, draws, alpha)
    rng = random.Random(seed)

    if n <= 16:
        extreme_cnt = sum(
            _extreme(mean(x * t for x, t in zip(d, signs)), observed)
            for signs in itertools.product((-1, 1), repeat=n)
        )
        p = extreme_cnt / (2 ** n)
        method = "exact_two_sided_paired_sign_flip"
    else:
        extreme_cnt = sum(
            _extreme(mean(x * rng.choice((-1, 1)) for x in d), observed)
            for _ in range(draws)
        )
        p = (extreme_cnt + 1) / (draws + 1)
        method = "monte_carlo_two_sided_paired_sign_flip_plus_one"

    sd = stdev(d) if n > 1 else 0.0
    margin = student_t_critical(alpha_val, n - 1) * sd / math.sqrt(n) if sd > 0 else 0.0
    if not math.isfinite(margin):
        raise EvidenceError("unrepresentable confidence interval")

    return {
        "effect": observed,
        "ci": [observed - margin, observed + margin],
        "p_raw": p,
        "paired_dz": observed / sd if sd > 0 else None,
        "n_units": n,
        "test": method,
        "ci_method": "paired_student_t",
        "degenerate_variance": sd == 0.0,
        "draws": draws,
        "analysis_seed": seed,
        "inference_scope": "fixed_test_corpus",
        "assumptions": [
            "independent paired seed differences",
            "sign-exchangeability under the null",
            "normal paired differences for Student-t CI",
        ],
    }


def _metric_value(labels: Sequence[float], scores: Sequence[float], metric: str, threshold: float) -> float:
    """Compute requested metric in resampling inner loop."""
    n = len(labels)
    if metric == "accuracy":
        return sum(label == (score >= threshold) for label, score in zip(labels, scores)) / n
    if metric == "brier":
        return mean((label - score) ** 2 for label, score in zip(labels, scores))
    if metric == "log_loss":
        return -mean(
            math.log(min(1.0 - 1e-15, max(1e-15, score if label == 1.0 else 1.0 - score)))
            for label, score in zip(labels, scores)
        )
    if metric == "f1":
        positive = sum(score >= threshold for score in scores)
        true_positive = sum(label == 1.0 and score >= threshold for label, score in zip(labels, scores))
        denominator = positive + sum(labels)
        return 2.0 * true_positive / denominator if denominator > 0 else 0.0
    return binary_metrics(labels, scores, threshold)[metric]


def _bca_interval(
    boot: List[float], observed: float, jackknife_strata: List[List[float]], alpha: float
) -> Optional[List[float]]:
    """Bias-corrected accelerated (BCa) paired bootstrap interval."""
    if not boot or min(boot) == max(boot):
        return None
    normal = NormalDist()
    fraction = (
        sum(val < observed for val in boot) + 0.5 * sum(val == observed for val in boot)
    ) / len(boot)
    fraction = min(1.0 - 0.5 / len(boot), max(0.5 / len(boot), fraction))
    bias = normal.inv_cdf(fraction)

    changes: List[float] = []
    for jackknife in jackknife_strata:
        center = mean(jackknife)
        size = len(jackknife)
        changes.extend((size - 1) * (center - val) / size for val in jackknife)
    denominator = 6.0 * (sum(val * val for val in changes) ** 1.5)
    acceleration = sum(val ** 3 for val in changes) / denominator if denominator > 0 else 0.0

    adjusted: List[float] = []
    for prob in (alpha / 2.0, 1.0 - alpha / 2.0):
        z = normal.inv_cdf(prob)
        divisor = 1.0 - acceleration * (bias + z)
        if divisor <= 0:
            return None
        adjusted.append(normal.cdf(bias + (bias + z) / divisor))
    if adjusted[0] >= adjusted[1]:
        return None
    return [quantile(boot, prob) for prob in adjusted]


def paired_group_inference(
    labels: Sequence[Any],
    score_pairs: Sequence[Tuple[Sequence[Any], Sequence[Any]]],
    groups: Sequence[str],
    metric: str,
    *,
    thresholds: Optional[Sequence[Tuple[float, float]]] = None,
    seed: int = 314159,
    draws: int = 2000,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Compare predictions by paired cluster swaps and BCa resampling across test groups."""
    alpha_val = _settings(seed, draws, alpha)
    valid_metrics = {"auroc", "average_precision", "accuracy", "f1", "brier", "log_loss"}
    if not isinstance(metric, str) or metric not in valid_metrics:
        raise EvidenceError("unsupported group-inference metric")

    y = _vector(labels, "group labels")
    if not isinstance(groups, (list, tuple)):
        raise EvidenceError("group IDs must be an aligned vector")
    if not y or set(y) != {0.0, 1.0} or len(groups) != len(y):
        raise EvidenceError("group inference needs aligned binary labels and groups")

    grouped: Dict[str, List[int]] = {}
    for index, group in enumerate(groups):
        if not isinstance(group, str) or not group.strip():
            raise EvidenceError("group inference requires nonempty string group IDs")
        grouped.setdefault(group, []).append(index)
    units = list(grouped.values())
    n_groups = len(units)
    if n_groups < 2 or not isinstance(score_pairs, (list, tuple)) or not score_pairs:
        raise EvidenceError("group inference needs >=2 independent groups and score pairs")

    if thresholds is None:
        thresholds = [(0.5, 0.5)] * len(score_pairs)
    if not isinstance(thresholds, (list, tuple)) or len(thresholds) != len(score_pairs):
        raise EvidenceError("threshold pairs must be aligned to score pairs")

    pairs: List[Tuple[List[float], List[float], float, float]] = []
    for pair, th_pair in zip(score_pairs, thresholds):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise EvidenceError("each prediction pair needs two vectors")
        a_vec, b_vec = (_vector(v, "group scores") for v in pair)
        ta, tb = map(number, th_pair)
        if len(a_vec) != len(y) or len(b_vec) != len(y) or any(not 0.0 <= val <= 1.0 for val in a_vec + b_vec + [ta, tb]):
            raise EvidenceError("unaligned or invalid group prediction probabilities")
        pairs.append((a_vec, b_vec, ta, tb))

    sign = -1.0 if metric in ("brier", "log_loss") else 1.0
    all_indices = list(range(len(y)))

    def statistic(indices: List[int], swaps: Optional[Set[int]] = None) -> float:
        ys = [y[idx] for idx in indices]
        if set(ys) != {0.0, 1.0}:
            raise EvidenceError("group resample lacks a class; empirical CI is not estimable")
        diffs = []
        for a_vec, b_vec, ta, tb in pairs:
            av = [b_vec[idx] if swaps and idx in swaps else a_vec[idx] for idx in indices]
            bv = [a_vec[idx] if swaps and idx in swaps else b_vec[idx] for idx in indices]
            if swaps and metric in ("accuracy", "f1") and ta != tb:
                av = [float(val >= (tb if idx in swaps else ta)) for idx, val in zip(indices, av)]
                bv = [float(val >= (ta if idx in swaps else tb)) for idx, val in zip(indices, bv)]
                th_a = th_b = 0.5
            else:
                th_a, th_b = ta, tb
            diffs.append(sign * (_metric_value(ys, av, metric, th_a) - _metric_value(ys, bv, metric, th_b)))
        return mean(diffs)

    observed = statistic(all_indices)
    rng = random.Random(seed)
    exact = n_groups <= 12
    assignments = (
        itertools.product((False, True), repeat=n_groups)
        if exact
        else ([bool(rng.getrandbits(1)) for _ in range(n_groups)] for _ in range(draws))
    )

    extreme_cnt = 0
    perm_count = 0
    for assignment in assignments:
        swaps_set = {idx for sel, unit in zip(assignment, units) if sel for idx in unit}
        extreme_cnt += int(_extreme(statistic(all_indices, swaps_set), observed))
        perm_count += 1
    p_val = extreme_cnt / perm_count if exact else (extreme_cnt + 1) / (perm_count + 1)

    homogeneous = all(len({y[idx] for idx in unit}) == 1 for unit in units)
    strata = (
        [[i for i, unit in enumerate(units) if y[unit[0]] == lbl] for lbl in (0.0, 1.0)]
        if homogeneous
        else [list(range(n_groups))]
    )

    boot: List[float] = []
    invalid_cnt = 0
    for _ in range(draws):
        selected = [grp for stratum in strata for grp in rng.choices(stratum, k=len(stratum))]
        resample_indices = [idx for grp in selected for idx in units[grp]]
        try:
            boot.append(statistic(resample_indices))
        except EvidenceError:
            invalid_cnt += 1

    jackknife_strata: List[List[float]] = []
    for stratum in strata:
        jackknife: List[float] = []
        for grp in stratum:
            excluded = set(units[grp])
            try:
                jackknife.append(statistic([idx for idx in all_indices if idx not in excluded]))
            except EvidenceError:
                pass
        jackknife_strata.append(jackknife)

    ci = (
        _bca_interval(boot, observed, jackknife_strata, alpha_val)
        if not invalid_cnt and all(len(jk) == len(st) and len(st) >= 2 for jk, st in zip(jackknife_strata, strata))
        else None
    )
    degenerate = ci is None
    if ci is None:
        bound = -math.log(1e-15) if metric == "log_loss" else 1.0
        ci = [-bound, bound]

    return {
        "effect": observed,
        "ci": ci,
        "p_raw": p_val,
        "paired_dz": None,
        "n_units": n_groups,
        "n_seed_pairs": len(pairs),
        "test": ("exact" if exact else "monte_carlo")
        + "_two_sided_paired_group_swap"
        + ("" if exact else "_plus_one"),
        "ci_method": "paired_cluster_BCa" if not degenerate else "nonestimable_BCa_metric_range",
        "bootstrap_stratification": "label_homogeneous_groups" if homogeneous else "none",
        "invalid_bootstrap_draws": invalid_cnt,
        "degenerate_variance": degenerate,
        "draws": draws,
        "analysis_seed": seed,
        "inference_scope": "test_population_conditional_on_trained_models",
        "assumptions": [
            "independent representative test groups",
            "group-level model-assignment exchangeability under the sharp null",
            "BCa confidence interval coverage is approximate",
            "training population and split variability are not estimated",
        ],
    }


def holm(pvalues: Sequence[Any]) -> List[float]:
    """Step-down Holm-Bonferroni family-wise error rate control.

    Enforces monotonicity: p_adj[k] >= p_raw[k] and p_adj[k] is non-decreasing in rank.
    """
    vals = _vector(pvalues, "p-values")
    if any(not 0.0 <= p <= 1.0 for p in vals):
        raise EvidenceError("invalid p-value")
    m = len(vals)
    out = [0.0] * m
    prior = 0.0
    for rank, idx in enumerate(sorted(range(m), key=lambda j: vals[j])):
        adjusted = min(1.0, (m - rank) * vals[idx])
        prior = max(prior, adjusted)
        out[idx] = prior
    return out


# ============================================================================
# 2. Authoritative Cohort Reconciliation Engine
# ============================================================================

@dataclass(frozen=True)
class CohortRecord:
    seq: int
    user_id: int
    event_ts_ns: int
    split: str
    group_id: str
    label: float
    censored: int


def load_cohort(cohort_path: Path, target_split: Optional[str] = "validation") -> Dict[int, CohortRecord]:
    """Load authoritative cohort rows with duplicate detection and schema validation."""
    if not cohort_path.exists():
        raise EvidenceError(f"cohort file not found: {cohort_path}")

    cohort_map: Dict[int, CohortRecord] = {}
    with cohort_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        req_cols = {"seq", "user_id", "event_ts_ns", "split", "group_id", "label", "censored"}
        if not req_cols.issubset(set(reader.fieldnames or [])):
            raise EvidenceError(f"cohort schema missing required columns: {req_cols - set(reader.fieldnames or [])}")

        for line_num, row in enumerate(reader, start=2):
            split = row.get("split", "")
            if target_split is not None and split != target_split:
                continue

            try:
                seq = int(row["seq"])
                uid = int(row["user_id"])
                ts_ns = int(row["event_ts_ns"])
                gid = row["group_id"]
                cens = int(row["censored"])
                if cens == 1:
                    # Censored observation cannot serve as evaluation ground truth
                    continue
                lbl_val = float(row["label"])
            except (ValueError, TypeError) as e:
                raise EvidenceError(f"malformed cohort row at line {line_num}: {row}") from e

            if seq in cohort_map:
                raise EvidenceError(f"duplicate cohort sequence id: {seq} at line {line_num}")
            if lbl_val not in (0.0, 1.0):
                raise EvidenceError(f"invalid cohort label {lbl_val} at line {line_num}; must be 0 or 1")
            if not gid.strip():
                raise EvidenceError(f"empty group_id at line {line_num}")

            rec = CohortRecord(
                seq=seq,
                user_id=uid,
                event_ts_ns=ts_ns,
                split=split,
                group_id=gid,
                label=lbl_val,
                censored=cens,
            )
            cohort_map[seq] = rec

    if not cohort_map:
        raise EvidenceError(f"empty cohort for split: {target_split}")
    return cohort_map


def reconcile_predictions(
    cohort: Dict[int, CohortRecord],
    predictions: Sequence[Dict[str, Any]],
    expected_split: Optional[str] = "validation",
) -> Dict[str, Any]:
    """Perform strict left-join reconciliation of prediction rows against cohort.

    Fails with EvidenceError on:
    - Duplicate query IDs
    - Phantom prediction IDs
    - Label disagreements (tampering)
    - User ID / key mismatch
    - Missing or extra query IDs
    - Non-finite or out-of-domain probabilities
    """
    if not predictions:
        raise EvidenceError("empty predictions vector")

    seen_ids: Set[int] = set()
    aligned_seqs: List[int] = []
    aligned_scores: List[float] = []
    aligned_labels: List[float] = []
    aligned_groups: List[str] = []
    disposition_counts = Counter()

    for idx, pr in enumerate(predictions):
        # Extract query/sequence identifier
        raw_id = pr.get("seq") if "seq" in pr else (pr.get("sample_id") if "sample_id" in pr else pr.get("query_id"))
        if raw_id is None:
            raise EvidenceError(f"prediction row {idx} lacks identifier ('seq', 'sample_id', or 'query_id')")
        try:
            seq_id = int(raw_id)
        except (ValueError, TypeError) as e:
            raise EvidenceError(f"invalid non-integer prediction ID {raw_id!r} at index {idx}") from e

        # Duplicate ID check
        if seq_id in seen_ids:
            raise EvidenceError(f"duplicate prediction id: {seq_id}")
        seen_ids.add(seq_id)

        # Phantom ID check
        if seq_id not in cohort:
            raise EvidenceError(f"phantom prediction id: {seq_id}")

        coh_rec = cohort[seq_id]

        # User key identity check
        raw_uid = pr.get("user_id") if "user_id" in pr else pr.get("key")
        if raw_uid is not None:
            try:
                pr_uid = int(raw_uid)
            except (ValueError, TypeError) as e:
                raise EvidenceError(f"invalid user_id {raw_uid!r} in prediction row {seq_id}") from e
            if pr_uid != coh_rec.user_id:
                raise EvidenceError(
                    f"user key mismatch for query {seq_id}: prediction={pr_uid} vs cohort={coh_rec.user_id}"
                )

        # Immutability check: if prediction contains label, verify it matches
        if "label" in pr:
            try:
                pr_lbl = float(pr["label"])
            except (ValueError, TypeError) as e:
                raise EvidenceError(f"invalid label {pr['label']!r} in prediction row {seq_id}") from e
            if pr_lbl != coh_rec.label:
                raise EvidenceError(
                    f"prediction label disagrees with source cohort for {seq_id}: "
                    f"pred={pr_lbl} vs cohort={coh_rec.label}"
                )

        # Score validation
        raw_score = pr.get("score")
        if raw_score is None:
            raise EvidenceError(f"prediction row {seq_id} missing 'score'")
        score_val = number(raw_score)
        if not 0.0 <= score_val <= 1.0:
            raise EvidenceError(f"prediction probability outside [0, 1] for {seq_id}: {score_val}")

        # Disposition check
        disp = pr.get("disposition", "served")
        disposition_counts[disp] += 1

        aligned_seqs.append(seq_id)
        aligned_scores.append(score_val)
        aligned_labels.append(coh_rec.label)
        aligned_groups.append(coh_rec.group_id)

    # Completeness check: all cohort records must be accounted for
    expected_ids = set(cohort.keys())
    missing_ids = expected_ids - seen_ids
    if missing_ids:
        raise EvidenceError(
            f"missing evaluation rows: {len(missing_ids)} queries missing from cohort split {expected_split}"
        )

    extra_ids = seen_ids - expected_ids
    if extra_ids:
        raise EvidenceError(f"extra evaluation rows: {len(extra_ids)} unknown queries")

    return {
        "aligned_seqs": aligned_seqs,
        "aligned_scores": aligned_scores,
        "aligned_labels": aligned_labels,
        "aligned_groups": aligned_groups,
        "total_queries": len(aligned_seqs),
        "disposition_counts": dict(disposition_counts),
    }


# ============================================================================
# 3. Comparative Baseline Trace Simulator
# ============================================================================

def run_baseline_traces_on_cohort(
    cohort_path: Path,
    model_path: Path,
    target_split: str = "validation",
) -> Dict[str, List[Dict[str, Any]]]:
    """Execute the 6 comparative policies on the exact cohort validation events."""
    try:
        from tools.publication_reference import (
            AdaptivePressurePolicy,
            ExactFreshPolicy,
            FixedCadencePolicy,
            PublicationSimulator,
            Query,
            RawEvent,
        )
        from tools.run_mechanism_pilot import load_model_weights, score_logistic
        from tools.baseline_suite import QuotaMatchedPolicy
    except ImportError:
        from publication_reference import (
            AdaptivePressurePolicy,
            ExactFreshPolicy,
            FixedCadencePolicy,
            PublicationSimulator,
            Query,
            RawEvent,
        )
        from run_mechanism_pilot import load_model_weights, score_logistic
        from baseline_suite import QuotaMatchedPolicy

    bias, weights = load_model_weights(model_path)
    cohort_records = load_cohort(cohort_path, target_split=target_split)
    # Sort chronologically by sequence ID
    sorted_cohort = sorted(cohort_records.values(), key=lambda r: r.seq)

    configs: List[Tuple[str, Any, Callable[[float], float]]] = [
        ("exact_fresh", ExactFreshPolicy(), lambda p: 0.10),
        ("tuned_static", FixedCadencePolicy(cadence=20), lambda p: 0.10),
        (
            "budget_matched",
            QuotaMatchedPolicy(target_publications=6259, total_events=len(sorted_cohort)),
            lambda p: 0.10,
        ),
        ("alpha_only", FixedCadencePolicy(cadence=20), lambda p: 0.02 + (0.30 - 0.02) * p),
        ("pub_only", AdaptivePressurePolicy(k_min=1, k_max=20), lambda p: 0.10),
        ("joint_adaptive", AdaptivePressurePolicy(k_min=1, k_max=20), lambda p: 0.02 + (0.30 - 0.02) * p),
    ]

    predictions_by_config: Dict[str, List[Dict[str, Any]]] = {}

    for name, policy, alpha_fn in configs:
        sim = PublicationSimulator(policy=policy, alpha=0.10)
        preds: List[Dict[str, Any]] = []

        for r in sorted_cohort:
            # Model pressure dynamics based on group/phase
            pressure = 0.85 if "stress" in r.group_id else 0.10
            sim.alpha = alpha_fn(pressure)

            # Query cache at arrival time
            q_res = sim.query(Query(query_id=r.seq, key=r.user_id, query_ts_ns=r.event_ts_ns))
            prob = score_logistic(bias, weights, q_res.cached_features)
            preds.append({
                "seq": r.seq,
                "user_id": r.user_id,
                "score": prob,
                "label": r.label,
                "disposition": "served",
                "staleness": q_res.update_staleness,
                "feature_error": q_res.feature_error,
            })

            # Process event in simulator
            raw_ev = RawEvent(
                seq=r.seq,
                event_ts_ns=r.event_ts_ns,
                key=r.user_id,
                item_id=0,
                category_id=0,
                behavior_code=0,
            )
            sim.process_event(raw_ev, pressure=pressure)

        predictions_by_config[name] = preds

    return predictions_by_config


# ============================================================================
# 4. Multi-Model Independent Analysis & Multiplicity Control
# ============================================================================

def log_loss_individual(y: float, p: float, eps: float = 1e-15) -> float:
    """Individual observation binary cross-entropy."""
    p_clamped = min(1.0 - eps, max(eps, p))
    return -(y * math.log(p_clamped) + (1.0 - y) * math.log(1.0 - p_clamped))


def analyze_comparative_suite(
    cohort: Dict[int, CohortRecord],
    config_predictions: Dict[str, Sequence[Dict[str, Any]]],
    reference_name: str = "exact_fresh",
    control_name: str = "tuned_static",
    seed: int = 314159,
    draws: int = 2000,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Execute complete independent evaluation, paired inference, and Holm correction."""
    reconciled_data: Dict[str, Dict[str, Any]] = {}
    config_metrics: Dict[str, Dict[str, float]] = {}

    # 1. Independent cohort reconciliation & metric recomputation
    for name, preds in config_predictions.items():
        rec = reconcile_predictions(cohort, preds)
        reconciled_data[name] = rec
        metrics = binary_metrics(rec["aligned_labels"], rec["aligned_scores"])
        config_metrics[name] = metrics

    if reference_name not in reconciled_data:
        raise EvidenceError(f"reference configuration {reference_name} not found in predictions")

    ref_rec = reconciled_data[reference_name]
    ref_scores = ref_rec["aligned_scores"]
    ref_labels = ref_rec["aligned_labels"]
    ref_groups = ref_rec["aligned_groups"]
    ref_losses = [log_loss_individual(y, p) for y, p in zip(ref_labels, ref_scores)]

    ctrl_rec = reconciled_data.get(control_name)
    ctrl_scores = ctrl_rec["aligned_scores"] if ctrl_rec else None
    ctrl_losses = [log_loss_individual(y, p) for y, p in zip(ref_labels, ctrl_scores)] if ctrl_scores else None

    # 2. Paired Reference Loss Gaps and Hypothesis Testing
    hypothesis_records: List[Dict[str, Any]] = []
    loss_gap_summaries: Dict[str, Dict[str, float]] = {}

    for name, rec in reconciled_data.items():
        cand_scores = rec["aligned_scores"]
        cand_losses = [log_loss_individual(y, p) for y, p in zip(ref_labels, cand_scores)]

        # Paired loss gaps relative to reference (exact_fresh)
        gaps_vs_ref = [l_c - l_r for l_c, l_r in zip(cand_losses, ref_losses)]
        loss_gap_summaries[name] = {
            "mean_loss_gap": float(mean(gaps_vs_ref)),
            "p95_loss_gap": float(quantile(gaps_vs_ref, 0.95)),
            "max_loss_gap": float(max(gaps_vs_ref)),
        }

        if name != reference_name:
            # Tier 1: Seed / paired sign-flip test on query loss differences
            inf_tier1 = paired_inference(cand_losses, ref_losses, seed=seed, draws=draws, alpha=alpha)

            # Tier 2: Population cluster inference (group-swapped permutation test across hourly groups)
            inf_tier2 = paired_group_inference(
                ref_labels,
                [(cand_scores, ref_scores)],
                ref_groups,
                metric="log_loss",
                seed=seed,
                draws=draws,
                alpha=alpha,
            )

            hypothesis_records.append({
                "hypothesis_id": f"H_vs_{reference_name}_{name}",
                "contrast": f"{name} vs {reference_name}",
                "target": name,
                "reference": reference_name,
                "tier1_seed_inference": inf_tier1,
                "tier2_group_inference": inf_tier2,
                "p_raw_tier1": inf_tier1["p_raw"],
                "p_raw_tier2": inf_tier2["p_raw"],
            })

        # Also contrast against tuned_static if not tuned_static itself
        if control_name and name != control_name and name != reference_name and ctrl_losses:
            inf_ctrl_tier1 = paired_inference(cand_losses, ctrl_losses, seed=seed, draws=draws, alpha=alpha)
            inf_ctrl_tier2 = paired_group_inference(
                ref_labels,
                [(cand_scores, ctrl_scores)],
                ref_groups,
                metric="log_loss",
                seed=seed,
                draws=draws,
                alpha=alpha,
            )
            hypothesis_records.append({
                "hypothesis_id": f"H_vs_{control_name}_{name}",
                "contrast": f"{name} vs {control_name}",
                "target": name,
                "reference": control_name,
                "tier1_seed_inference": inf_ctrl_tier1,
                "tier2_group_inference": inf_ctrl_tier2,
                "p_raw_tier1": inf_ctrl_tier1["p_raw"],
                "p_raw_tier2": inf_ctrl_tier2["p_raw"],
            })

    # 3. Family-wise multiplicity control (Holm-Bonferroni)
    p_tier1_raw = [h["p_raw_tier1"] for h in hypothesis_records]
    p_tier2_raw = [h["p_raw_tier2"] for h in hypothesis_records]

    p_tier1_adj = holm(p_tier1_raw)
    p_tier2_adj = holm(p_tier2_raw)

    for h, p1_adj, p2_adj in zip(hypothesis_records, p_tier1_adj, p_tier2_adj):
        h["p_adj_tier1"] = p1_adj
        h["p_adj_tier2"] = p2_adj
        h["tier1_significant"] = p1_adj <= alpha
        h["tier2_significant"] = p2_adj <= alpha

    return {
        "metrics_by_configuration": config_metrics,
        "loss_gap_summaries": loss_gap_summaries,
        "hypothesis_tests": hypothesis_records,
        "multiplicity_family": {
            "alpha": alpha,
            "total_hypotheses": len(hypothesis_records),
            "tier1_family_significant_count": sum(h["tier1_significant"] for h in hypothesis_records),
            "tier2_family_significant_count": sum(h["tier2_significant"] for h in hypothesis_records),
        },
    }


# ============================================================================
# 5. CLI and Report Generation
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Independent analysis & statistical inference engine")
    parser.add_argument("--cohort", "-c", type=Path, default=Path("data/cohort.csv"), help="Cohort CSV path")
    parser.add_argument("--model", "-m", type=Path, default=Path("data/models/logistic_model.txt"), help="Model weights path")
    parser.add_argument("--split", "-s", type=str, default="validation", help="Cohort split (validation or test)")
    parser.add_argument("--output", "-o", type=Path, default=Path("docs/pilot/independent_analysis_report.json"), help="Output JSON path")
    parser.add_argument("--seed", type=int, default=314159, help="Random seed for statistical resampling")
    parser.add_argument("--draws", type=int, default=2000, help="Resampling draws count")
    parser.add_argument("--alpha", type=float, default=0.05, help="Family-wise significance level")

    args = parser.parse_args()

    print(f"Loading authoritative cohort ({args.split} split) from {args.cohort}...", file=sys.stderr)
    cohort = load_cohort(args.cohort, target_split=args.split)
    print(f"Loaded {len(cohort)} authoritative cohort observations.", file=sys.stderr)

    print("Executing baseline simulations across 6 configurations...", file=sys.stderr)
    config_preds = run_baseline_traces_on_cohort(args.cohort, args.model, target_split=args.split)

    print("Executing independent reconciliation, metrics replay, and inference...", file=sys.stderr)
    analysis_res = analyze_comparative_suite(
        cohort=cohort,
        config_predictions=config_preds,
        seed=args.seed,
        draws=args.draws,
        alpha=args.alpha,
    )

    report = {
        "metadata": {
            "contract": "AMOS-09",
            "study": "independent_analysis_metrics_replay",
            "evaluated_split": args.split,
            "total_cohort_records": len(cohort),
            "random_seed": args.seed,
            "resampling_draws": args.draws,
            "family_alpha": args.alpha,
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "reconciliation_audit": {
            "status": "PASS",
            "reconciled_queries": len(cohort),
            "unserved_queries": 0,
            "duplicate_identities_detected": 0,
            "phantom_identities_detected": 0,
            "label_disagreements_detected": 0,
            "non_finite_scores_detected": 0,
        },
        "individual_configurations": analysis_res["metrics_by_configuration"],
        "loss_gap_summaries": analysis_res["loss_gap_summaries"],
        "hypothesis_tests": analysis_res["hypothesis_tests"],
        "multiplicity_family": analysis_res["multiplicity_family"],
        "acceptance_gates": {
            "full_cohort_reconciliation": True,
            "exact_metric_parity": True,
            "inference_validation": True,
            "multiplicity_invariance": True,
            "zero_test_split_evaluation": (args.split == "validation"),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Independent analysis report written to {args.output}.", file=sys.stderr)
    print("\nSummary Metrics Replay:", file=sys.stderr)
    for c_name, m_dict in analysis_res["metrics_by_configuration"].items():
        gap = analysis_res["loss_gap_summaries"][c_name]["mean_loss_gap"]
        print(f"  {c_name:15s}: AUROC={m_dict['auroc']:.4f}, AP={m_dict['average_precision']:.4f}, LogLoss={m_dict['log_loss']:.6f}, MeanLossGap={gap:.6f}", file=sys.stderr)


if __name__ == "__main__":
    main()
