"""Explicit BPFeat dataset adapters (``bpfeat.adapter.v1``).

The adapter is deliberately independent of filenames and values such as
``Amount``. A caller selects a schema ID, and every row is validated against
that schema before it becomes a canonical event.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import math
from typing import Iterator, Optional

TAOBAO_SCHEMA_ID = "bpfeat.taobao.1"
ULB_SCHEMA_ID = "bpfeat.ulb.1"
_U64_MAX = (1 << 64) - 1

TAOBAO_BEHAVIOR_MAP = {"pv": 0, "cart": 1, "fav": 2, "buy": 3}


@dataclass(frozen=True)
class CanonicalEvent:
    seq: int
    event_ts_ns: int
    entity_id: Optional[int]
    item_id: Optional[int]
    category_id: Optional[int]
    behavior_code: Optional[int]
    amount: Optional[float]
    label: Optional[int]
    label_valid: int
    censored: int
    is_burst_period: int


@dataclass
class AdapterStats:
    """Row disposition counters for one complete adapter invocation."""

    offered: int = 0
    accepted: int = 0
    rejected: int = 0
    censored: int = 0
    duplicates: int = 0


def _int_cell(value: str, field: str, row: int) -> int:
    try:
        return int(value.strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer {field!r} at row {row}") from exc


def _binary_cell(value: str, field: str, row: int) -> int:
    parsed = _int_cell(value, field, row)
    if parsed not in (0, 1):
        raise ValueError(f"{field!r} must be 0 or 1 at row {row}")
    return parsed


def _epoch_seconds_to_ns(value: str, row: int) -> int:
    try:
        seconds = Decimal(value.strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid epoch timestamp at row {row}") from exc
    if not seconds.is_finite() or seconds < 0 or seconds != seconds.to_integral_value():
        raise ValueError(f"Taobao timestamp must be a non-negative integer at row {row}")
    result = int(seconds) * 1_000_000_000
    if result > _U64_MAX:
        raise ValueError(f"timestamp overflow at row {row}")
    return result


def _elapsed_seconds_to_ns(value: str, origin_ns: int, row: int) -> int:
    try:
        seconds = Decimal(value.strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid elapsed timestamp at row {row}") from exc
    if not seconds.is_finite() or seconds < 0:
        raise ValueError(f"ULB Time must be finite and non-negative at row {row}")
    scaled = (seconds * Decimal(1_000_000_000)).to_integral_value(rounding=ROUND_HALF_EVEN)
    result = origin_ns + int(scaled)
    if result < 0 or result > _U64_MAX:
        raise ValueError(f"timestamp overflow at row {row}")
    return result


class DatasetAdapter:
    """Convert one explicitly selected source schema to canonical events.

    ``validated_row_index`` is an explicit sequence policy for source files
    without a sequence column; it is not inferred from a filename. A future
    adapter can require ``source_column`` and a new schema version.
    """

    def __init__(
        self,
        schema_id: str,
        *,
        sequence_source: str = "validated_row_index",
        prediction_horizon_ns: Optional[int] = None,
        observation_end_ns: Optional[int] = None,
    ) -> None:
        if schema_id not in (TAOBAO_SCHEMA_ID, ULB_SCHEMA_ID):
            raise ValueError(f"Unknown or unallowed schema_id: {schema_id!r}; mode inference is prohibited")
        if sequence_source not in ("validated_row_index", "source_column"):
            raise ValueError("sequence_source must be validated_row_index or source_column")
        if prediction_horizon_ns is not None and prediction_horizon_ns < 0:
            raise ValueError("prediction_horizon_ns must be non-negative")
        if observation_end_ns is not None and not 0 <= observation_end_ns <= _U64_MAX:
            raise ValueError("observation_end_ns is outside uint64 nanoseconds")
        if prediction_horizon_ns is not None and observation_end_ns is None:
            raise ValueError("observation_end_ns is required when a horizon is declared")
        self.schema_id = schema_id
        self.sequence_source = sequence_source
        self.prediction_horizon_ns = prediction_horizon_ns
        self.observation_end_ns = observation_end_ns
        self._stats = AdapterStats()

    @property
    def stats(self) -> AdapterStats:
        """Counters for the most recent invocation (updated as rows are read)."""
        return self._stats

    @staticmethod
    def _header(reader: csv.reader, path: str) -> list[str]:
        header = next(reader, None)
        if header is None:
            raise ValueError(f"Empty CSV at {path}")
        normalized = [column.strip().lower() for column in header]
        if not all(normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("header contains an empty or duplicate column")
        return normalized

    def _sequence(self, row: list[str], columns: dict[str, int], next_seq: int, row_no: int) -> int:
        if self.sequence_source == "source_column":
            if "seq" not in columns:
                raise ValueError("source_column sequence policy requires a seq column")
            seq = _int_cell(row[columns["seq"]], "seq", row_no)
        else:
            seq = next_seq
        if seq < 0 or seq > _U64_MAX:
            raise ValueError(f"seq outside uint64 domain at row {row_no}")
        return seq

    def _validity(
        self,
        event_ts_ns: int,
        label: Optional[int],
        label_valid: int,
        censored: int,
    ) -> tuple[Optional[int], int, int]:
        if self.prediction_horizon_ns is not None:
            assert self.observation_end_ns is not None
            horizon_end = event_ts_ns + self.prediction_horizon_ns
            if horizon_end > self.observation_end_ns:
                return label, 0, 1
        if censored:
            return label, 0, 1
        return label, label_valid, censored

    def adapt_csv(self, file_path: str, run_origin_ns: int = 0) -> Iterator[CanonicalEvent]:
        self._stats = AdapterStats()
        try:
            yield from self._adapt_csv_impl(file_path, run_origin_ns)
        except ValueError as exc:
            self._stats.rejected += 1
            if "duplicate or non-increasing seq" in str(exc):
                self._stats.duplicates += 1
            raise

    def _adapt_csv_impl(self, file_path: str, run_origin_ns: int = 0) -> Iterator[CanonicalEvent]:
        if not 0 <= run_origin_ns <= _U64_MAX:
            raise ValueError("run_origin_ns is outside uint64 nanoseconds")
        with open(file_path, "r", encoding="utf-8", errors="strict", newline="") as stream:
            reader = csv.reader(stream)
            header = self._header(reader, file_path)
            columns = {name: index for index, name in enumerate(header)}
            if self.schema_id == TAOBAO_SCHEMA_ID:
                required = ("user_id", "item_id", "category_id", "behavior", "timestamp")
            else:
                required = ("time", "amount", "class")
            missing = [name for name in required if name not in columns]
            if missing:
                raise ValueError(f"missing required {self.schema_id} columns: {missing}")

            last_seq: Optional[int] = None
            last_ts_by_entity: dict[int, int] = {}
            last_global_ts: Optional[int] = None
            next_seq = 0
            for row_no, row in enumerate(reader, start=2):
                if not row or not any(cell.strip() for cell in row):
                    continue
                self._stats.offered += 1
                if len(row) != len(header):
                    raise ValueError(f"row {row_no} has {len(row)} columns; expected {len(header)}")
                seq = self._sequence(row, columns, next_seq, row_no)
                if last_seq is not None and seq <= last_seq:
                    raise ValueError(f"duplicate or non-increasing seq at row {row_no}")
                last_seq = seq
                next_seq += 1

                if self.schema_id == TAOBAO_SCHEMA_ID:
                    uid = _int_cell(row[columns["user_id"]], "user_id", row_no)
                    item_id = _int_cell(row[columns["item_id"]], "item_id", row_no)
                    category_id = _int_cell(row[columns["category_id"]], "category_id", row_no)
                    if min(uid, item_id, category_id) < 0:
                        raise ValueError(f"negative Taobao identity at row {row_no}")
                    behavior_text = row[columns["behavior"]].strip()
                    if behavior_text not in TAOBAO_BEHAVIOR_MAP:
                        raise ValueError(f"unknown Taobao behavior {behavior_text!r} at row {row_no}")
                    event_ts_ns = _epoch_seconds_to_ns(row[columns["timestamp"]], row_no)
                    label: Optional[int] = None
                    label_valid = 0
                    censored = 0
                    if "label" in columns and row[columns["label"]].strip():
                        label = _binary_cell(row[columns["label"]], "label", row_no)
                    if "label_valid" in columns and row[columns["label_valid"]].strip():
                        label_valid = _binary_cell(row[columns["label_valid"]], "label_valid", row_no)
                    if "censored" in columns and row[columns["censored"]].strip():
                        censored = _binary_cell(row[columns["censored"]], "censored", row_no)
                    previous = last_ts_by_entity.get(uid)
                    if previous is not None and event_ts_ns < previous:
                        raise ValueError(f"non-monotonic timestamp for user {uid} at row {row_no}")
                    last_ts_by_entity[uid] = event_ts_ns
                    label, label_valid, censored = self._validity(event_ts_ns, label, label_valid, censored)
                    event = CanonicalEvent(seq, event_ts_ns, uid, item_id, category_id,
                                           TAOBAO_BEHAVIOR_MAP[behavior_text], 0.0,
                                           label, label_valid, censored, 0)
                else:
                    event_ts_ns = _elapsed_seconds_to_ns(row[columns["time"]], run_origin_ns, row_no)
                    try:
                        amount = float(row[columns["amount"]].strip())
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"invalid ULB Amount at row {row_no}") from exc
                    if not math.isfinite(amount) or amount < 0.0:
                        raise ValueError(f"ULB Amount must be finite and non-negative at row {row_no}")
                    label = _binary_cell(row[columns["class"]], "class", row_no)
                    if last_global_ts is not None and event_ts_ns < last_global_ts:
                        raise ValueError(f"non-monotonic global ULB timestamp at row {row_no}")
                    last_global_ts = event_ts_ns
                    label, label_valid, censored = self._validity(event_ts_ns, label, 1, 0)
                    event = CanonicalEvent(seq, event_ts_ns, None, None, None, 0, amount,
                                           label, label_valid, censored, 0)
                self._stats.accepted += 1
                self._stats.censored += event.censored
                yield event
