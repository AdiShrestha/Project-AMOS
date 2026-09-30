# Corrected engine boundary

This is a small C++17 CPU engine for **per-event feature extraction, batching, and scoring**. It replaces defective legacy execution paths and preserves the seven declared Taobao features. It is not yet the complete scientific system described in `plan.md`.

There are three actual workers: streaming source/features, batching/controller, and scoring/file output. Every successfully read event is extracted, batched, scored and written exactly once before success. EOF flushes the partial batch. Closed queues, joined workers and equal terminal counters are required. Failure cancels the workers and produces no successful engine receipt. The cooperative timeout cannot interrupt a blocking operating-system file call; a future research supervisor must enforce a process deadline.

The two queues are bounded SPSC with one reserved slot. `--feature-slots 1024` means 1023 usable entries; `--batch-slots 8` means seven batches. Slot occupancy is approximate under concurrency and does not measure bytes or service work. Queue storage contains constructed objects. The producer closes its own queue after its final accepted push; external concurrent close is not an admission barrier. This API does not provide MPMC or multi-producer support.

Input must be a regular, unquoted integer CSV with the exact header:

```text
seq,event_ts_ns,key,item_id,category_id,behavior_code
```

IDs and event timestamps are uint64. Sequence IDs must strictly increase but may have gaps. Global event timestamps must not decrease; equal timestamps are permitted. Behavior mapping is `pv=0, cart=1, fav=2, buy=3`. No labels, burst markers, amount values or ULB schema are accepted by this version. Raw candidates must first pass the admission, canonical ordering and labeling contracts.

Features are: engagement EMA with declared behavior weights `[1,3,2,5]`; `log1p(pv_count)`; `log1p(cart_count+fav_count)`; `min(event_gap_seconds,3600)/3600`; purchase count divided by all observed count; `log1p(purchase_count)`; and event-gap EMA. Both EMAs initialize to zero. First gap is zero and a separate seen flag makes timestamp zero valid. State uses the current observed event. This is causal for a future target that excludes all purchases at the current timestamp; it is unsuitable for predicting whether that same event is a purchase. Event-gap EMA is **not cached-feature age**. Numeric reference code is under `source/reference/`; strict-future label reference is under `source/preprocessing/`.

Model files must contain exactly this schema plus a finite bias and all seven finite weights, each once:

```text
schema=bpfeat.taobao.features.v2
bias=...
w0=...
w1=...
w2=...
w3=...
w4=...
w5=...
w6=...
```

The ellipses describe fields; they are not a valid model. There is no default trained model, zero-weight fallback or ULB adapter. Unknown fields, missing fields, duplicate fields, nonfinite numbers and schema mismatch fail. The current loader validates numeric structure, not model provenance; signed training scope and feature-policy binding are future requirements.

```sh
build/debug/bpfeat_engine --events PATH_TO_ADMITTED_EVENT_CSV --model PATH_TO_EXPLICIT_WEIGHTS --out-dir NEW_ATTEMPT_DIRECTORY --mode fixed
```

The required output directory must not exist; attempts cannot overwrite one another. Other modes are `batch`, `alpha`, and `joint`, forming the basic 2×2 controller toggle. Defaults are design choices, not fitted values or results:

| Option | Default |
|---|---:|
| `--batch-size`, `--batch-min`, `--batch-max` | 32, 8, 256 |
| `--alpha`, `--alpha-min`, `--alpha-max`, `--alpha-delta` | .10, .02, .30, .01 |
| `--occupancy-gain` | .10 |
| `--low`, `--high` | .30, .70 |
| `--shrink`, `--grow` | .70, 1.15 |
| `--feature-slots`, `--batch-slots` | 1024, 8 |
| `--max-keys`, `--timeout-seconds` | 1000000, 60 |

Batch feedback is sampled once per nonempty batch start. Idle polling and blocked retries do not advance it. Occupancy EMA starts at zero. A coherent pressure record contains value, generation, sample time and availability. Adaptive alpha holds the declared initial value until a pressure sample exists, then updates once per source event from the available record, subject to slew and bounds. Gain is global while feature state is keyed; this confounding and sampling cadence require explicit research review.

The batch law uses multiplicative decrease and multiplicative increase, with integer growth progress at the lower bound. It is MIMD. Decreasing batch size under pressure is retained as an explicit **unvalidated policy**; it has no proven stabilizing or compute-saving effect. `W` is batch size, not publication cadence, not an EMA horizon, and not a compute-skipping mechanism. All events are scored in every mode. Changing alpha leaves the EMA update O(1).

`predictions.csv` preserves every source sequence, event timestamp and key, actual features and score, alpha/pressure used, source creation time and per-item scoring time. `latency_ns` is scoring time minus creation time; creation is after parsing and before feature extraction. It excludes read/parse time, completed file write, durable storage, scheduled-arrival lateness and client response time. `controller_trace.csv` contains real nonempty batch-start observations. These files are diagnostics, not complete research telemetry. File formatting and writes currently lie on the scoring path.

`engine_receipt.json` records actual terminal counters and engine times only. Its status is `ENGINE_COMPLETED` and `research_evidence` is false. It does not bind input/model/binary hashes, admission, split integrity, training or factory certification. Partial CSVs left by failures cannot be admitted. Future end-to-end contracts must add process supervision, authoritative publication/query clocks, manifests, policy binding and independent replay.

Correctness fixtures exercise tiny queues, nonconsecutive sequences, EOF boundaries, concurrency, missing/malformed models, output failure, task domains, future-label censoring and analytic EMA identities. Debug/Release/address-and-undefined-behavior/ThreadSanitizer logs are in `docs/audit/`. No fixture throughput or score is a scientific result.
