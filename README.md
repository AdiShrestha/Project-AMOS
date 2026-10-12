# Project AMOS / BPFeat

A high-performance C++ engine for streaming event feature extraction, adaptive batching, and scoring.

## Overview

The engine provides streaming event processing across three pipelined stages:
1. **Source & Features**: parses raw event streams, computes causal engagement EMAs and event-gap statistics.
2. **Batch Controller**: manages bounded queue occupancy and adjusts batch boundaries via adaptive controllers.
3. **Scoring & Diagnostics**: applies linear model weights and records latency and batch telemetry.

**Status**: Verified engine foundation; no research evidence admitted.

## Building and Testing

Prerequisites: CMake 3.16+, C++17 compiler (Clang or GCC), Python 3.10+.

```sh
# Build in Release mode
cmake -S . -B build/release -DCMAKE_BUILD_TYPE=Release
cmake --build build/release -j 4

# Run test suite
ctest --test-dir build/release --output-on-failure

# Run unit tests
python3 -m unittest discover tests
```

## Diagnostic Verification

Engine outputs can be verified using the standalone diagnostic replay tool:

```sh
python3 -B tools/verify_engine_diagnostics.py --attempt ATTEMPT_DIR --events EVENTS_CSV --model MODEL_FILE
```

## Data and Licensing

Candidate datasets are quarantined under `data/quarantine/raw/` and excluded from source control. Raw datasets require verified provider terms before admission.

This project is licensed under the terms specified in [LICENSE](LICENSE).
