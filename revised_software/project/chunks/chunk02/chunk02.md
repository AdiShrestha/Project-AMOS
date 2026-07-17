# Chunk 02: KLStream Runtime Core

**Project:** BPFeat
**Factory Version:** 1.0.1
**Owner:** Claude (Architect)
**Status:** Planned

---

## Objective

Implement the foundational KLStream runtime components: configuration, events, lock-free queues (SPSC and MPMC), operator interfaces, backpressure tracking, worker thread scheduling, and the runtime coordinator. Ensure that exact-count termination (INV-001) is built into the runtime coordinator from the start.

---

## Scope

### Included Work

- `source/include/klstream/core/config.hpp` — Runtime parameters and configuration structs.
- `source/include/klstream/core/event.hpp` — Core templated Event payload structures.
- `source/include/klstream/core/metrics.hpp` — Runtime metrics and latency tracking.
- `source/include/klstream/core/pinning.hpp` — Thread pinning and CPU affinity mapping.
- `source/include/klstream/core/spsc_queue.hpp` — Lock-free single-producer single-consumer ring buffer.
- `source/include/klstream/core/mpmc_queue.hpp` — Multi-producer multi-consumer concurrent queue.
- `source/include/klstream/core/operator.hpp` — Operator base class and thread-safe pipeline link definitions.
- `source/include/klstream/core/backpressure.hpp` — EMAOccupancyTracker and TokenBucketRateLimiter logic.
- `source/include/klstream/core/worker.hpp` — Cooperative scheduler and task execution loop.
- `source/include/klstream/core/runtime.hpp` — End-to-end runtime coordinator with exact-count matching handshake.
- Core library unit tests.
- CMake configurations under `source/`.

### Excluded Work

- Keyed feature extraction, elastic windows, and downstream scoring operators (Chunk 03).
- Offline preprocessing and oracle training pipelines (Chunk 04).
- End-to-end pipeline wiring and harness (Chunk 05).

---

## Repository State Required

- Repository status is clean (except for planned files in progress).
- Factory initialization (Chunk 01) is complete and approved.
- Roadmap has Chunk 01 marked as COMPLETE.
- requirements.txt is defined with base dependencies.

---

## Deliverables

1. `source/include/klstream/core/config.hpp`
2. `source/include/klstream/core/event.hpp`
3. `source/include/klstream/core/metrics.hpp`
4. `source/include/klstream/core/pinning.hpp`
5. `source/include/klstream/core/spsc_queue.hpp`
6. `source/include/klstream/core/mpmc_queue.hpp`
7. `source/include/klstream/core/operator.hpp`
8. `source/include/klstream/core/backpressure.hpp`
9. `source/include/klstream/core/worker.hpp`
10. `source/include/klstream/core/runtime.hpp`
11. `source/CMakeLists.txt`
12. Core unit tests under `source/tests/`

---

## Success Criteria

- All C++ files compile successfully with standard compiler settings (`-std=c++17` on GCC/Clang).
- Core unit tests pass successfully.
- Lock-free queues (SPSC/MPMC) pass concurrency checks without data races (verified via ThreadSanitizer).
- Exact termination matching handshake (INV-001) is implemented and verified.

---

## Acceptance Criteria

- [ ] Core configuration parameters and structures are defined in `config.hpp`.
- [ ] Core templated `Event` structure with metadata headers is defined in `event.hpp`.
- [ ] Runtime metrics collection and throughput/latency statistics are implemented in `metrics.hpp`.
- [ ] Cross-platform thread pinning and CPU affinity functions are implemented in `pinning.hpp`.
- [ ] Lock-free circular SPSC queue is implemented and tested in `spsc_queue.hpp`.
- [ ] Thread-safe lock-free/blocking MPMC queue is implemented and tested in `mpmc_queue.hpp`.
- [ ] Operator base class and basic operator interfaces are defined in `operator.hpp`.
- [ ] `EMAOccupancyTracker` and `TokenBucketRateLimiter` are implemented in `backpressure.hpp`.
- [ ] `Worker` scheduler class with pinning support is implemented in `worker.hpp`.
- [ ] `Runtime` coordinator with atomic event-count termination matching is implemented in `runtime.hpp`.
- [ ] `CMakeLists.txt` correctly configures the build targets for the core library.
- [ ] Test harness successfully verifies queues, scheduler, and exact-count termination logic.

---

## Contracts

This chunk is split into five sequential contracts:

1. **Contract C-02-1:** Core Utilities & Event Payload
   - Objective: Define config parameters, templated Event structure, metrics collectors, and CPU affinity handlers.
   - Files: `config.hpp`, `event.hpp`, `metrics.hpp`, `pinning.hpp`.
2. **Contract C-02-2:** SPSC & MPMC Lock-Free Queues
   - Objective: Implement high-performance lock-free queues for inter-operator thread communication.
   - Files: `spsc_queue.hpp`, `mpmc_queue.hpp`.
3. **Contract C-02-3:** Operator & Backpressure Tracking
   - Objective: Define the operator pipeline interface and implement backpressure telemetry trackers.
   - Files: `operator.hpp`, `backpressure.hpp`.
4. **Contract C-02-4:** Worker Scheduler & Core Threads
   - Objective: Implement cooperative scheduler workers executing operator tasks on pinned cores.
   - Files: `worker.hpp`.
5. **Contract C-02-5:** Runtime Coordinator & Verification
   - Objective: Implement the coordinator that orchestrates startup, pipeline execution, and exact termination tracking (INV-001). Configure CMake.
   - Files: `runtime.hpp`, `CMakeLists.txt`.

---

## Risks

- **Memory Ordering on Lock-Free Queues:** Queue push/pop operations use `std::atomic` and require exact memory order semantics (`acquire`, `release`, `relaxed`) to prevent data corruption.
- **Portability of Thread Pinning:** CPU affinity scheduling differs between macOS (`pthread_setaffinity_np` is not standard) and Linux. The implementation must dynamically adapt to the target platform (INV-004 compliance).
- **Termination Race Conditions:** The exact termination handshake must handle situations where upstream producers finish and queues are being drained, ensuring zero dropped events (INV-001).

---

## References

- [Project Description](file:///Users/adi/Desktop/Project%20AMOS/revised_software/project/project_description.md)
- [Architecture Details](file:///Users/adi/Desktop/Project%20AMOS/revised_software/project/architecture.md)
- [Invariants Checklist](file:///Users/adi/Desktop/Project%20AMOS/revised_software/project/invariants.md)
