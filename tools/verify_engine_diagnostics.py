"""Independent replay of engine diagnostics, never research certification.

Uses explicit event/model inputs, complete emitted rows and declared config.
Loads the small diagnostic cohort in memory. It does not authenticate inputs,
measure resource use, prove pressure sensor truth, or supervise a live service.
"""
import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path


class ReplayError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReplayError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def number(value):
    require(not isinstance(value, bool), "boolean numeric value")
    if isinstance(value, str):
        require(re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value) is not None,
                "nondecimal/padded numeric value")
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError) as ex:
        raise ReplayError("invalid numeric value") from ex
    require(math.isfinite(value), "nonfinite numeric value")
    return value


def integer(value):
    require(isinstance(value, str) and value.isascii() and value.isdigit(), "noncanonical unsigned integer")
    result = int(value)
    require(result <= 2**64-1, "integer exceeds uint64")
    return result


def close(actual, expected, field):
    require(math.isclose(number(actual), number(expected), rel_tol=2e-12, abs_tol=2e-14), f"numeric replay mismatch: {field}")


def table(path, columns):
    # Match the native unquoted CSV contract. Generic CSV readers silently
    # skip blank rows and accept quoting that the native source rejects.
    data = Path(path).read_bytes().split(b"\n")
    if data[-1] == b"":
        data.pop()
    lines = [line[:-1] if line.endswith(b"\r") else line for line in data]
    require(lines and lines[0].decode("ascii") == ",".join(columns), f"unexpected CSV schema: {path}")
    rows = []
    for line in lines[1:]:
        require(line and b'"' not in line and b"\r" not in line, "blank/quoted/malformed CSV record")
        values = line.decode("ascii").split(",")
        require(len(values) == len(columns), "malformed CSV width")
        rows.append(dict(zip(columns, values)))
    return rows


def model_values(path):
    lines = Path(path).read_text().splitlines()
    require(lines and lines[0] == "schema=bpfeat.taobao.features.v2", "model schema mismatch")
    values = {}
    for line in lines[1:]:
        require(line.count("=") == 1, "malformed model field")
        key, value = line.split("=")
        require(key not in values and value == value.strip() and bool(value), "duplicate/empty/padded model field")
        require(re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value) is not None, "nondecimal model value")
        values[key] = number(value)
    require(set(values) == {"bias", *(f"w{i}" for i in range(7))}, "incomplete/unknown model fields")
    return values["bias"], [values[f"w{i}"] for i in range(7)]


