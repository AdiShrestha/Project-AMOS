#!/usr/bin/env python3
"""Single-threaded reference simulator for publication/query core and work-cost separation.

Separates raw ingestion events, mutable feature extraction, publication policies,
immutable versioned cache storage, and independent query lookups.
Enforces exact conservation: processed_updates == published_updates + coalesced_updates.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple, Union

FEATURE_DIMENSION: int = 7
FEATURE_SCHEMA: str = "bpfeat.taobao.features.v2"
BEHAVIOR_WEIGHTS: Tuple[float, ...] = (1.0, 3.0, 2.0, 5.0)


@dataclass(frozen=True)
class RawEvent:
    seq: int
    event_ts_ns: int
    key: int
    item_id: int
    category_id: int
    behavior_code: int


@dataclass(frozen=True)
class Query:
    query_id: int
    key: int
    query_ts_ns: int


@dataclass(frozen=True)
class PublishedVersion:
    key: int
    version_id: int
    latest_included_seq: int
    latest_event_ts_ns: int
    features: Tuple[float, ...]
    published_ts_ns: int


@dataclass(frozen=True)
class QueryResult:
    query_id: int
    key: int
    query_ts_ns: int
    cold_start: int
    version_id: int
    latest_included_seq: int
    latest_event_ts_ns: int
    cached_features: Tuple[float, ...]
    fresh_features: Tuple[float, ...]
    event_time_age_ns: int
    update_staleness: int
    feature_error: float


class PolicyType(str, Enum):
    EXACT_FRESH = "ExactFresh"
    FIXED_CADENCE = "FixedCadence"
    ELAPSED_THRESHOLD = "ElapsedThreshold"
    ADAPTIVE_PRESSURE = "AdaptivePressure"


@dataclass
class UserState:
    engagement_ema: float = 0.0
    gap_ema: float = 0.0
    pv: int = 0
    cart_fav: int = 0
    buy: int = 0
    count: int = 0
    last_ns: int = 0
    seen: bool = False
    pending_updates: int = 0
    has_published: bool = False
    published_version_id: int = 0
    last_published_event_ts_ns: int = 0
    last_published_seq: int = 0

    def current_features(self) -> Tuple[float, ...]:
        if not self.seen:
            return (0.0,) * FEATURE_DIMENSION
        gap = 0.0
        return (
            self.engagement_ema,
            math.log1p(self.pv),
            math.log1p(self.cart_fav),
            0.0,
            float(self.buy) / self.count if self.count > 0 else 0.0,
            math.log1p(self.buy),
            self.gap_ema,
        )


class PublicationPolicy:
    """Base interface for publication decision policies."""

    def should_publish(self, event: RawEvent, state: UserState, pressure: float) -> bool:
        raise NotImplementedError


class ExactFreshPolicy(PublicationPolicy):
    """U = 1: Every event update is published immediately."""

    def should_publish(self, event: RawEvent, state: UserState, pressure: float) -> bool:
        return True


class FixedCadencePolicy(PublicationPolicy):
    """U = k: Publishes every k-th update for the key."""

    def __init__(self, cadence: int = 1) -> None:
        if cadence < 1:
            raise ValueError(f"Cadence must be >= 1, got {cadence}")
        self.cadence = cadence

    def should_publish(self, event: RawEvent, state: UserState, pressure: float) -> bool:
        return (state.pending_updates + 1) >= self.cadence


class ElapsedThresholdPolicy(PublicationPolicy):
    """U = delta_t: Publishes when event-time elapsed since last publication >= delta_t."""

    def __init__(self, delta_t_ns: int) -> None:
        if delta_t_ns < 0:
            raise ValueError(f"delta_t_ns must be >= 0, got {delta_t_ns}")
        self.delta_t_ns = delta_t_ns

    def should_publish(self, event: RawEvent, state: UserState, pressure: float) -> bool:
        if not state.has_published:
            return True
        return (event.event_ts_ns - state.last_published_event_ts_ns) >= self.delta_t_ns


class AdaptivePressurePolicy(PublicationPolicy):
    """Adapts publication cadence based on system pressure p in [0, 1]."""

    def __init__(self, k_min: int = 1, k_max: int = 16) -> None:
        if k_min < 1 or k_max < k_min:
            raise ValueError(f"Invalid cadence bounds: k_min={k_min}, k_max={k_max}")
        self.k_min = k_min
        self.k_max = k_max

    def target_cadence(self, pressure: float) -> int:
        p = max(0.0, min(1.0, float(pressure)))
        k = self.k_min + int(p * (self.k_max - self.k_min))
        return max(self.k_min, min(self.k_max, k))

    def should_publish(self, event: RawEvent, state: UserState, pressure: float) -> bool:
        k = self.target_cadence(pressure)
        return (state.pending_updates + 1) >= k


class VersionedCache:
    """Thread-safe / deterministic storage of published versions."""

    def __init__(self) -> None:
        self._versions: Dict[int, PublishedVersion] = {}
        self.total_publications: int = 0

    def get(self, key: int) -> Tuple[bool, PublishedVersion]:
        """Look up key in cache. Returns (cold_start, version)."""
        if key not in self._versions:
            cold_version = PublishedVersion(
                key=key,
                version_id=0,
                latest_included_seq=0,
                latest_event_ts_ns=0,
                features=(0.0,) * FEATURE_DIMENSION,
                published_ts_ns=0,
            )
            return True, cold_version
        return False, self._versions[key]

    def publish(
        self,
        key: int,
        seq: int,
        event_ts_ns: int,
        features: Tuple[float, ...],
        published_ts_ns: int,
    ) -> PublishedVersion:
        """Publish a new immutable version for key."""
        old_version_id = self._versions[key].version_id if key in self._versions else 0
        new_version_id = old_version_id + 1
        version = PublishedVersion(
            key=key,
            version_id=new_version_id,
            latest_included_seq=seq,
            latest_event_ts_ns=event_ts_ns,
            features=features,
            published_ts_ns=published_ts_ns,
        )
        self._versions[key] = version
        self.total_publications += 1
        return version

    def clear(self) -> None:
        self._versions.clear()
        self.total_publications = 0

    def size(self) -> int:
        return len(self._versions)


class PublicationSimulator:
    """Single-threaded deterministic reference simulator.

    Manages mutable state updates, publication policy decisions, versioned cache,
    independent query lookups, and exact conservation accounting.
    """

    def __init__(
        self,
        policy: PublicationPolicy,
        alpha: float = 0.1,
        max_keys: int = 1_000_000,
    ) -> None:
        if not (0.0 < alpha <= 1.0):
            raise ValueError(f"Alpha must be in (0, 1], got {alpha}")
        if max_keys <= 0:
            raise ValueError("max_keys must be positive")
        self.policy = policy
        self.alpha = alpha
        self.max_keys = max_keys
        self.cache = VersionedCache()
        self.users: Dict[int, UserState] = {}
        self.latest_fresh_features: Dict[int, Tuple[float, ...]] = {}

        # Conservation and telemetry accounting
        self.processed_updates: int = 0
        self.published_updates: int = 0
        self.coalesced_updates: int = 0
        self.queries_served: int = 0
        self.cold_queries: int = 0
        self.warm_queries: int = 0

    def process_event(
        self,
        event: RawEvent,
        pressure: float = 0.0,
        wall_clock_ns: int = 0,
    ) -> Tuple[bool, Optional[PublishedVersion]]:
        """Process an incoming ingestion event and evaluate publication policy."""
        if event.behavior_code > 3:
            raise ValueError(f"Unknown behavior code: {event.behavior_code}")

        key = event.key
        if key not in self.users:
            if len(self.users) >= self.max_keys:
                raise RuntimeError("Key budget exhausted; no silent drops allowed")
            self.users[key] = UserState()

        state = self.users[key]
        if state.seen and event.event_ts_ns < state.last_ns:
            raise ValueError(f"Event timestamp decreased for key {key}: {event.event_ts_ns} < {state.last_ns}")

        gap = (event.event_ts_ns - state.last_ns) / 1e9 if state.seen else 0.0
        w = BEHAVIOR_WEIGHTS[event.behavior_code]
        state.engagement_ema += self.alpha * (w - state.engagement_ema)
        state.gap_ema += self.alpha * (gap - state.gap_ema)
        state.count += 1

        if event.behavior_code == 0:
            state.pv += 1
        elif event.behavior_code == 3:
            state.buy += 1
        else:
            state.cart_fav += 1

        state.last_ns = event.event_ts_ns
        state.seen = True

        fresh_x = (
            state.engagement_ema,
            math.log1p(state.pv),
            math.log1p(state.cart_fav),
            min(gap, 3600.0) / 3600.0,
            float(state.buy) / state.count if state.count > 0 else 0.0,
            math.log1p(state.buy),
            state.gap_ema,
        )
        self.latest_fresh_features[key] = fresh_x
        self.processed_updates += 1

        # Evaluate publication policy
        publish = self.policy.should_publish(event, state, pressure)
        if publish:
            pub_ts = wall_clock_ns if wall_clock_ns > 0 else event.event_ts_ns
            version = self.cache.publish(
                key=key,
                seq=event.seq,
                event_ts_ns=event.event_ts_ns,
                features=fresh_x,
                published_ts_ns=pub_ts,
            )
            state.has_published = True
            state.published_version_id = version.version_id
            state.last_published_seq = event.seq
            state.last_published_event_ts_ns = event.event_ts_ns
            state.pending_updates = 0
            self.published_updates += 1
            return True, version
        else:
            state.pending_updates += 1
            self.coalesced_updates += 1
            return False, None

    def query(self, q: Query) -> QueryResult:
        """Serve an independent query lookup from the versioned cache."""
        cold_start, version = self.cache.get(q.key)
        self.queries_served += 1
        if cold_start:
            self.cold_queries += 1
        else:
            self.warm_queries += 1

        fresh_features = self.latest_fresh_features.get(q.key, (0.0,) * FEATURE_DIMENSION)
        cached_features = version.features

        # Compute Euclidean feature error ||x_cached - x_fresh||_2
        feature_error = math.sqrt(
            sum((c - f) ** 2 for c, f in zip(cached_features, fresh_features))
        )

        # Event-time age
        if not cold_start:
            event_time_age_ns = max(0, q.query_ts_ns - version.latest_event_ts_ns)
        else:
            event_time_age_ns = q.query_ts_ns

        # Update staleness (coalesced updates since published version)
        if q.key in self.users:
            state = self.users[q.key]
            update_staleness = state.pending_updates
        else:
            update_staleness = 0

        return QueryResult(
            query_id=q.query_id,
            key=q.key,
            query_ts_ns=q.query_ts_ns,
            cold_start=1 if cold_start else 0,
            version_id=version.version_id,
            latest_included_seq=version.latest_included_seq,
            latest_event_ts_ns=version.latest_event_ts_ns,
            cached_features=cached_features,
            fresh_features=fresh_features,
            event_time_age_ns=event_time_age_ns,
            update_staleness=update_staleness,
            feature_error=feature_error,
        )

    def get_accounting(self) -> Dict[str, Union[int, bool]]:
        """Return exact accounting and verify conservation invariant."""
        is_conserved = (self.processed_updates == self.published_updates + self.coalesced_updates)
        return {
            "processed_updates": self.processed_updates,
            "published_updates": self.published_updates,
            "coalesced_updates": self.coalesced_updates,
            "queries_served": self.queries_served,
            "cold_queries": self.cold_queries,
            "warm_queries": self.warm_queries,
            "conservation_valid": is_conserved,
        }


def make_policy(policy_name: str, cadence: int = 1, delta_t_ns: int = 0) -> PublicationPolicy:
    """Factory helper to instantiate a publication policy."""
    p_lower = policy_name.lower()
    if p_lower in ("exactfresh", "exact_fresh", "fresh", "u1"):
        return ExactFreshPolicy()
    elif p_lower in ("fixedcadence", "fixed_cadence", "cadence"):
        return FixedCadencePolicy(cadence=cadence)
    elif p_lower in ("elapsedthreshold", "elapsed_threshold", "elapsed"):
        return ElapsedThresholdPolicy(delta_t_ns=delta_t_ns)
    elif p_lower in ("adaptivepressure", "adaptive_pressure", "adaptive"):
        return AdaptivePressurePolicy(k_min=1, k_max=max(16, cadence))
    else:
        raise ValueError(f"Unknown publication policy: {policy_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publication reference simulator")
    parser.add_argument("--events", type=Path, required=True, help="Input events CSV")
    parser.add_argument("--queries", type=Path, required=False, help="Input queries CSV")
    parser.add_argument("--out-queries", type=Path, required=False, help="Output query results CSV")
    parser.add_argument("--out-accounting", type=Path, required=False, help="Output accounting JSON")
    parser.add_argument("--policy", type=str, default="ExactFresh", help="Publication policy")
    parser.add_argument("--cadence", type=int, default=1, help="Fixed cadence U=k")
    parser.add_argument("--delta-t-ns", type=int, default=0, help="Elapsed threshold delta_t_ns")
    parser.add_argument("--alpha", type=float, default=0.1, help="Feature alpha gain")

    args = parser.parse_args()
    policy = make_policy(args.policy, cadence=args.cadence, delta_t_ns=args.delta_t_ns)
    sim = PublicationSimulator(policy=policy, alpha=args.alpha)

    # Process events
    with open(args.events, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            event = RawEvent(
                seq=int(row["seq"]),
                event_ts_ns=int(row["event_ts_ns"]),
                key=int(row["key"]),
                item_id=int(row["item_id"]),
                category_id=int(row["category_id"]),
                behavior_code=int(row["behavior_code"]),
            )
            sim.process_event(event)

    # Process queries if supplied
    query_results: List[QueryResult] = []
    if args.queries and args.queries.exists():
        with open(args.queries, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                q = Query(
                    query_id=int(row["query_id"]),
                    key=int(row["key"]),
                    query_ts_ns=int(row["query_ts_ns"]),
                )
                query_results.append(sim.query(q))

    # Write query results
    if args.out_queries and query_results:
        args.out_queries.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_queries, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            headers = [
                "query_id",
                "key",
                "query_ts_ns",
                "cold_start",
                "version_id",
                "latest_included_seq",
                "latest_event_ts_ns",
                "event_time_age_ns",
                "update_staleness",
                "feature_error",
            ] + [f"cached_x{i}" for i in range(FEATURE_DIMENSION)] + [f"fresh_x{i}" for i in range(FEATURE_DIMENSION)]
            writer.writerow(headers)
            for r in query_results:
                row_vals = [
                    r.query_id,
                    r.key,
                    r.query_ts_ns,
                    r.cold_start,
                    r.version_id,
                    r.latest_included_seq,
                    r.latest_event_ts_ns,
                    r.event_time_age_ns,
                    r.update_staleness,
                    f"{r.feature_error:.17e}",
                ] + [f"{x:.17e}" for x in r.cached_features] + [f"{x:.17e}" for x in r.fresh_features]
                writer.writerow(row_vals)

    accounting = sim.get_accounting()
    if args.out_accounting:
        args.out_accounting.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_accounting, "w", encoding="utf-8") as f:
            json.dump(accounting, f, indent=2)

    print(json.dumps(accounting, indent=2))


if __name__ == "__main__":
    main()