def verify(attempt, events, model):
    attempt = Path(attempt)
    require(not (attempt / "engine_failure.json").exists(), "failed attempt cannot pass replay")
    require(not (attempt / "engine_receipt.pending.json").exists(), "unfinished receipt")
    paths = {"events": Path(events), "model": Path(model), "receipt": attempt / "engine_receipt.json",
             "predictions": attempt / "predictions_unlabeled.csv", "controller": attempt / "batch_controller.csv"}
    require({path.name for path in attempt.iterdir()} == {"engine_receipt.json", "predictions_unlabeled.csv", "batch_controller.csv"}, "unexpected attempt membership")
    def hashes():
        result = {}
        for name, path in paths.items():
            require(path.is_file() and not path.is_symlink(), "expected regular diagnostic/input file")
            h = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b""):
                    h.update(chunk)
            result[name] = h.hexdigest()
        return result
    before = hashes()
    def reject_constant(value):
        raise ReplayError("nonfinite JSON constant: " + value)
    receipt = json.loads(paths["receipt"].read_text(), object_pairs_hook=unique_object, parse_constant=reject_constant)
    require(receipt.get("schema") == "bpfeat.engine.receipt.v3" and receipt.get("status") == "ENGINE_COMPLETED"
            and receipt.get("research_evidence") is False, "invalid diagnostic receipt")
    require(receipt.get("feature_schema") == "bpfeat.taobao.features.v2", "feature schema mismatch")
    mode = receipt["mode"]
    require(mode in ("fixed", "batch", "alpha", "joint"), "invalid mode")
    config = receipt["config"]
    integer_fields = {"batch_initial", "batch_min", "batch_max", "feature_slots", "batch_slots", "max_keys", "timeout_seconds"}
    real_fields = {"alpha_initial", "alpha_min", "alpha_max", "alpha_delta", "occupancy_gain", "low", "high", "shrink", "grow"}
    require(set(config) == integer_fields | real_fields, "incomplete config")
    require(all(type(config[k]) is int and config[k] > 0 for k in integer_fields), "invalid integer config")
    require(all(type(config[k]) in (int, float) and math.isfinite(config[k]) for k in real_fields), "invalid real config")
    require(0 < config["batch_min"] <= config["batch_initial"] <= config["batch_max"] <= 256, "batch bounds")
    require(0 < config["alpha_min"] <= config["alpha_initial"] <= config["alpha_max"] <= 1 and config["alpha_delta"] > 0, "alpha bounds")
    require(0 < config["occupancy_gain"] <= 1 and 0 <= config["low"] < config["high"] <= 1
            and 0 < config["shrink"] < 1 < config["grow"], "controller bounds")
    for key, maximum in (("feature_slots", 1048576), ("batch_slots", 4096)):
        slots = config[key]
        require(2 <= slots <= maximum and slots & (slots-1) == 0, "queue bounds")
    require(config["timeout_seconds"] <= 86400, "deadline bounds")
    bias, weights = model_values(model)
    require(type(receipt["model_parameters"]) is dict and type(receipt["model_parameters"].get("weights")) is list,
            "invalid model parameter types")
    number(receipt["model_parameters"]["bias"])
    for weight in receipt["model_parameters"]["weights"]:
        number(weight)
    require(receipt["model_parameters"] == {"bias": bias, "weights": weights}, "model parameter mismatch")
    events = table(events, ["seq", "event_ts_ns", "key", "item_id", "category_id", "behavior_code"])
    columns = ("seq,event_ts_ns,key,score,alpha_used,pressure_used,pressure_generation_used,pressure_available,"
               "source_created_ns,scored_ns,latency_ns,batch_size,batch_pressure,batch_pressure_generation,"
               "x0,x1,x2,x3,x4,x5,x6,item_id,category_id,behavior_code,pressure_sampled_ns,pressure_loaded_ns").split(",")
    predictions = table(paths["predictions"], columns)
    trace = table(paths["controller"], "generation,sampled_ns,occupancy_slots,occupancy_ema,batch_target,first_seq,last_seq,actual_count,is_tail".split(","))
    require(len(events) == len(predictions), "missing/extra predictions")
    for key in ("read", "extracted", "batched", "scored", "written"):
        require(type(receipt[key]) is int and receipt[key] == len(events), "counter conservation: " + key)
    for key in ("batches", "tail_batches", "source_block_retries", "batch_block_retries", "batch_actions", "direction_changes", "started_monotonic_ns", "finished_monotonic_ns"):
        require(type(receipt[key]) is int and 0 <= receipt[key] <= 2**64-1, "invalid receipt counter/clock: " + key)
    started, finished = receipt["started_monotonic_ns"], receipt["finished_monotonic_ns"]
    require(started <= finished, "engine clock regression")
    require(receipt["batches"] == len(trace), "batch counter mismatch")
    pressure = 0.0
    target = config["batch_initial"]
    observations, batch_rows = {}, {}
    actions = changes = previous_direction = tails = offset = 0
    previous_sampled = started
    for generation, row in enumerate(trace, 1):
        require(integer(row["generation"]) == generation, "missing/duplicate controller generation")
        sampled = integer(row["sampled_ns"])
        require(previous_sampled <= sampled <= finished, "controller clock regression")
        previous_sampled = sampled
        raw = number(row["occupancy_slots"])
        require(0 <= raw <= 1, "invalid slot occupancy")
        close(raw * (config["batch_slots"]-1), round(raw * (config["batch_slots"]-1)), "slot fraction")
        pressure = config["occupancy_gain"]*raw + (1-config["occupancy_gain"])*pressure
        close(row["occupancy_ema"], pressure, "occupancy EMA")
        # Replay discrete decisions with the actually emitted IEEE value after
        # independently checking its arithmetic. Otherwise a harmless alternate
        # rounding at a threshold could choose a different branch.
        used_pressure = number(row["occupancy_ema"])
        previous_target = target
        if mode in ("batch", "joint"):
            if used_pressure > config["high"] and target > config["batch_min"]:
                target = max(config["batch_min"], math.floor(target*config["shrink"]))
            elif used_pressure < config["low"] and target < config["batch_max"]:
                target = min(config["batch_max"], max(target+1, math.floor(target*config["grow"])))
        require(integer(row["batch_target"]) == target, "batch policy mismatch")
        direction = (target > previous_target) - (target < previous_target)
        if direction:
            actions += 1
            changes += int(previous_direction != 0 and previous_direction != direction)
            previous_direction = direction
        count = integer(row["actual_count"])
        tail = integer(row["is_tail"])
        require(0 < count <= target and tail in (0, 1), "invalid batch count/tail")
        require((count < target) == bool(tail) and (not tail or generation == len(trace)), "tail convention mismatch")
        group = predictions[offset:offset+count]
        require(len(group) == count, "unmatched batch rows")
        require(integer(row["first_seq"]) == integer(group[0]["seq"]) and integer(row["last_seq"]) == integer(group[-1]["seq"]), "batch identity mismatch")
        for record in group:
            require(integer(record["batch_size"]) == count and integer(record["batch_pressure_generation"]) == generation, "prediction batch join mismatch")
            close(record["batch_pressure"], pressure, "prediction batch pressure")
            require(integer(record["source_created_ns"]) <= sampled if record is group[0] else True, "batch precedes first source event")
            require(sampled <= integer(record["scored_ns"]), "scoring precedes batch sample")
        observations[generation] = (number(row["occupancy_ema"]), sampled)
        batch_rows[generation] = row
        tails += tail
        offset += count
    require(offset == len(predictions), "unbatched predictions")
    require((actions, changes, tails) == (receipt["batch_actions"], receipt["direction_changes"], receipt["tail_batches"]), "controller action counters")
    states = {}
    alpha = config["alpha_initial"]
    previous_seq = previous_event = previous_created = previous_scored = previous_generation = None
    for event, record in zip(events, predictions):
        event = {key: integer(value) for key, value in event.items()}
        require(event["behavior_code"] in range(4), "unknown behavior")
        for key, value in event.items():
            require(integer(record[key]) == value, "source identity/value mismatch: " + key)
        seq, timestamp, key = event["seq"], event["event_ts_ns"], event["key"]
        require(previous_seq is None or seq > previous_seq, "source sequence regression")
        require(previous_event is None or timestamp >= previous_event, "source event-time regression")
        previous_seq, previous_event = seq, timestamp
        created, loaded, scored = (integer(record[k]) for k in ("source_created_ns", "pressure_loaded_ns", "scored_ns"))
        require(started <= created <= loaded <= scored <= finished, "invalid per-item clock envelope")
        require(previous_created is None or created >= previous_created, "source creation clock regression")
        require(previous_scored is None or scored >= previous_scored, "scoring clock regression")
        previous_created, previous_scored = created, scored
        require(integer(record["latency_ns"]) == scored-created, "latency arithmetic mismatch")
        generation = integer(record["pressure_generation_used"])
        available = integer(record["pressure_available"])
        require(available in (0, 1), "invalid availability flag")
        require(previous_generation is None or generation >= previous_generation, "feedback generation regressed")
        previous_generation = generation
        if available:
            require(generation in observations, "unmatched pressure generation")
            value, sampled = observations[generation]
            close(record["pressure_used"], value, "loaded feedback")
            require(integer(record["pressure_sampled_ns"]) == sampled <= loaded, "feedback clock mismatch")
            require(generation <= integer(record["batch_pressure_generation"]), "future batch feedback")
            if mode in ("alpha", "joint"):
                target_alpha = config["alpha_min"] + (config["alpha_max"]-config["alpha_min"])*value
                alpha = min(config["alpha_max"], max(config["alpha_min"], alpha + min(config["alpha_delta"], max(-config["alpha_delta"], target_alpha-alpha))))
        else:
            require(generation == 0 and integer(record["pressure_sampled_ns"]) == 0 and number(record["pressure_used"]) == 0, "invented unavailable pressure")
        close(record["alpha_used"], alpha, "source alpha policy")
        require(key in states or len(states) < config["max_keys"], "key budget exceeded")
        state = states.setdefault(key, {"engagement": 0.0, "gap": 0.0, "pv": 0, "cart_fav": 0, "buy": 0, "count": 0, "last": None})
        gap = (timestamp-state["last"])/1e9 if state["last"] is not None else 0.0
        behavior = event["behavior_code"]
        used_alpha = number(record["alpha_used"])
        state["engagement"] = (1-used_alpha)*state["engagement"] + used_alpha*(1, 3, 2, 5)[behavior]
        state["gap"] = (1-used_alpha)*state["gap"] + used_alpha*gap
        state["pv"] += behavior == 0
        state["cart_fav"] += behavior in (1, 2)
        state["buy"] += behavior == 3
        state["count"] += 1
        state["last"] = timestamp
        features = [state["engagement"], math.log1p(state["pv"]), math.log1p(state["cart_fav"]),
                    min(gap, 3600)/3600, state["buy"]/state["count"], math.log1p(state["buy"]), state["gap"]]
        for i, expected in enumerate(features):
            close(record[f"x{i}"], expected, f"feature {i}")
        z = math.fsum([bias, *(w*x for w, x in zip(weights, features))])
        expected_score = 1/(1+math.exp(-z)) if z >= 0 else math.exp(z)/(1+math.exp(z))
        close(record["score"], expected_score, "logistic score")
    bindings = hashes()
    require(before == bindings, "input/diagnostic bytes changed during replay")
    return {"status": "DIAGNOSTIC_REPLAY_PASSED", "research_evidence": False, "rows": len(events), "batches": len(trace),
            "file_sha256": bindings, "limitations": ["input/provider and sensor authenticity not established", "no live-service deadlines or resource measurements", "reference loads diagnostic cohort in memory", "no sealed evaluation or scientific certification"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.attempt, args.events, args.model), indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError, OverflowError, csv.Error) as ex:
        print(json.dumps({"status": "DIAGNOSTIC_REPLAY_FAILED", "research_evidence": False, "error": str(ex)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
