## BPFeat: Backpressure-Driven Elastic Feature Windows for Real-Time ML Pipelines

### Complete Implementation & Research Build Prompt (for Copilot / a coding agent)

---

**How to use this document.** This file is written to be handed, as-is, to a coding agent (GitHub Copilot, Claude Code, etc.) as the single source of truth for building this project end to end. It assumes the agent has — or will be given read access to — the existing `KLStream` repository (the runtime built for the prior IT4D submission) and the existing `load-adaptive-iir` repository (the prior DSP mini-project). Every class name, file path, formula, and default parameter below is chosen to compose with those two repositories without translation. Where this document deviates from the original research brief (`Real-Time_ML_Feature_Pipeline_Control.docx`), Section 2 states the deviation and the reason for it explicitly — read Section 2 before writing any code, the same way the KLStream-AdaptiveWindow document insisted on Section 7.2 being read first.

This is intended as a serious, IEEE-conference-worthy research artifact, not a toy demo. Treat every "why" in this document as load-bearing for the eventual paper's Related Work and Methodology sections, not as throwaway commentary.

---

## Table of Contents

1. Relationship to Prior Work — What Already Exists, What Is New
2. Design Decision Log — Every Deviation From the Source Brief, Justified
3. The One-Paragraph Pitch
4. Prior Art Survey — Consolidated, Including New Findings Beyond the Source Brief
5. The Precise Gap and Research Questions
6. Why This Is Hard Enough to Be a Paper
7. Theoretical Foundation — Z-Domain Recap and the W↔α Equivalence
8. System Architecture — The Resolved Design
9. Data Sourcing — Taobao UserBehavior (Primary) and ULB Credit Card Fraud (Secondary)
10. Label and Feature Engineering
11. Python Offline Preprocessing Pipeline
12. New KLStream Types
13. `KeyedFeatureExtractOp` — Per-Key State and the Continuous α-Control Path
14. `AdaptiveFeatureWindowOp` and `BPFeatController` — The Core Contribution
15. `FixedWindowOp` (Reused) and `DriftAdaptiveWindowOp` (Literature Baseline)
16. `RateThrottleSource` Wiring — The Admission-Control Baseline
17. `ScoringFlushOp` — The O(W) Cost Engine
18. `BehaviorSource` — Replaying Taobao / ULB Data
19. `ResultSink` and Controller Trace Logging
20. Offline Model Training — Logistic Regression, Native Export
21. Repository Structure
22. CMake Integration
23. Full Pipeline Wiring — `main.cpp` for Each Architecture
24. Z-Domain Post-Hoc Analysis — Closing the Loop With Project 1
25. Evaluation Methodology — Metrics in Full
26. The Regret-Attribution Trap and How This Project Avoids It
27. Experiment Design — Six Experiments in Full
28. Statistical Rigor — Runs, Warmup, Confidence Intervals
29. Testing Strategy
30. Risks and Honest Difficulty Assessment
31. Build Timeline
32. Paper Outline and Venue Guidance
33. Full Reference List
34. Glossary of New Terms
35. Appendix — Ordered Task Breakdown for a Coding Agent

---

## 1. Relationship to Prior Work — What Already Exists, What Is New

This is the third project in a coherent three-project research arc. The agent building this should understand all three pieces before writing code, because this project's entire contribution is a *recombination* of validated parts from the first two, not a from-scratch system.

**Project 1 — `load-adaptive-iir` (completed).** A single-pole IIR / EMA filter whose smoothing coefficient α is driven by an exogenous system-load signal L[n] ∈ [0,1], with a slew-rate bound on how fast α can move per sample, analyzed formally in the Z-domain as a time-varying (frozen-time / quasi-static) system. Applied to financial tick smoothing for anomaly residual computation. The key reusable artifacts from this project are: (a) the exact control law `α[n] = α_max − (α_max − α_min)·L[n]` with the slew-rate clamp, (b) the frozen-time Z-domain analysis methodology (pole-zero plots, magnitude/phase response, group delay, swept over a representative α range and stitched into a time-varying frequency response heatmap), and (c) the general thesis that *an exogenous, system-state-driven control signal can legitimately replace a signal-derived adaptation law* for a recursive filter's coefficient.

**Project 2 — `KLStream` + the `AdaptiveWindowOp` research extension (completed, target venue IT4D 2026).** A bespoke, Kafka-less, lock-free, multi-core C++17 stream processing runtime (`KLStream`), plus a research extension that repurposes the runtime's own `EMAOccupancyTracker` — originally built to drive *admission-rate* throttling at a source operator — to instead drive *window size* at a windowing operator, creating a closed feedback loop between an operator's own output-queue occupancy and how much work its next invocation will have to do. Validated against `FixedWindowOp` (static baseline) and `DataDrivenWindowOp` (a volatility-driven, signal-based baseline modeled on the data-driven window-sizing literature), with rigorous evaluation machinery (PATR, WOR, LBA, the point-adjustment-trap-aware F1 computation) built specifically to avoid well-known evaluation pitfalls in the time-series anomaly detection literature.

**Project 3 — `BPFeat` (this document).** Takes the *mechanism* validated in Project 2 (an `EMAOccupancyTracker` on an operator's own output queue, driving an actuator other than admission rate) and applies it to a different actuator, in a different domain, against a different set of baselines, evaluated with a different (and arguably harder) metric: not "did we detect the anomaly," but "how much did the downstream ML model's predictive quality degrade because the features it was scored on were staler or more aggressively approximated than the oracle." It additionally reuses Project 1's continuous-pole control law — with the sign flipped, for reasons given in Section 2 — as a *second*, simultaneously active control loop, and reuses Project 1's frozen-time Z-domain analysis methodology as a post-hoc diagnostic applied to real logged traces from the running C++ system, rather than to a synthetic signal. This is the connective tissue across all three projects: Project 1 supplies the continuous-control theory, Project 2 supplies the discrete-control systems mechanism and runtime, Project 3 unifies both and asks a genuinely new applied question (feature freshness vs. compute cost in ML pipelines) that neither prior project addressed.

**What this document assumes already exists and is working**, referenced by file path exactly as in `KLStream_Complete_Implementation_Guide.md`:
- `include/klstream/core/config.hpp`, `event.hpp`, `spsc_queue.hpp`, `mpmc_queue.hpp`, `operator.hpp`, `pinning.hpp`, `metrics.hpp`, `backpressure.hpp`, `worker.hpp`, `runtime.hpp` (Sections 7.1–7.10 of the Implementation Guide)
- `include/klstream/operators/source.hpp`, `map.hpp`, `filter.hpp`, `aggregate.hpp`, `window.hpp`, `sink.hpp` (Sections 8.1–8.7)
- The root `CMakeLists.txt` and `klstream::klstream` interface target (Section 9.1)
- The `AdaptiveWindowController` pattern and the causal-chain mechanism from `KLStream_Research.md` Sections 7.2 and 14 (read these two sections in the existing repo before writing Section 14 of this document — the new controller below is a close sibling, not a copy-paste, and the differences matter)

If any of these files are missing from the checkout the agent is working in, recreate them exactly per the cited sections of `KLStream_Complete_Implementation_Guide.md` before proceeding — do not improvise alternate signatures, since downstream code in this document depends on the exact signatures quoted in Section 12 onward.

---

## 2. Design Decision Log — Every Deviation From the Source Brief, Justified

The research brief (`Real-Time_ML_Feature_Pipeline_Control.docx`) that motivated this project envisioned a production-realistic stack: Apache Flink, Kafka, Redis, on Kubernetes, with `KeyedProcessFunction`, watermarks, and checkpointing. That brief did excellent literature work (RALF, ADWIN, the Spark/Flink backpressure mechanisms, AQM) but its *implementation* framing does not match how this research program has built its first two projects, and does not match what a single person can build, control, and causally attribute results from inside a conference-paper timeline. This section is the same kind of explicit, defensible pivot that `KLStream_Research.md` Section 2 made for ONNX vs. native C++ — read it the same way: as a record of *why*, not as something to silently disagree with.

**Decision 1 — Build inside KLStream (C++17), not on real Flink/Kafka/Redis/Kubernetes.** A real distributed deployment introduces JVM GC pauses, network round-trip jitter, Kubernetes scheduler noise, and Kafka's own internal batching and replication — every one of which would confound the one variable this paper needs to isolate (window/freshness control policy). Project 2 already made and defended this exact trade-off (Section 2.5–2.6 of the Implementation Guide: "bounded queues + blocking backpressure as the baseline," extended with EMA-based adaptive backpressure, all single-node). Building Project 3 as a second research extension *inside the same runtime* means the only thing that changes between this paper's baselines and its contribution is the window/freshness control logic — exactly the clean attribution story that made Project 2 defensible, and exactly the property a real Flink deployment would destroy. The Flink-specific material in the source brief (Section "Architectural Blueprint," `KeyedProcessFunction`, watermarks, RocksDB state backend, checkpointing) is retained as Related-Work / Discussion content — it demonstrates the production mapping without requiring the production system to actually be stood up. State this explicitly in the paper's Discussion section: "the mechanism validated here maps directly onto Flink's `KeyedProcessFunction` + `ProcessingTimeTimer` API; we built a controlled, single-node analog to isolate causal attribution, consistent with how active queue management mechanisms (RED, CoDel) were first validated on single-queue models before wide deployment."

**Decision 2 — Two simultaneous control mechanisms, not one.** The source brief's Z-domain section proposes mapping an elastic sliding window onto an IIR pole. Taken literally, this would mean choosing *either* a discrete-batch actuator (à la Project 2's window size) *or* a continuous-pole actuator (à la Project 1's α), and most papers would stop at one. This project deliberately implements both, simultaneously, driven by the same backpressure signal, because: (a) it lets the paper make a genuinely new claim — formally and empirically demonstrating the equivalence the source brief only asserted — and (b) it maximizes reuse of already-validated code from both prior projects rather than inventing a third control law from nothing. Mechanism A (discrete, `W`, AIMD-controlled) governs *publish/refresh cadence* — directly implementing RALF's "extend the time between recomputations" lever. Mechanism B (continuous, α, slew-rate-bounded) governs *feature memory/reactivity* — directly implementing the IIR-pole framing from both the source brief and Project 1. Section 7 below derives the formal bridge between them (the EWMA span-to-alpha relationship); Section 24 tests the bridge empirically against real logged traces.

**Decision 3 — α moves in the *opposite* direction from Project 1, and this is stated explicitly rather than hidden.** In Project 1, rising backpressure *lowers* α (widens the smoothing window) because the cost being controlled is downstream alert volume — a smoother signal triggers fewer anomaly flags, which is what relieves load on whatever consumes those flags. In this project, rising backpressure *raises* α (narrows the effective memory). The cost being controlled here is different: under load, `W` is already being grown (publishes become less frequent — Mechanism A). Each individual publish therefore needs to count for more, not less; a long-memory (low-α) feature published rarely would compound staleness on top of infrequency. A short-memory (high-α) feature published rarely at least reflects whatever happened *recently*, rather than a smoothed-out average of the distant past. This is exactly the kind of detail a TAD-literate reviewer would ask about if it were left unaddressed, so it becomes a named discussion point in the paper: "Why the Direction of Pole Adaptation Is Application-Dependent, Not Universal" — Sections 14 and 25 are written to support that discussion honestly, including treating the W↔α empirical relationship as a hypothesis to be tested (Experiment 6), not an assumption.

**Decision 4 — Taobao UserBehavior as the primary dataset; ULB Credit Card Fraud as secondary, with its limitation stated up front.** The source brief's running example for fraud was "rolling count of transactions per card," but the standard Kaggle/ULB Credit Card Fraud dataset has no card, account, or merchant identifier at all — every feature except `Time` and `Amount` is an anonymized PCA component (`V1`–`V28`), specifically because the data was released this way to protect identity. A per-entity keyed rolling feature literally cannot be computed from this dataset. Rather than quietly inventing a synthetic key (which would be scientifically dishonest — exactly the kind of shortcut Project 2's wash-trading-proxy caveat explicitly refused to take), this project uses the Taobao UserBehavior dataset (Alibaba Tianchi; ~1M users, ~100M (user_id, item_id, category_id, behavior_type, timestamp) events, behavior ∈ {pv, cart, fav, buy}, Nov 25–Dec 3 2017) as the **primary** dataset, because it has a genuine entity key (`user_id`) and a genuine downstream-relevant label (purchase propensity), making it a faithful realization of the keyed streaming-feature scenario the whole project is about. The ULB Credit Card Fraud dataset is retained as a **secondary, generalization dataset**, used only for *global* (non-keyed) rolling aggregate features (count/sum of `Amount` in a trailing window across the entire stream) — this is an honest, explicitly scoped use that tests whether the mechanism generalizes to a domain with a different cost structure, without overclaiming entity-level capability the data does not support.

**Decision 5 — A native, hand-rolled logistic regression for downstream scoring, not ONNX, not a GBM served through a runtime.** This directly extends Project 2's own precedent (Section 2 of `KLStream_Research.md`: native C++ Isolation Forest, no ONNX Runtime, to avoid adding a large, fragile, version-sensitive dependency whose failure modes are orthogonal to the research question). A logistic regression's inference step is a dot product plus a sigmoid — trivially and exactly portable from a scikit-learn-trained weight vector to twenty lines of C++, with zero serialization-format risk. The research question is about window/freshness control, not about model-serving infrastructure; keeping the model itself as simple and exactly-reproducible as possible isolates the variable under test, exactly as Project 2 argued for its own model choice.

**Decision 6 — `DriftAdaptiveWindowOp` implements a simplified two-timescale EMA-crossover drift detector, not full ADWIN.** Real ADWIN maintains a sliding window of sub-windows and searches over all valid cut points for the one with the largest Hoeffding-bound-justified statistic gap — a meaningfully heavier piece of machinery than this baseline needs to make its point. The baseline exists to answer one question: "does a *signal-driven* (input-statistics-driven) adaptation law behave differently from a *load-driven* (queue-occupancy-driven) one?" A two-EMA crossover detector (fast EMA vs. slow EMA of per-tick engagement rate; shrink `W` when they diverge past a threshold, grow otherwise) answers that question with an order of magnitude less implementation risk while preserving the one property that matters for the comparison: it is a function of the *data*, never of the *queue*. This mirrors exactly how `DataDrivenWindowOp` in Project 2 was scoped (Section 15 of `KLStream_Research.md`) — a literature-style baseline, not a literature-reproducing one. State this scoping decision explicitly in the paper, citing Bifet & Gavaldà (2007) for the concept being approximated.

**Decision 7 — `RateThrottleSource` is not a new mechanism; it is Project 2's *original* admission-control extension, redeployed here as a baseline.** Project 2's `EMAOccupancyTracker` + `TokenBucketRateLimiter` pair (`backpressure.hpp` Section 7.8) was originally built to throttle a source operator's emission rate — this is, structurally, exactly what Spark Streaming's `PIDRateEstimator` and Flink's credit-based flow control do in production. Reusing it here, unmodified, as the third baseline (representing "current industry practice: throttle ingestion, leave window/freshness semantics untouched") produces a uniquely strong paper structure: the same codebase, the same `EMAOccupancyTracker` class, the same backpressure signal, driving three genuinely different actuators (admission rate / Baseline 3, window size and α / the contribution), compared directly. Note precisely for accuracy: Spark's `PIDRateEstimator` lives in the legacy DStream-based Spark Streaming API, not Structured Streaming — cite it correctly as such in the paper's related work.

**Decision 8 — Feature Regret, not detection F1, is the headline accuracy metric.** This project does not detect discrete events; it serves continuous-valued features to a downstream classifier. The correct accuracy metric is therefore RALF's notion of *regret* (Aderghal/Russo et al., VLDB 2024 — verify exact author list against the published paper before citing) — the gap between the downstream model's loss using the system's actual (possibly stale/approximated) features versus an oracle's loss using maximally fresh, unbatched features — not a detection-style F1/precision/recall, which would be a category error here. Section 25 defines this precisely; Section 26 names and defends against the analogous evaluation trap to Project 2's point-adjustment trap.

---
## 3. The One-Paragraph Pitch

Real-time ML feature pipelines face a freshness-vs-cost trade-off that current practice treats as a static configuration problem: an engineer picks a fixed TTL, a fixed window size, or a fixed refresh cadence, once, by hand, and the system lives with that choice regardless of load. We treat this as a closed-loop control problem instead. We repurpose a backpressure signal — the EMA-smoothed occupancy of a stream-processing operator's own output queue, already validated as a control input in our prior systems work — to drive two coupled actuators simultaneously: how often a per-key feature snapshot is republished to a downstream model (a discrete, AIMD-controlled window size) and how reactive that feature's underlying exponential moving average is to recent events (a continuous, slew-rate-bounded IIR pole). We implement both inside a real, multi-threaded, lock-free C++ stream runtime; compare against three baselines spanning current practice (a static window, a literature-style input-statistics-driven window, and an admission-rate-throttling baseline structurally identical to Spark's and Flink's production backpressure mechanisms); and evaluate not via a window-size proxy metric but via the actual downstream cost that matters — the degradation in a real classifier's predictive quality (regret, in RALF's sense) caused by the features it was scored on being staler or more aggressively smoothed than an oracle's. To our knowledge, no prior systems paper treats feature-pipeline freshness-vs-cost as a closed-loop, queue-state-driven control problem with both a discrete and a continuous actuator, formally connects the two via the EWMA span-to-α identity, and validates the connection empirically rather than asserting it.

---

## 4. Prior Art Survey — Consolidated, Including New Findings Beyond the Source Brief

The source brief already surveyed feature-store and AQM literature well. The items marked **[NEW]** below were not in the source brief and were found during an independent research pass for this document; they matter because two of them (Biathlon, the Cisco patent) are *closer* prior art than anything the source brief cited, and engaging with them honestly is what will make this paper's novelty claim survive review rather than collapse under a reviewer's first search.

### 4.1 Feature Stores — Freshness as a Static or Per-Request Configuration

- **RALF** (Russo et al., VLDB 2024 — verify exact citation before submission) — the closest prior systems work. Periodically re-prioritizes which keys' features get recomputed under a fixed compute budget, using a "feature store regret" objective that explicitly accounts for how staleness affects downstream model loss. Critically, RALF's scheduler operates in **discrete refresh decisions per key, polled against a budget**, not as a continuous feedback loop reacting to a live queue-occupancy signal — there is no actuator analogous to this project's continuous α-control, and no architectural connection to a stream-processing runtime's own backpressure state. We adopt RALF's *regret* formalization directly as this project's headline accuracy metric (Section 25) and must cite it as the closest related system in the paper, not relegate it to a passing mention.
- **Feast, Tecton, Hopsworks, Chalk** — industrial feature stores. Freshness is governed by configured TTLs and materialization schedules set by an engineer, not adapted online. Useful as the "current industry practice" framing in the Introduction.

### 4.2 [NEW] Biathlon — Approximate Feature Aggregation for ML Inference Pipelines (VLDB 2024)

Found independently during research for this document; **this is the single closest piece of prior art and must anchor the Related Work section, ahead of RALF.** Biathlon determines, per inference request, the degree of statistical approximation to apply to an aggregation feature so that the resulting accuracy loss stays within a guaranteed bound, evaluated on real production-style ML inference pipelines with expensive aggregation features. The crucial distinction to draw explicitly in the paper: Biathlon's lever is chosen **per request**, from an **accuracy-bound target** (an endogenous, statistical criterion — "how much can I approximate this aggregate and still guarantee an error bound on this prediction"). This project's lever is chosen **at the operator level, continuously**, from an **exogenous, system-state signal** (queue occupancy — "how loaded is my downstream consumer right now"). The two are complementary, not competing: a system could in principle run both (Biathlon deciding per-request sample size; this project's controller deciding how often and how reactively the underlying aggregate is refreshed at all). State this complementarity explicitly rather than implying competition — it is both honest and strengthens the paper's framing.

### 4.3 [NEW] ADWISE — Adaptive Window-Based Streaming Edge Partitioning (IEEE ICDCS 2018)

Found independently; the closest **structural** analog to this project's discrete actuator, outside the ML feature-store space entirely. ADWISE adapts a streaming graph partitioner's batch window size at runtime based on measured assignment latency, growing the window while a latency target is met and shrinking it otherwise, trading partition quality against latency. This is the same "elastic window size as a latency-vs-quality actuator" idea this project uses, but: (a) the domain is graph partitioning, not ML feature serving; (b) the control signal is a measured *latency*, not a queue-occupancy *EMA*; and (c) there is no continuous second actuator and no downstream ML-model-regret evaluation. Cite this as the closest non-ML structural precedent for "elastic windows as a load actuator," and use the comparison to sharpen, not undermine, this project's novelty claim: the mechanism generalizes the idea ADWISE pioneered in one systems niche to a different actuator pairing (discrete + continuous) and a different evaluation philosophy (downstream-model-regret rather than partition-quality).

### 4.4 [NEW] US Patent 9,521,158 — "Feature Aggregation in a Computer Network" (Cisco-style, network telemetry)

Found independently; the most directly on-point piece of **non-academic** prior art and must not be omitted from the related-work search, since a reviewer doing the same search this document's author did would find it immediately. The patent describes closed-loop control of feature-aggregation parameters (a time window or sampling rate feeding an ML classifier) that adapts based on measured network congestion, in a network-intrusion/DDoS-monitoring context. This predates and structurally resembles the present mechanism (congestion-state-driven aggregation-parameter control feeding an ML classifier) more closely than any academic citation found. Distinguish honestly: it is scoped to network telemetry/security classifiers, not general ML feature stores; it does not formalize a Z-domain / IIR treatment; it does not pair a discrete actuator with a continuous one; and it does not evaluate via downstream-model regret against an oracle. Cite it as prior art in the Related Work section exactly as the paper would cite a closely related patent in any systems venue — acknowledging it strengthens the paper's credibility rather than weakening it (a reviewer who finds it after the paper fails to mention it is a worse outcome than the paper citing and distinguishing it itself).

### 4.5 [NEW] Dynamic Batching for ML Inference Serving (Clipper, Triton/Nvidia dynamic batcher, continuous-batching LLM serving systems)

An adjacent body of work that must be engaged with directly rather than ignored: serving systems widely adapt *batch size* to queue depth or latency SLA to trade throughput against tail latency. The load-bearing distinction for this paper: dynamic batching groups already-arrived, independent *requests* for one forward pass — a pure throughput optimization with no information loss, since each request is still scored on its own true input. This project's discrete actuator (`W`) instead controls how many raw *events* get folded into a per-key feature's *temporal aggregate* before that aggregate is republished — changing what information the feature itself encodes (which is exactly the freshness/information trade-off this paper is about), not just how many independent items get processed per kernel launch. State this distinction explicitly in Related Work; do not let a reviewer draw the (wrong) conclusion that this is "just dynamic batching with extra steps."

### 4.6 Active Queue Management (AQM) — Conceptual Ancestor

RED, CoDel, PIE: queue-occupancy-driven control loops, but the actuator is always a drop/mark decision on packets, never a downstream computation's window size or smoothing coefficient. Retained from the source brief as the conceptual-ancestor citation, exactly as Project 2's literature review used it.

### 4.7 Backpressure Mechanisms in Production Stream Processors

Spark Streaming's legacy `PIDRateEstimator` (DStream API — cite correctly, not Structured Streaming) and Flink's credit-based flow control both throttle *admission rate* in response to downstream load. Neither adapts a window size or a smoothing coefficient. This is precisely what `RateThrottleSource` (Section 16) operationalizes as a baseline, making this comparison concrete and empirical rather than purely textual.

### 4.8 Concept-Drift-Adaptive Windowing

ADWIN (Bifet & Gavaldà, SDM 2007) and its descendants adapt a window size based on a statistical test for distributional change in the *data*. This is the literature ancestor for `DriftAdaptiveWindowOp` (Section 15); the gap this paper identifies relative to this whole line of work is the same one Project 2 identified relative to its own data-driven baseline: none of it responds to *system load*.

### 4.9 The Gap Table

| Prior work | Adapts what | Driven by | Evaluated via | What this project adds |
|---|---|---|---|---|
| RALF (VLDB '24) | refresh schedule per key | regret-weighted budget poll | downstream regret | continuous queue-driven loop, not periodic poll; pairs with a continuous actuator |
| Biathlon (VLDB '24) | per-feature approximation degree | per-request accuracy bound | accuracy-bound guarantee | exogenous system-state signal instead of endogenous accuracy target; operator-level not request-level |
| ADWISE (ICDCS '18) | batch window size | measured latency | partition quality | applies the idea to ML feature serving; pairs with a continuous actuator; regret-based evaluation |
| US Patent 9,521,158 | aggregation window / sample rate | network congestion | (not academically evaluated) | general ML feature-store framing; formal Z-domain treatment; regret evaluation against oracle |
| Dynamic batching (Clipper, Triton, etc.) | request batch size | queue depth / SLA | throughput, tail latency | the lever changes feature *information content*, not just request grouping |
| ADWIN and descendants | window size | data drift statistic | concept-drift accuracy | exists in this paper as `DriftAdaptiveWindowOp`, the literature-style baseline directly contrasted against the load-driven contribution |
| Spark `PIDRateEstimator` / Flink credit flow control | admission rate | queue/processing-time signal | throughput stability | exists in this paper as `RateThrottleSource`, reusing Project 2's own mechanism as a baseline against a *different* actuator |
| AQM (RED, CoDel) | packet drop/mark | queue occupancy | throughput, fairness | conceptual ancestor; this paper's actuator is a computation parameter, not a drop decision |

---

## 5. The Precise Gap and Research Questions

**RQ1 (mechanism).** Can an `EMAOccupancyTracker` reading from a stream operator's own output queue — already validated as a control signal for admission-rate throttling (Project 2's original extension) and for window-size control in an anomaly-detection pipeline (Project 2's `AdaptiveWindowOp`) — be repurposed, unmodified, to simultaneously drive a discrete publish-cadence actuator and a continuous IIR-pole actuator in a keyed ML feature pipeline, without conflict between the two control loops?

**RQ2 (equivalence).** Does the discrete window-size control law and the continuous α control law, when driven by the same backpressure signal, produce empirically consistent "effective memory" trajectories under the EWMA span-to-α identity (Section 7), or do they diverge — and if they diverge, under what load conditions and why?

**RQ3 (cost-quality trade-off).** Relative to a static baseline, a data-drift-driven baseline (`DriftAdaptiveWindowOp`), and an admission-throttling baseline (`RateThrottleSource`) — all sharing the identical runtime, identical pretrained downstream model, and identical workload — does the backpressure-driven controller achieve a more favorable Pareto frontier between (a) throughput retention under burst load and (b) downstream model regret, than any of the three baselines achieve individually?

**RQ4 (generalization).** Does the mechanism's qualitative behavior (throughput retention gain without proportionally larger regret) hold on a second dataset (ULB Credit Card Fraud) with a structurally different cost profile (global, non-keyed aggregation instead of per-key), or is the result an artifact specific to the Taobao workload's particular key cardinality and event-rate distribution?

These four questions are each directly falsifiable by one or more of the six experiments in Section 27, and RQ2 in particular is treated as a genuine open empirical question (Decision 3, Section 2) rather than something assumed true going in.

---

## 6. Why This Is Hard Enough to Be a Paper

Five reasons, each addressed by a specific piece of this design, mirroring the rigor Project 2 applied to the same question for its own contribution:

1. **Two simultaneously active control loops can fight each other.** If `W` grows (publishing less often) at the same moment α is rising (feature memory shrinking), is the net effect on staleness ambiguous? Section 14 and Experiment 6 (Section 27) directly measure and report this rather than assuming the two loops are compatible by construction.
2. **A discrete AIMD controller and a continuous slew-rate-bounded controller have different natural timescales.** `W`'s controller updates once per window-firing event (variable rate, since window size itself varies); α's controller updates once per raw event (fixed rate). Getting their relative reactivity wrong could make one loop dominate the other's effect on the system. This is exactly why Decision 3 frames the W↔α relationship as an empirical question, not a guaranteed one.
3. **The right accuracy metric is not obvious and the wrong one would be misleading.** A naive evaluation might report "feature freshness" in milliseconds and stop there — exactly the proxy-metric trap Project 2's Section 24 warned against for detection F1. Section 26 names and defends against the analogous trap here: reporting staleness alone, without connecting it to actual downstream model regret, would let a system that publishes garbage instantly "win" on a metric that does not measure what matters.
4. **A keyed, multi-tenant stream (many users sharing one global backpressure signal) introduces a fairness question a single-stream system never has to answer**: does a global `W`/α controller systematically starve low-traffic users of freshness in favor of high-traffic ones? This is a genuine open question this project's evaluation must check (folded into Experiment 3, Section 27), not an assumption to wave away.
5. **Generalization across a genuinely different cost structure (keyed vs. global aggregation) is the actual test of whether this is a domain-specific trick or a real systems mechanism.** Experiment 5 (the ULB dataset) exists specifically because a result that only holds on one dataset, with one key cardinality, is a much weaker claim than the source brief's stated ambition ("fraud, recsys, ad-bidding") would suggest, and a careful reviewer will ask for exactly this check.

---

## 7. Theoretical Foundation — Z-Domain Recap and the W↔α Equivalence

### 7.1 Recap of Project 1's Control Law (Mechanism B's Ancestor)

Project 1 defines, for a single-pole IIR/EMA filter `y[n] = α[n]·x[n] + (1-α[n])·y[n-1]`, a load-driven coefficient:

```
α[n] = α_max − (α_max − α_min) · L[n]            (Project 1, Section 1.2)
|α[n] − α[n−1]| ≤ Δα_max                          (Project 1, Section 1.3, default Δα_max = 0.01/sample)
```

with `α_min = 0.02`, `α_max = 0.30` as defaults, and `L[n] ∈ [0,1]` an exogenous load signal. Under this law, rising load *lowers* α (widens the effective window) — appropriate when the cost being controlled is downstream alert/event volume, since a smoother signal triggers fewer threshold crossings.

### 7.2 Mechanism B's Control Law (Sign-Flipped, Justified in Decision 3)

This project uses the same functional form with the roles of `α_min`/`α_max` swapped relative to which load level they correspond to:

```
α[n] = α_min + (α_max − α_min) · L[n]             (Mechanism B)
|α[n] − α[n−1]| ≤ Δα_max
```

Defaults: `α_min = 0.02` (calm — long effective memory, ~99 events), `α_max = 0.30` (stressed — short effective memory, ~5.7 events), `Δα_max = 0.01` per raw event, `L[n]` taken from the *same* `EMAOccupancyTracker` reading used by Mechanism A (Section 14) — not a second, independent tracker; this is a deliberate scoping choice (Decision 3) to keep the two control loops' relationship empirically interpretable rather than introducing a second, potentially decorrelated, signal.

### 7.3 The EWMA Span–to–α Identity (the Formal Bridge)

The standard identity relating an exponential moving average's smoothing coefficient to an equivalent simple-moving-average "span" `N` (this is the exact relationship `pandas.DataFrame.ewm(span=N)` uses internally, and the one to cite for it):

```
α = 2 / (N + 1)      ⟺      N = 2/α − 1
```

This is the formal content behind the source brief's "mapping IIR poles to elastic sliding windows" framing, and the precise tool this project uses to test RQ2. At any instant `n`, Mechanism B's α[n] has an *equivalent span* `N_α[n] = 2/α[n] − 1` — "the effective number of recent events this feature's memory currently represents." Mechanism A's `W[n]` is, separately, "the number of raw events folded into the next published batch." These are conceptually different quantities (one is a *memory horizon*, the other is a *publish granularity*), and the paper's claim is **not** that they are the same thing by definition — it is the empirically testable claim that, under a shared backpressure signal, **they move together** (both shrink under load, both grow under calm), and Experiment 6 (Section 27) reports the actual empirical correlation between the logged `N_α[n]` and `W[n]` traces from a real run, honestly, including if it is weaker than expected.

### 7.4 Frozen-Time Z-Domain Analysis, Retargeted

Project 1's frozen-time methodology — treat α as constant over a short window, compute the standard single-pole IIR transfer function `H(z) = α / (1 − (1−α)z⁻¹)`, its pole at `z = 1−α`, magnitude/phase response via `H(e^{jω})`, and group delay, then sweep across a representative range of α and stitch the results into a time-varying frequency-response heatmap — is reused verbatim as a *post-hoc diagnostic*, applied in Section 24 to the real, logged α[n] trace produced by a genuine run of `AdaptiveFeatureWindowOp` against the Taobao replay, rather than to a synthetic signal as in Project 1. This is what makes Project 3's Z-domain content a genuine empirical contribution rather than a re-statement of Project 1's theory: the same machinery, pointed at real data from a real system under real backpressure, producing the flagship "passband narrowing under backpressure" visualization with an actual causal story behind it (a real burst in the Taobao replay caused real queue occupancy to rise, which moved a real α[n] and a real W[n], logged from a real C++ run) instead of a designed synthetic load trace.

### 7.5 Worked Numeric Sanity Check (Include This in the Paper's Theory Section)

At calm (`L=0`): α=0.02 → `N_α` = 2/0.02 − 1 = 99 events of effective memory. At full stress (`L=1`): α=0.30 → `N_α` = 2/0.30 − 1 ≈ 5.67 events. Over the same range, Mechanism A moves `W` from `w_max=256` (calm) down to `w_min=8` (stressed) — i.e., across the same calm-to-stressed range, the *publish-cadence* horizon shrinks by a factor of 32, while the *memory* horizon shrinks by a factor of ~17.5. These are not designed to match exactly — stating this mismatch up front, with the exact numbers, is more credible than implying a 1:1 correspondence the chosen defaults do not actually produce; Experiment 6 is what determines whether the *trajectories* (not the static endpoints) track each other in practice.

---

## 8. System Architecture — The Resolved Design

### 8.1 The Pipeline

```text
BehaviorSource ──▶ KeyedFeatureExtractOp ──▶ [WindowOp variant] ──▶ ScoringFlushOp ──▶ ResultSink
  (replays Taobao      (Map operator; O(1)         ▲                  (pops ONE Event<
   UserBehavior         per event; updates          │ reads occupancy   FeatureBatch>;
   events keyed by      per-user EMAFeatureState     │ of ITS OWN         for each of the W
   user_id; optional    in a bounded hash map         │ output queue       buffered FeatureSnapshots:
   burst injection;     using α[n] from Mechanism    │                    native logistic-
   ULB secondary mode   B [Section 13]; emits one    AdaptiveFeatureWindowOp  regression scoring,
   for the global,      FeatureSnapshot Event per    (this operator only;     O(1) each → O(W)
   non-keyed variant)   raw event)                    other 3 variants do       total per tick();
                                                       not read any               writes ScoredResult,
                                                       occupancy signal)          refreshes
                                                                                   last_publish_ts)
```

Four interchangeable window-stage implementations, swapped via a command-line flag, all producing the same `Event<FeatureBatch>` type so `ScoringFlushOp` and everything downstream is completely unaware which window strategy is active — exactly the interchangeability property that made Project 2's three-architecture comparison clean.

| Variant | File | Sizing logic | Represents |
|---|---|---|---|
| `FixedWindowOp` | reuses `klstream/operators/window.hpp` unmodified | constant `W = 128` | static configuration (current default practice) |
| `DriftAdaptiveWindowOp` | new, `klstream/feature/drift_adaptive_window_op.hpp` | two-EMA crossover on engagement rate | literature-style, data-driven adaptation (ADWIN lineage) |
| `FixedWindowOp` + `RateThrottleSource` | reuses `backpressure.hpp` unmodified, wired at `BehaviorSource` | constant `W = 128`, throttled admission rate | current industry practice (Spark/Flink-style admission control) |
| `AdaptiveFeatureWindowOp` | new, `klstream/feature/adaptive_feature_window_op.hpp` | EMA of its own output queue's occupancy, driving both `W` and α | the contribution |

### 8.2 The Causal Chain (Read Before Writing Any Code)

1. `ScoringFlushOp::tick()` pops **one** `Event<FeatureBatch>` per call. A `FeatureBatch` holds up to `MAX_FEATURE_BATCH` `FeatureSnapshot`s (each already containing a user's current feature vector, computed upstream by `KeyedFeatureExtractOp`).
2. Inside that single `tick()` call, `ScoringFlushOp` scores **every snapshot in the batch** with the native logistic regression (a fixed-cost dot product + sigmoid per snapshot) and writes a `ScoredResult` for each. Total cost per `tick()` call: **O(W·d)**, `d` = feature dimension (constant), so effectively **O(W)**.
3. Because KLStream's cooperative scheduler calls `tick()` in a tight, non-preemptive loop, a larger `W` makes this one `tick()` call take measurably longer in wall-clock time — the same mechanism Project 2 established, applied to a different per-item cost function (a dot product instead of an Isolation Forest path traversal).
4. While `ScoringFlushOp` is busy inside one long `tick()`, it is not popping its input queue — which is the window operator's output queue. That queue's occupancy rises.
5. `AdaptiveFeatureWindowOp` owns an `EMAOccupancyTracker` wrapping **exactly this queue** (its own output, `ScoringFlushOp`'s input) — the same load-bearing pattern as Project 2's `AdaptiveWindowOp`. Rising occupancy → rising EMA → the controller shrinks the **next** window's target `W` (captured once at window start, held fixed for the in-progress window — never mid-window).
6. Smaller next window → shorter next `tick()` call inside `ScoringFlushOp` → faster drain → occupancy falls → `AdaptiveFeatureWindowOp` grows `W` back. Closed loop.
7. **Simultaneously**, every raw event processed by `KeyedFeatureExtractOp` reads the *same* tracker's published EMA reading (via a small shared `BackpressureSignal` struct, Section 12.5) to compute α[n] under Mechanism B (Section 7.2), independently of whether a window has just fired. This is the second control loop, running at a different cadence (per-event, not per-window) but off the identical signal.

This causal chain — with both consequences (W and α) explicitly traced from the same root signal — is what the paper's System Design section describes, with a diagram. Experiment 1 (Section 27) exists specifically to demonstrate both halves happen as described, not just the `W` half.

### 8.3 Why Mechanism B Lives Inside `KeyedFeatureExtractOp`, Not `AdaptiveFeatureWindowOp`

α has to be applied **once per raw event, per key**, the moment that event updates its user's EMA state — which happens upstream of any batching decision. `AdaptiveFeatureWindowOp` only ever sees already-computed `FeatureSnapshot`s; it has no per-key state and must not acquire any (that would break the O(1)-per-tick property that keeps its own cost independent of `W`, which is essential to the causal chain in 8.2). `AdaptiveFeatureWindowOp` is therefore the **owner and publisher** of the shared backpressure signal; `KeyedFeatureExtractOp` is a **reader** of it. This ownership direction must not be reversed.

---

## 9. Data Sourcing — Taobao UserBehavior (Primary) and ULB Credit Card Fraud (Secondary)

### 9.1 Taobao UserBehavior — Primary Dataset

Source: Alibaba Tianchi (`https://tianchi.aliyun.com/dataset/649`), free but requires a Tianchi account registration (state this plainly in the README — unlike Kaggle, there is no anonymous direct-download link). Fields, comma-separated, no header row in the raw release: `user_id, item_id, category_id, behavior_type, timestamp` where `behavior_type ∈ {pv, buy, cart, fav}` and `timestamp` is Unix seconds. Coverage: November 25 – December 3, 2017; roughly 1 million users and 100 million behavior records in the full release.

**Practical subsampling plan** (do not attempt to process the full 100M-row release on a laptop): select a contiguous block of `N_USERS` users (recommend starting with 5,000–20,000, chosen by `user_id` hash bucket, not by row order, to avoid any ordering artifact in the raw file) and retain every event belonging to those users across the full 9-day window. This typically yields a few million events — large enough for a meaningful burst/calm contrast and a meaningful number of `buy` labels, small enough to load entirely into memory for `BehaviorSource` (Section 18), mirroring Project 2's "LOBSTER sample fits comfortably in RAM, no streaming I/O during the actual run" design choice.

**Burst injection**, mirroring Project 2's Section 9 methodology exactly: tag a subset of time intervals as `is_burst_period = 1` (e.g., short windows of artificially compressed inter-arrival time during replay, simulating a flash-sale-like traffic spike — Taobao's own data already contains natural diurnal bursts around the dataset's known "Double 11"-adjacent dates; prefer using **real** natural bursts identified from the raw arrival-rate time series over purely synthetic injection where possible, falling back to synthetic compression only where the real data does not provide enough burst/calm contrast for a clean Experiment 2).

### 9.2 ULB Credit Card Fraud — Secondary, Generalization Dataset, With Its Limitation Stated Plainly

Source: Kaggle, `mlg-ulb/creditcardfraud` (also hosted via the ULB Machine Learning Group). 284,807 transactions over two days, 492 fraudulent (0.172%), fields `Time` (seconds elapsed since the first transaction in the dataset), `V1`–`V28` (PCA-anonymized, no semantic meaning individually), `Amount`, `Class` (1 = fraud). **There is no card, account, or merchant identifier in this dataset** — this is by design, for anonymization, and means no per-entity keyed rolling feature can be computed from it. This project therefore uses it **only** for a *global* (non-keyed) variant of the pipeline: a single rolling count and rolling sum/EMA of `Amount` across the entire transaction stream (effectively `user_id = 0` for every event, a degenerate one-key case of the same `KeyedFeatureExtractOp` code path — no special-casing needed, see Section 13.4), used in Experiment 5 (Section 27) purely to test whether the throughput-retention-vs-regret result generalizes to a structurally different (single global key, much higher event rate per key) workload. State this scoping plainly in the paper's Experimental Setup section — do not imply this dataset supports the "velocity check per card" framing from the original research brief, because it does not.

### 9.3 Practical Acquisition Checklist

1. Register a Tianchi account; download `UserBehavior.csv` (the full release is large — several GB compressed; download once, subsample locally per Section 9.1, do not re-download per experiment run).
2. Download `creditcard.csv` from Kaggle (`mlg-ulb/creditcardfraud`), no registration friction beyond a Kaggle account.
3. Store both raw files under `data/raw/` (gitignored — both datasets are large and/or have redistribution restrictions; commit only the small preprocessed replay CSVs under `data/replay/`, exactly mirroring Project 2's `data/raw/` vs `data/replay/` split).
4. If Tianchi registration is delayed or blocked, fall back to a synthetic-but-realistic Taobao-shaped generator (Zipfian item popularity, power-law-ish per-user event rate, configurable `buy` conversion rate) so development is not blocked on data access — flag clearly in the README that results from the synthetic fallback are for pipeline validation only, not for the paper's headline numbers, exactly mirroring Project 2's Section 9.4 fallback-generator caveat.

---

## 10. Label and Feature Engineering

### 10.1 The Label (Taobao)

Per user, per event, a forward-looking binary label computed **offline, in Python, before replay** (the online C++ system never sees this — it is ground truth for training and evaluation only, exactly mirroring Project 2's `injection_log.csv` separation):

```
label[i] = 1  if the user's NEXT `buy` event occurs within H raw events of event i (recommend H = 5)
         = 0  otherwise (or if the user has no further `buy` event in the dataset)
```

`H` measured in **the user's own event count**, not global event count or wall-clock time — this is "is this user about to convert," the natural recsys/ad-bidding-style propensity target the source brief's RecSys application section describes. Exclude the last `H` events of each user's sequence from labeled training data (look-ahead would run off the end of the observed window) but retain them in the replay stream itself (the online system still needs to process them; they are simply excluded from the *labeled* evaluation set, with this exclusion documented in the preprocessing script's output summary).

### 10.2 Per-User EMA Feature State (Online, Computed by `KeyedFeatureExtractOp`)

Maintained per `user_id` in a bounded hash map (Section 13), updated incrementally, **O(1) per event regardless of α or W** — this O(1) property is what makes clear, in the paper, that Mechanism B's cost is not what causes backpressure (Decision 2's justification depends on this being stated precisely): the EMA recursion itself is cheap at any α; what costs `O(W)` is the *publish* step in `ScoringFlushOp`, not the *update* step in `KeyedFeatureExtractOp`.

```
engagement_weight(behavior) = { pv: 1.0, fav: 2.0, cart: 3.0, buy: 5.0 }
ema_engagement[u]  ← α[n]·engagement_weight(behavior) + (1−α[n])·ema_engagement[u]
raw_pv_count[u]    ← raw_pv_count[u] + 1{behavior == pv}      (lifetime exact counter, O(1), never approximated)
raw_cart_count[u]  ← raw_cart_count[u] + 1{behavior == cart}
raw_fav_count[u]   ← raw_fav_count[u] + 1{behavior == fav}
prev_event_ts[u]   ← current event's timestamp (after computing recency from the OLD value)
```

### 10.3 The Feature Vector Sent to `ScoringFlushOp` (D = 4, Matching Project 2's "Order Matters, Documented" Convention)

```
FeatureSnapshot.x = [
    ema_engagement,                                  // continuous, α-controlled — Mechanism B's output
    log1p(raw_pv_count[u]),                          // exact lifetime signal, log-scaled (cf. Project 2's volume feature)
    log1p(raw_cart_count[u] + raw_fav_count[u]),      // exact lifetime "intent" signal, log-scaled
    clip(recency_sec, 0, 3600) / 3600.0               // exact, normalized time-since-previous-event, never approximated
]
```

Only `ema_engagement` is subject to approximation under load (via α); the other three are always exact, O(1) counters — this asymmetry is deliberate and should be stated in the paper: it isolates the *one* feature whose information content genuinely degrades under the controller's action, making the regret analysis (Section 25) interpretable as "regret attributable to this one feature's staleness/smoothing," not a diffuse, hard-to-attribute mix.

### 10.4 Staleness, Logged but Not Fed to the Model

```
staleness_at_publish[u] = (event_ts_ns_at_publish − last_publish_ts_ns[u]) / 1e9   (seconds)
```

Logged by `ScoringFlushOp` alongside every `ScoredResult` (Section 19), used purely for evaluation (Sections 25–26) — deliberately **not** included as a model input feature, since feeding "how stale am I" into the classifier itself would be an unusual and confounding design choice that RALF's own evaluation does not make either.

### 10.5 ULB Secondary Dataset — Degenerate Single-Key Case

Identical pipeline, identical operator code, with every event's `user_id` (the `Event.key` field) set to a constant `0`. `engagement_weight` is replaced by `Amount` itself (or `log1p(Amount)`); `raw_pv_count`/`raw_cart_count`/`raw_fav_count` collapse to a single rolling transaction counter; the label is `Class` (already provided, no forward-looking construction needed). No new operator code is required — this is the value of the keyed design: a global aggregate is just the `N_USERS = 1` special case (Section 13.4 states this precisely for the implementer).

---

## 11. Python Offline Preprocessing Pipeline

One script per dataset, both producing the same replay CSV schema so `BehaviorSource` (Section 18) has a single code path regardless of which dataset is active.

```python
# preprocessing/preprocess_taobao.py
"""
Reads the raw Taobao UserBehavior.csv, subsamples to N_USERS, computes the
forward-looking label (Section 10.1), tags burst periods, and writes
data/replay/replay_taobao_<n_users>.csv with the schema BehaviorSource expects.

Usage:
    python preprocess_taobao.py --raw data/raw/UserBehavior.csv \
        --n-users 10000 --horizon 5 --out data/replay/replay_taobao_10k.csv
"""
import argparse
import numpy as np
import pandas as pd

BEHAVIOR_CODE = {"pv": 0, "cart": 1, "fav": 2, "buy": 3}

def load_and_subsample(raw_path: str, n_users: int, seed: int = 42) -> pd.DataFrame:
    cols = ["user_id", "item_id", "category_id", "behavior_type", "timestamp"]
    df = pd.read_csv(raw_path, names=cols, header=None)
    rng = np.random.default_rng(seed)
    all_users = df["user_id"].unique()
    chosen = rng.choice(all_users, size=min(n_users, len(all_users)), replace=False)
    df = df[df["user_id"].isin(chosen)].copy()
    df.sort_values(["user_id", "timestamp"], inplace=True, kind="mergesort")
    df.reset_index(drop=True, inplace=True)
    return df

def compute_forward_label(df: pd.DataFrame, horizon: int) -> pd.Series:
    """label[i] = 1 if a 'buy' occurs within `horizon` of this user's FUTURE events."""
    labels = np.zeros(len(df), dtype=np.uint8)
    valid = np.ones(len(df), dtype=bool)   # False for the trailing H events of each user
    for _, idx in df.groupby("user_id").groups.items():
        idx = list(idx)
        is_buy = (df.loc[idx, "behavior_type"] == "buy").to_numpy()
        n = len(idx)
        for i in range(n):
            window_end = min(i + horizon, n - 1)
            if i + horizon >= n:
                valid[idx[i]] = False
                continue
            labels[idx[i]] = int(is_buy[i + 1: window_end + 1].any())
    return pd.Series(labels, index=df.index), pd.Series(valid, index=df.index)

def tag_bursts(df: pd.DataFrame, bucket_seconds: int = 60,
                burst_percentile: float = 90.0) -> pd.Series:
    """Identify naturally bursty intervals from the real arrival-rate time series
    (Section 9.1's preference for real over synthetic bursts where possible)."""
    bucket = df["timestamp"] // bucket_seconds
    rate_per_bucket = bucket.value_counts()
    threshold = np.percentile(rate_per_bucket.values, burst_percentile)
    burst_buckets = set(rate_per_bucket[rate_per_bucket >= threshold].index)
    return bucket.isin(burst_buckets).astype(np.uint8)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--n-users", type=int, default=10000)
    ap.add_argument("--horizon", type=int, default=5)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    df = load_and_subsample(args.raw, args.n_users)
    labels, valid = compute_forward_label(df, args.horizon)
    df["label"] = labels
    df["label_valid"] = valid.astype(np.uint8)
    df["is_burst_period"] = tag_bursts(df)
    df["behavior_code"] = df["behavior_type"].map(BEHAVIOR_CODE).astype(np.uint8)
    df["seq"] = np.arange(len(df), dtype=np.uint64)
    df["timestamp_ns"] = (df["timestamp"].astype(np.int64) * 1_000_000_000)

    out_cols = ["seq", "timestamp_ns", "user_id", "item_id", "category_id",
                "behavior_code", "label", "label_valid", "is_burst_period"]
    df[out_cols].to_csv(args.out, index=False)
    print(f"wrote {len(df)} rows, {df['label'].sum()} positive labels "
          f"({100*df['label'].mean():.3f}%), {df['is_burst_period'].sum()} burst-tagged rows")

if __name__ == "__main__":
    main()
```

```python
# preprocessing/preprocess_ulb.py
"""
Reads creditcard.csv, builds the degenerate single-key (user_id=0) replay
stream for the secondary/generalization dataset (Section 9.2, 10.5).
"""
import argparse
import numpy as np
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.raw)
    df.sort_values("Time", inplace=True, kind="mergesort")
    df.reset_index(drop=True, inplace=True)

    df["seq"] = np.arange(len(df), dtype=np.uint64)
    df["timestamp_ns"] = (df["Time"].astype(np.int64) * 1_000_000_000)
    df["user_id"] = 0                      # degenerate single key — Section 10.5
    df["item_id"] = 0
    df["category_id"] = 0
    df["behavior_code"] = 0                # reinterpreted as "transaction" — only one type here
    df["amount"] = df["Amount"]
    df["label"] = df["Class"].astype(np.uint8)
    df["label_valid"] = 1
    # Burst tagging by transaction-rate percentile, identical method to Taobao's.
    bucket = (df["Time"] // 60).astype(np.int64)
    rate = bucket.value_counts()
    thresh = np.percentile(rate.values, 90.0)
    burst_buckets = set(rate[rate >= thresh].index)
    df["is_burst_period"] = bucket.isin(burst_buckets).astype(np.uint8)

    out_cols = ["seq", "timestamp_ns", "user_id", "item_id", "category_id",
                "behavior_code", "amount", "label", "label_valid", "is_burst_period"]
    df[out_cols].to_csv(args.out, index=False)
    print(f"wrote {len(df)} rows, {df['label'].sum()} positive (fraud) labels "
          f"({100*df['label'].mean():.4f}%)")

if __name__ == "__main__":
    main()
```

Note the schema difference (`amount` column present only for the ULB output) — `BehaviorSource` (Section 18) handles both via a `--dataset {taobao,ulb}` flag that selects which column layout to parse, rather than forcing a single artificial schema across two genuinely different datasets.

---

## 12. New KLStream Types

```cpp
// include/klstream/feature/types.hpp
#pragma once
#include <array>
#include <atomic>
#include <cstdint>
#include <type_traits>

namespace klstream {

// ── RawBehaviorEvent ─────────────────────────────────────────────────────
// One row from the replay CSV (Section 11). `user_id` is duplicated into
// the payload (in addition to living in Event::key — Section 1's note on
// reusing the existing key field for grouping) purely for convenience in
// ResultSink's CSV logging without threading the key through separately.
// behavior_code: 0=pv, 1=cart, 2=fav, 3=buy (Section 11's BEHAVIOR_CODE map).
// For the ULB secondary dataset, `amount` is populated and behavior_code is
// always 0 (Section 10.5) — `KeyedFeatureExtractOp` branches on a
// compile-time/runtime `DatasetMode` flag (Section 13.4), not on inspecting
// which fields happen to be nonzero.
struct RawBehaviorEvent {
    std::uint32_t user_id;
    std::uint32_t item_id;
    std::uint16_t category_id;
    std::uint8_t  behavior_code;
    float         amount;        // 0 for Taobao; transaction Amount for ULB
};
static_assert(std::is_trivially_copyable_v<RawBehaviorEvent>);

// ── FeatureSnapshot ───────────────────────────────────────────────────────
// Emitted by KeyedFeatureExtractOp once per raw event (Section 13). D=4,
// matching Section 10.3's feature table exactly — order matters, must match
// the column order ScoringFlushOp's native dot product expects (Section 17)
// and the order train_classifier.py (Section 20) exports weights in.
struct FeatureSnapshot {
    std::uint32_t user_id;
    float         x[4];           // ema_engagement, log_pv, log_cart_fav, recency_norm
    float         alpha_used;     // the alpha[n] Mechanism B used for THIS event — logged for Sec. 24's analysis
    std::uint8_t  label;          // ground-truth label, carried through for offline evaluation only
    std::uint8_t  label_valid;    // 0 for the trailing H events of each user (Section 10.1)

    static constexpr std::size_t kDim = 4;
};
static_assert(std::is_trivially_copyable_v<FeatureSnapshot>);

// ── FeatureBatch ──────────────────────────────────────────────────────────
// Fixed-capacity, trivially-copyable, exactly mirroring WindowBatch's
// rationale in KLStream_Research.md Section 7.3 (SPSCQueue<T> requires
// std::is_trivially_copyable_v<T>; a std::vector cannot cross the queue
// boundary). MAX_FEATURE_BATCH caps every window strategy's upper bound.
inline constexpr std::size_t MAX_FEATURE_BATCH = 256;

struct FeatureBatch {
    std::array<FeatureSnapshot, MAX_FEATURE_BATCH> items{};
    std::uint32_t count = 0;
    std::uint64_t first_seq = 0;
    std::uint64_t last_seq  = 0;

    void push_back(const FeatureSnapshot& fs, std::uint64_t seq) {
        if (count == 0) first_seq = seq;
        items[count++] = fs;
        last_seq = seq;
    }
    bool full(std::size_t target_size) const { return count >= target_size; }
};
static_assert(std::is_trivially_copyable_v<FeatureBatch>);

// ── ScoredResult ──────────────────────────────────────────────────────────
// Emitted by ScoringFlushOp (Section 17), consumed by ResultSink (Section 19).
struct ScoredResult {
    std::uint32_t user_id;
    double        score              = 0.0;   // sigmoid output, P(buy within H)
    std::uint8_t  label              = 0;
    std::uint8_t  label_valid        = 0;
    std::uint32_t window_size_used   = 0;      // W for the batch this came from
    float         alpha_used         = 0.0f;   // alpha[n] at the moment this snapshot was computed
    float         staleness_sec      = 0.0f;   // Section 10.4 — time since this user's last publish
    float         occupancy_at_decision = 0.0f; // EMA reading at window-start; 0 for non-adaptive variants
};
static_assert(std::is_trivially_copyable_v<ScoredResult>);

// ── BackpressureSignal ───────────────────────────────────────────────────
// The shared publish point between AdaptiveFeatureWindowOp (writer, Section
// 14) and KeyedFeatureExtractOp (reader, Section 13) — Section 8.3's
// ownership rule: AdaptiveFeatureWindowOp publishes, KeyedFeatureExtractOp
// only ever reads. relaxed ordering is sufficient and deliberate: this is a
// soft, slowly-varying control signal, not a correctness-critical value —
// same justification style used for SPSCQueue::occupancy()'s relaxed loads
// (Implementation Guide Section 7.3).
//
// For the three non-adaptive architectures (Fixed, DriftAdaptive,
// RateThrottle), no AdaptiveFeatureWindowOp instance exists to write to
// this struct, so it is constructed once with a fixed value and never
// updated — KeyedFeatureExtractOp reads a constant 0.0, and Mechanism B's
// formula (Section 7.2) collapses to a fixed alpha_min for those three
// architectures, exactly as Decision 3's "baselines have fixed alpha"
// design states.
struct BackpressureSignal {
    std::atomic<double> ema_occupancy{0.0};
};

} // namespace klstream
```

---

## 13. `KeyedFeatureExtractOp` — Per-Key State and the Continuous α-Control Path

### 13.1 Per-User State (Internal — Never Crosses a Queue, No Trivial-Copyability Requirement)

```cpp
// include/klstream/feature/user_state.hpp
#pragma once
#include <cstdint>

namespace klstream {

struct EMAUserState {
    float         ema_engagement   = 0.0f;
    std::uint32_t raw_pv_count     = 0;
    std::uint32_t raw_cart_count   = 0;
    std::uint32_t raw_fav_count    = 0;
    std::uint64_t prev_event_ts_ns = 0;     // 0 = no prior event seen yet
    std::uint64_t last_publish_ts_ns = 0;   // 0 = never published — Section 10.4
    bool          initialized      = false;
};

} // namespace klstream
```

### 13.2 Engagement Weight Table

```cpp
// include/klstream/feature/engagement.hpp
#pragma once
#include <array>
#include <cstdint>

namespace klstream {
// Index by behavior_code (Section 12's RawBehaviorEvent: 0=pv,1=cart,2=fav,3=buy).
inline constexpr std::array<float, 4> ENGAGEMENT_WEIGHT = { 1.0f, 3.0f, 2.0f, 5.0f };
}
```

### 13.3 `KeyedFeatureExtractOp`

```cpp
// include/klstream/feature/keyed_feature_extract_op.hpp
#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "types.hpp"
#include "user_state.hpp"
#include "engagement.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <unordered_map>

namespace klstream {

// Cap on distinct keys tracked at once. Section 9.1 recommends preprocessing
// at most a few tens of thousands of distinct users — keep this comfortably
// above that (no eviction policy is implemented; if this cap is hit it is a
// MISCONFIGURATION of the preprocessing N_USERS parameter, not a runtime
// condition this operator needs to handle gracefully — assert and fail loud
// rather than silently dropping users, which would silently bias results).
inline constexpr std::size_t MAX_TRACKED_USERS = 65536;

// Mechanism B's control law (Section 7.2) — the sign-flipped sibling of
// Project 1's Section 1.2/1.3 law. Pure function, unit-testable in
// isolation exactly like AdaptiveWindowController (Section 14's pattern).
class AlphaController {
public:
    AlphaController(double alpha_min, double alpha_max, double d_alpha_max)
        : alpha_min_(alpha_min), alpha_max_(alpha_max), d_alpha_max_(d_alpha_max)
        , current_alpha_(alpha_min)   // start calm: assume long memory until proven otherwise
    {}

    double update(double ema_occupancy) {
        double target = alpha_min_ + (alpha_max_ - alpha_min_) * ema_occupancy;
        double delta = std::clamp(target - current_alpha_, -d_alpha_max_, d_alpha_max_);
        current_alpha_ += delta;
        return current_alpha_;
    }

    double current() const { return current_alpha_; }

private:
    double alpha_min_, alpha_max_, d_alpha_max_;
    double current_alpha_;
};

class KeyedFeatureExtractOp : public IOperator {
public:
    using InQueue  = SPSCQueue<Event<RawBehaviorEvent>>;
    using OutQueue = SPSCQueue<Event<FeatureSnapshot>>;

    // `signal` is nullptr for the three non-adaptive architectures (Section
    // 12's BackpressureSignal doc comment) — in that case alpha is held
    // fixed at alpha_min for the whole run (Decision 3's "baselines have
    // fixed alpha" rule), implemented below by skipping the controller
    // entirely rather than constructing one that always reads zero (more
    // explicit, avoids relying on a default EMA-occupancy-of-zero
    // coincidentally producing the right fixed value).
    KeyedFeatureExtractOp(std::string name, InQueue* input, OutQueue* output,
                          const BackpressureSignal* signal,   // nullptr => fixed alpha
                          double fixed_alpha = 0.10,
                          double alpha_min = 0.02, double alpha_max = 0.30,
                          double d_alpha_max = 0.01)
        : IOperator(std::move(name))
        , input_(input), output_(output), signal_(signal)
        , fixed_alpha_(fixed_alpha)
        , controller_(signal ? AlphaController(alpha_min, alpha_max, d_alpha_max)
                              : AlphaController(fixed_alpha, fixed_alpha, 0.0))
    {
        users_.reserve(MAX_TRACKED_USERS);
    }

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }
    double last_alpha() const { return controller_.current(); }

    OpStatus tick() override {
        if (has_pending_) {
            if (output_->try_push(pending_)) {
                has_pending_ = false;
                if (metrics_) metrics_->events_processed.increment();
                return OpStatus::Processed;
            }
            if (metrics_) metrics_->events_blocked.increment();
            return OpStatus::Blocked;
        }

        Event<RawBehaviorEvent> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        // ── Mechanism B: one alpha update per raw event, regardless of key.
        // Section 8.3: this operator only READS the shared signal, never
        // writes it. relaxed load is intentional (BackpressureSignal's
        // doc comment, Section 12).
        double occ = signal_ ? signal_->ema_occupancy.load(std::memory_order_relaxed) : 0.0;
        double alpha = controller_.update(occ);

        // ── Per-key state lookup/insert. assert rather than silently evict
        // (Section 13.3's MAX_TRACKED_USERS comment).
        auto [it, inserted] = users_.try_emplace(in_ev.data.user_id);
        if (inserted) {
            if (users_.size() > MAX_TRACKED_USERS) {
                throw std::runtime_error(
                    "KeyedFeatureExtractOp: MAX_TRACKED_USERS exceeded — "
                    "reduce --n-users in preprocessing (Section 9.1) or raise "
                    "MAX_TRACKED_USERS deliberately and re-measure memory.");
            }
        }
        EMAUserState& st = it->second;

        const RawBehaviorEvent& raw = in_ev.data;
        float weight = ENGAGEMENT_WEIGHT[raw.behavior_code];
        if (raw.amount > 0.0f) weight = raw.amount;   // ULB secondary mode, Section 10.5

        st.ema_engagement = static_cast<float>(alpha) * weight
                           + static_cast<float>(1.0 - alpha) * st.ema_engagement;
        if (raw.behavior_code == 0) ++st.raw_pv_count;
        else if (raw.behavior_code == 1) ++st.raw_cart_count;
        else if (raw.behavior_code == 2) ++st.raw_fav_count;

        float recency_sec = st.initialized
            ? static_cast<float>(in_ev.timestamp_ns - st.prev_event_ts_ns) / 1e9f
            : 0.0f;
        float recency_norm = std::clamp(recency_sec, 0.0f, 3600.0f) / 3600.0f;

        float staleness_sec = st.last_publish_ts_ns > 0
            ? static_cast<float>(in_ev.timestamp_ns - st.last_publish_ts_ns) / 1e9f
            : 0.0f;
        (void)staleness_sec; // logged downstream from ScoringFlushOp's own
                              // copy of last_publish_ts (Section 17) — kept
                              // here only as the source of truth this
                              // operator updates; not re-emitted twice.

        FeatureSnapshot fs{};
        fs.user_id = raw.user_id;
        fs.x[0] = st.ema_engagement;
        fs.x[1] = std::log1p(static_cast<float>(st.raw_pv_count));
        fs.x[2] = std::log1p(static_cast<float>(st.raw_cart_count + st.raw_fav_count));
        fs.x[3] = recency_norm;
        fs.alpha_used = static_cast<float>(alpha);
        fs.label = in_ev.data.behavior_code; // placeholder overwritten below if label fields present
        fs.label_valid = 0;

        st.prev_event_ts_ns = in_ev.timestamp_ns;
        st.initialized = true;

        Event<FeatureSnapshot> out_ev;
        out_ev.timestamp_ns = in_ev.timestamp_ns;
        out_ev.key  = in_ev.key;     // user_id, propagated for downstream grouping
        out_ev.seq  = in_ev.seq;
        out_ev.data = fs;

        if (output_->try_push(out_ev)) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }
        pending_     = out_ev;
        has_pending_ = true;
        if (metrics_) metrics_->events_blocked.increment();
        return OpStatus::Blocked;
    }

private:
    InQueue*    input_;
    OutQueue*   output_;
    const BackpressureSignal* signal_;
    double      fixed_alpha_;
    AlphaController controller_;
    std::unordered_map<std::uint32_t, EMAUserState> users_;
    Event<FeatureSnapshot> pending_{};
    bool        has_pending_{false};
    OperatorMetrics* metrics_{nullptr};
};

} // namespace klstream
```

**Implementation note for the agent:** the label/label_valid fields on `FeatureSnapshot` must actually be populated from `RawBehaviorEvent`'s ground-truth columns (Section 11's CSV output), not left as the placeholder shown above — `RawBehaviorEvent` as defined in Section 12 intentionally does not carry `label`/`label_valid` (keeping the queue payload that crosses the hot path free of evaluation-only fields, exactly mirroring Project 2's `WindowBatch`/`DetectionResult` separation). Extend `BehaviorSource` (Section 18) to carry label/label_valid alongside the `Event<RawBehaviorEvent>` via a **parallel, index-aligned `std::vector<std::pair<uint8_t,uint8_t>>` looked up by `seq`** inside `KeyedFeatureExtractOp`, rather than widening `RawBehaviorEvent` itself — this keeps the trivially-copyable queue payload minimal while still making ground truth available where it is needed (`ScoringFlushOp`'s output, Section 17, for offline evaluation only).

### 13.4 The ULB Degenerate Single-Key Case, Stated Precisely

When `--dataset ulb` is active, every `RawBehaviorEvent.user_id = 0` (Section 9.2/10.5's "user_id=0 for every event"). `users_.try_emplace(0)` then always returns the same single `EMAUserState` — the hash map degenerates to a single entry, and the per-key code above is exercised with key cardinality 1 instead of thousands. No branch in `KeyedFeatureExtractOp` needs to know which dataset is active; the only dataset-specific logic is the `raw.amount > 0.0f` check already shown (using transaction amount as the engagement weight instead of the fixed `ENGAGEMENT_WEIGHT` table) and `preprocessing/preprocess_ulb.py`'s schema (Section 11).

---

## 14. `AdaptiveFeatureWindowOp` and `BPFeatController` — The Core Contribution

This is the operator the paper's headline claim is about. It reuses `EMAOccupancyTracker<Queue>` from `klstream/core/backpressure.hpp` **completely unmodified** — exactly the framing Project 2's `AdaptiveWindowOp` used for the same class, and exactly as important to state plainly here: the novelty is in what reads the tracker and what two things it does with the reading (Mechanism A locally, Mechanism B via the published `BackpressureSignal`), not in the tracker itself.

```cpp
// include/klstream/feature/adaptive_feature_window_op.hpp
#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "../core/backpressure.hpp"   // EMAOccupancyTracker — reused as-is
#include "types.hpp"
#include <algorithm>
#include <cstdint>

namespace klstream {

// ── BPFeatController ─────────────────────────────────────────────────────
// Pure control logic for the discrete actuator (Mechanism A), separated
// from the operator so it can be unit-tested without any queue/threading
// machinery — same separation Project 2's AdaptiveWindowController used,
// for the same reason (Section 27 covers testing this in isolation with
// synthetic occupancy traces). The asymmetric shrink-fast/grow-slow update
// is the same AIMD shape as Project 2's controller, reused with identical
// default constants for cross-project comparability (Section 2, Decision 3).
class BPFeatController {
public:
    BPFeatController(std::uint32_t w_min, std::uint32_t w_max,
                     double occ_low, double occ_high,
                     double shrink_factor = 0.70,
                     double grow_factor   = 1.15)
        : w_min_(w_min), w_max_(w_max)
        , occ_low_(occ_low), occ_high_(occ_high)
        , shrink_factor_(shrink_factor), grow_factor_(grow_factor)
        , current_w_(w_max)
    {}

    // Called once per window START (the operator's tick() logic below
    // captures this once and holds it for the whole window's fill
    // duration — never mid-window, identical rule to Project 2's Section
    // 7.2 "shrink for FUTURE windows only").
    std::uint32_t update(double ema_occupancy) {
        if (ema_occupancy > occ_high_) {
            current_w_ = std::max(w_min_,
                static_cast<std::uint32_t>(current_w_ * shrink_factor_));
            ++shrink_events_;
        } else if (ema_occupancy < occ_low_) {
            current_w_ = std::min(w_max_,
                static_cast<std::uint32_t>(current_w_ * grow_factor_));
            ++grow_events_;
        }
        track_direction(ema_occupancy);
        return current_w_;
    }

    std::uint32_t current() const { return current_w_; }
    std::uint64_t direction_changes() const { return direction_changes_; }   // Section 25.2's WOR

private:
    void track_direction(double ema_occupancy) {
        int dir = 0;
        if (ema_occupancy > occ_high_) dir = -1;
        else if (ema_occupancy < occ_low_) dir = 1;
        else return;
        if (last_dir_ != 0 && dir != last_dir_) ++direction_changes_;
        last_dir_ = dir;
    }

    std::uint32_t w_min_, w_max_;
    double        occ_low_, occ_high_;
    double        shrink_factor_, grow_factor_;
    std::uint32_t current_w_;
    std::uint64_t shrink_events_{0};
    std::uint64_t grow_events_{0};
    std::uint64_t direction_changes_{0};
    int           last_dir_{0};
};

// ── AdaptiveFeatureWindowOp ────────────────────────────────────────────────
// Implements the IOperator interface (Section 7.5 of the Implementation
// Guide) — same tick()/OpStatus contract as every other KLStream operator.
// Constructed with a pointer to the BackpressureSignal it OWNS and PUBLISHES
// to (Section 8.3, Section 12) — KeyedFeatureExtractOp upstream holds the
// same pointer as a READER only.
class AdaptiveFeatureWindowOp : public IOperator {
public:
    using InQueue  = SPSCQueue<Event<FeatureSnapshot>>;
    using OutQueue = SPSCQueue<Event<FeatureBatch>>;

    AdaptiveFeatureWindowOp(std::string name, InQueue* input, OutQueue* output,
                            BackpressureSignal* signal,
                            std::uint32_t w_min = 8, std::uint32_t w_max = MAX_FEATURE_BATCH,
                            double occ_low = 0.30, double occ_high = 0.70)
        : IOperator(std::move(name))
        , input_(input), output_(output), signal_(signal)
        , controller_(w_min, w_max, occ_low, occ_high)
        , tracker_(*output)   // reads occupancy of ITS OWN output queue —
                                // the load-bearing line, see Section 8.2
    {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }
    const BPFeatController& controller() const { return controller_; }

    OpStatus tick() override {
        if (has_pending_) {
            if (output_->try_push(pending_)) {
                has_pending_ = false;
                if (metrics_) metrics_->events_processed.increment();
                return OpStatus::Processed;
            }
            if (metrics_) metrics_->events_blocked.increment();
            return OpStatus::Blocked;
        }

        // At the START of a new window, capture this window's target size
        // ONCE, and publish the fresh EMA reading for Mechanism B's
        // consumers (Section 13) — both happen together, from the same
        // tracker.update() call, so the two mechanisms are always reacting
        // to the literal same instant's reading, never a stale copy from
        // a different tick.
        if (buffer_.count == 0) {
            tracker_.update();
            double occ = tracker_.ema();
            target_w_ = controller_.update(occ);
            signal_->ema_occupancy.store(occ, std::memory_order_relaxed);
        }

        Event<FeatureSnapshot> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        buffer_.push_back(in_ev.data, in_ev.seq);

        if (!buffer_.full(target_w_)) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }

        Event<FeatureBatch> out_ev;
        out_ev.timestamp_ns = in_ev.timestamp_ns;
        out_ev.key  = 0;
        out_ev.seq  = in_ev.seq;
        out_ev.data = buffer_;
        buffer_ = FeatureBatch{};   // reset for next window

        if (output_->try_push(out_ev)) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }
        pending_     = out_ev;
        has_pending_ = true;
        if (metrics_) metrics_->events_blocked.increment();
        return OpStatus::Blocked;
    }

private:
    InQueue*                       input_;
    OutQueue*                      output_;
    BackpressureSignal*            signal_;
    BPFeatController                controller_;
    EMAOccupancyTracker<OutQueue>  tracker_;
    FeatureBatch                   buffer_{};
    std::uint32_t                  target_w_{0};
    Event<FeatureBatch>            pending_{};
    bool                            has_pending_{false};
    OperatorMetrics*               metrics_{nullptr};
};

} // namespace klstream
```

### 14.1 Recommended Default Thresholds

| Parameter | Default | Rationale |
|---|---|---|
| `w_min` | 8 | Small enough to meaningfully cut per-window scoring cost; large enough that `ScoringFlushOp` still amortizes a non-trivial batch |
| `w_max` | 256 | Equals `MAX_FEATURE_BATCH` — uses the full compile-time budget when calm |
| `occ_low` | 0.30 | Reuses Project 2's exact default — below this, `ScoringFlushOp` is comfortably keeping up |
| `occ_high` | 0.70 | Reuses Project 2's exact default and `BP_SOFT_THRESHOLD` |
| `shrink_factor` | 0.70 | Reused unmodified from Project 2 — cross-project comparability is itself a result worth reporting (do the same AIMD constants behave similarly in a different domain?) |
| `grow_factor` | 1.15 | Reused unmodified from Project 2 |
| `alpha_min` | 0.02 | Identical numeric value to Project 1, opposite role (Section 7.2) — calm-state memory ≈ 99 events |
| `alpha_max` | 0.30 | Identical numeric value to Project 1, opposite role — stressed-state memory ≈ 5.7 events |
| `d_alpha_max` | 0.01/event | Identical numeric value to Project 1's slew-rate bound |

Reusing every numeric default from Projects 1 and 2 unmodified, rather than re-tuning them for this new domain, is a deliberate choice: it makes "do the same constants generalize" a clean, explicit, falsifiable part of Experiment 4's sensitivity sweep (Section 27), rather than a hidden confound from silently re-tuning.

---

## 15. `FixedWindowOp` (Reused) and `DriftAdaptiveWindowOp` (Literature Baseline)

### 15.1 `FixedWindowOp` — Reusing Existing KLStream Code

`TumblingCountWindow<T, Out>` (Implementation Guide Section 8.5) is reused **unmodified** as the static baseline, instantiated as `TumblingCountWindow<FeatureSnapshot, FeatureBatch>` with `window_size_ = 128` (the midpoint of `w_min`/`w_max`, matching Project 2's `FixedWindowOp` baseline precedent exactly) and an aggregation function that simply folds the buffered `FeatureSnapshot`s into a `FeatureBatch`:

```cpp
auto aggr = [](const std::vector<FeatureSnapshot>& buf) -> FeatureBatch {
    FeatureBatch fb{};
    for (std::size_t i = 0; i < buf.size(); ++i) fb.push_back(buf[i], /*seq placeholder*/ i);
    return fb;
};
TumblingCountWindow<FeatureSnapshot, FeatureBatch> fixed_window(
    "fixed_window_128", &q_feat, &q_batch, /*window_size=*/128, aggr);
```

(The wiring in Section 23 fills in `seq` correctly from the actual `Event<FeatureSnapshot>::seq`, not the placeholder index shown above — `TumblingCountWindow`'s aggregation function signature only receives the buffered payloads, not their original `Event` wrappers, so `first_seq`/`last_seq` are reconstructed from the surrounding `Event<Out>` fields the same way `TumblingCountWindow::tick()` already does internally; see Implementation Guide Section 8.5's `out_ev.seq = in_ev.seq` line for the pattern.)

### 15.2 `DriftAdaptiveWindowOp` — The Literature-Style Baseline

Implements Decision 6's scoped two-timescale EMA-crossover drift detector: a fast EMA and a slow EMA of per-event engagement weight (Section 13's `ENGAGEMENT_WEIGHT`), shrinking the window when they diverge (signaling a behavior-pattern shift — e.g., a flash-sale-like surge in `buy`/`cart` events) and growing it when stable. Driven entirely by the **input data's** statistics; reads no queue-occupancy signal at all, which is the one property that must hold for this to be a fair "signal-driven, not load-driven" baseline.

```cpp
// include/klstream/feature/drift_adaptive_window_op.hpp
#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "types.hpp"
#include "engagement.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace klstream {

// Decision 6: a simplified two-EMA crossover detector, NOT full ADWIN —
// scoped deliberately (see Section 2). The detector statistic is the
// relative gap between a fast EMA (alpha_fast) and a slow EMA (alpha_slow)
// of per-event engagement weight; when the gap exceeds drift_threshold,
// a "drift" is declared and the window shrinks (capture the regime change
// in a smaller, more timely batch); otherwise it grows (amortize cost
// while the input statistics are stable).
class DriftAdaptiveWindowOp : public IOperator {
public:
    using InQueue  = SPSCQueue<Event<FeatureSnapshot>>;
    using OutQueue = SPSCQueue<Event<FeatureBatch>>;

    DriftAdaptiveWindowOp(std::string name, InQueue* input, OutQueue* output,
                          std::uint32_t w_min = 8, std::uint32_t w_max = MAX_FEATURE_BATCH,
                          double alpha_fast = 0.30, double alpha_slow = 0.02,
                          double drift_threshold = 0.50,
                          double shrink_factor = 0.70, double grow_factor = 1.15)
        : IOperator(std::move(name))
        , input_(input), output_(output)
        , w_min_(w_min), w_max_(w_max)
        , alpha_fast_(alpha_fast), alpha_slow_(alpha_slow)
        , drift_threshold_(drift_threshold)
        , shrink_factor_(shrink_factor), grow_factor_(grow_factor)
        , target_w_(w_max)
    {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }
    std::uint64_t direction_changes() const { return direction_changes_; }

    OpStatus tick() override {
        if (has_pending_) {
            if (output_->try_push(pending_)) {
                has_pending_ = false;
                if (metrics_) metrics_->events_processed.increment();
                return OpStatus::Processed;
            }
            if (metrics_) metrics_->events_blocked.increment();
            return OpStatus::Blocked;
        }

        Event<FeatureSnapshot> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }

        // Drift statistic: re-derive an "engagement-rate-like" scalar from
        // the already-computed ema_engagement feature (x[0]) rather than
        // re-reading the raw behavior code — this keeps the detector a
        // pure function of the FeatureSnapshot stream, with no dependency
        // on RawBehaviorEvent, matching the principle that EVERY window
        // strategy operates on the identical Event<FeatureSnapshot> type
        // (Section 8.1's table).
        float sample = in_ev.data.x[0];
        fast_ema_ = static_cast<float>(alpha_fast_) * sample + static_cast<float>(1.0 - alpha_fast_) * fast_ema_;
        slow_ema_ = static_cast<float>(alpha_slow_) * sample + static_cast<float>(1.0 - alpha_slow_) * slow_ema_;

        if (buffer_.count == 0) {
            double denom = std::max(1e-6, static_cast<double>(std::abs(slow_ema_)));
            double rel_gap = std::abs(static_cast<double>(fast_ema_) - static_cast<double>(slow_ema_)) / denom;
            int dir = 0;
            if (rel_gap > drift_threshold_) {
                target_w_ = std::max(w_min_, static_cast<std::uint32_t>(target_w_ * shrink_factor_));
                dir = -1;
            } else {
                target_w_ = std::min(w_max_, static_cast<std::uint32_t>(target_w_ * grow_factor_));
                dir = 1;
            }
            if (last_dir_ != 0 && dir != last_dir_) ++direction_changes_;
            last_dir_ = dir;
        }

        buffer_.push_back(in_ev.data, in_ev.seq);
        if (!buffer_.full(target_w_)) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }

        Event<FeatureBatch> out_ev;
        out_ev.timestamp_ns = in_ev.timestamp_ns;
        out_ev.key = 0;
        out_ev.seq = in_ev.seq;
        out_ev.data = buffer_;
        buffer_ = FeatureBatch{};

        if (output_->try_push(out_ev)) {
            if (metrics_) metrics_->events_processed.increment();
            return OpStatus::Processed;
        }
        pending_ = out_ev;
        has_pending_ = true;
        if (metrics_) metrics_->events_blocked.increment();
        return OpStatus::Blocked;
    }

private:
    InQueue*  input_;
    OutQueue* output_;
    std::uint32_t w_min_, w_max_;
    double    alpha_fast_, alpha_slow_, drift_threshold_;
    double    shrink_factor_, grow_factor_;
    float     fast_ema_{0.0f}, slow_ema_{0.0f};
    std::uint32_t target_w_;
    FeatureBatch  buffer_{};
    std::uint64_t direction_changes_{0};
    int           last_dir_{0};
    Event<FeatureBatch> pending_{};
    bool          has_pending_{false};
    OperatorMetrics* metrics_{nullptr};
};

} // namespace klstream
```

---

## 16. `RateThrottleSource` Wiring — The Admission-Control Baseline

No new operator code is required here — this is the point of Decision 7. Baseline 3 wires `BehaviorSource` (Section 18) with the **identical** `EMAOccupancyTracker<Queue>` + `TokenBucketRateLimiter` pair from `klstream/core/backpressure.hpp` (Implementation Guide Section 7.8), in the same configuration Project 2's original adaptive-backpressure extension used (Implementation Guide Section 14.1), and pairs it with the plain `FixedWindowOp` (Section 15.1, `W=128`, untouched) downstream:

```cpp
// Baseline 3 wiring sketch (full version in Section 23) — note this is
// SourceOperator-level admission control, structurally identical to Spark's
// PIDRateEstimator and Flink's credit-based flow control (Section 4.7):
// it throttles HOW FAST raw events enter the pipeline; it does not touch
// window size or alpha at all. Window-stage and KeyedFeatureExtractOp are
// wired exactly as in the Fixed baseline (alpha fixed, W fixed at 128).

klstream::EMAOccupancyTracker<klstream::SPSCQueue<klstream::Event<klstream::RawBehaviorEvent>>>
    admission_tracker(q_raw, /*alpha=*/0.10);
klstream::TokenBucketRateLimiter limiter(/*tokens_per_sec=*/100000.0, /*max_burst=*/5000.0);

// Inside BehaviorSource::tick() (Section 18), before emitting each row:
admission_tracker.update();
if (admission_tracker.soft_pressure()) {
    limiter.set_rate(limiter.rate() * 0.85);   // gradually slow down — same
                                                 // policy shape as Implementation
                                                 // Guide Section 14.1
} else {
    limiter.set_rate(std::min(100000.0, limiter.rate() * 1.05));
}
if (!limiter.try_consume()) { return OpStatus::Idle; }   // skip emitting this tick
```

This baseline answers, empirically rather than only textually, "what happens if you address backpressure the way production systems already do, leaving feature freshness/window semantics untouched?" — directly operationalizing the Related Work comparison against Spark/Flink (Section 4.7) inside the same codebase and the same experiment runs as the other three architectures, rather than as a citation with no empirical counterpart.

---

## 17. `ScoringFlushOp` — The O(W) Cost Engine

This operator is where the causal chain's cost actually lives (Section 8.2, steps 1–3). It pops one `Event<FeatureBatch>` per `tick()` and, in a tight loop, runs the native logistic-regression dot product over every snapshot in the batch — directly structurally analogous to `InferenceOp`'s Isolation-Forest scoring loop in Project 2 (`KLStream_Research.md` Section 17), with the per-item cost function swapped.

```cpp
// include/klstream/feature/scoring_flush_op.hpp
#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "../model/logistic_model.hpp"
#include "types.hpp"
#include <cmath>
#include <unordered_map>

namespace klstream {

class ScoringFlushOp : public IOperator {
public:
    using InQueue  = SPSCQueue<Event<FeatureBatch>>;
    using OutQueue = SPSCQueue<Event<ScoredResult>>;

    ScoringFlushOp(std::string name, InQueue* input, OutQueue* output,
                   const LogisticModel* model)
        : IOperator(std::move(name))
        , input_(input), output_(output), model_(model)
    {}

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }

    OpStatus tick() override {
        if (has_pending_idx_ < pending_batch_.count) {
            // Resume flushing a partially-pushed batch (Blocked-recovery,
            // generalizing the single-pending-event pattern used elsewhere
            // in KLStream to a multi-item flush — see the note below).
            return flush_from(has_pending_idx_);
        }

        Event<FeatureBatch> in_ev;
        if (!input_->try_pop(&in_ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }
        last_batch_window_size_ = in_ev.data.count;
        last_batch_timestamp_   = in_ev.timestamp_ns;
        pending_batch_ = in_ev.data;
        return flush_from(0);
    }

private:
    // ── The O(W) hot loop — Section 8.2's causal mechanism ───────────────
    OpStatus flush_from(std::uint32_t start_idx) {
        for (std::uint32_t i = start_idx; i < pending_batch_.count; ++i) {
            const FeatureSnapshot& fs = pending_batch_.items[i];
            double z = model_->bias;
            for (std::size_t d = 0; d < FeatureSnapshot::kDim; ++d) {
                z += model_->weights[d] * static_cast<double>(fs.x[d]);
            }
            double score = 1.0 / (1.0 + std::exp(-z));   // sigmoid

            float staleness = 0.0f;
            auto it = last_publish_ts_.find(fs.user_id);
            if (it != last_publish_ts_.end()) {
                staleness = static_cast<float>(last_batch_timestamp_ - it->second) / 1e9f;
            }
            last_publish_ts_[fs.user_id] = last_batch_timestamp_;

            Event<ScoredResult> out_ev;
            out_ev.timestamp_ns = last_batch_timestamp_;
            out_ev.key  = fs.user_id;
            out_ev.seq  = pending_batch_.first_seq + i;
            out_ev.data = ScoredResult{
                fs.user_id, score, fs.label, fs.label_valid,
                last_batch_window_size_, fs.alpha_used, staleness,
                0.0f   // filled in by the wiring code for the Adaptive variant only (Section 23)
            };

            if (!output_->try_push(out_ev)) {
                has_pending_idx_ = i;   // remember where we stopped
                if (metrics_) metrics_->events_blocked.increment();
                return OpStatus::Blocked;
            }
        }
        has_pending_idx_ = pending_batch_.count;   // batch fully flushed
        if (metrics_) metrics_->events_processed.increment();
        return OpStatus::Processed;
    }

    InQueue*  input_;
    OutQueue* output_;
    const LogisticModel* model_;     // owned by main(), lives for the runtime's lifetime
    FeatureBatch  pending_batch_{};
    std::uint32_t has_pending_idx_{0};
    std::uint32_t last_batch_window_size_{0};
    std::uint64_t last_batch_timestamp_{0};
    std::unordered_map<std::uint32_t, std::uint64_t> last_publish_ts_;  // Section 10.4's staleness state
    OperatorMetrics* metrics_{nullptr};
};

} // namespace klstream
```

**Note on the multi-item Blocked-recovery pattern.** Every other operator in this document and in Project 2 only ever holds **one** pending `Event<Out>` across a `Blocked` return (the `pending_`/`has_pending_` idiom from Implementation Guide Section 8.5). `ScoringFlushOp` differs because one input batch fans out into up to `MAX_FEATURE_BATCH` output events — it must remember **which index** it stopped at, not just a single pending event, hence `has_pending_idx_` instead of a boolean. This is a genuine, intentional deviation from the standard idiom and should be called out as such in code review / in the paper's implementation notes, not silently treated as "the same pattern as everywhere else."

```cpp
// include/klstream/model/logistic_model.hpp
#pragma once
#include "../feature/types.hpp"
#include <array>
#include <fstream>
#include <stdexcept>

namespace klstream {

struct LogisticModel {
    double bias = 0.0;
    double weights[FeatureSnapshot::kDim] = {0.0, 0.0, 0.0, 0.0};

    // Loads the plain-text weight file exported by train_classifier.py
    // (Section 20) — format: one line "bias=<value>", then kDim lines
    // "w<i>=<value>", deliberately the simplest possible format (no JSON
    // parser dependency, no ONNX — Decision 5).
    static LogisticModel load(const std::string& path) {
        std::ifstream f(path);
        if (!f) throw std::runtime_error("cannot open model weights file: " + path);
        LogisticModel m;
        std::string key; char eq; double val;
        while (f >> key) {
            auto pos = key.find('=');
            std::string name = key.substr(0, pos);
            val = std::stod(key.substr(pos + 1));
            if (name == "bias") m.bias = val;
            else if (name.size() > 1 && name[0] == 'w') {
                std::size_t idx = std::stoul(name.substr(1));
                if (idx < FeatureSnapshot::kDim) m.weights[idx] = val;
            }
        }
        return m;
    }
};

} // namespace klstream
```

---

## 18. `BehaviorSource` — Replaying Taobao / ULB Data

```cpp
// include/klstream/feature/behavior_source.hpp
#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "types.hpp"
#include <chrono>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace klstream {

enum class DatasetMode { Taobao, ULB };
enum class ReplayMode  { PreserveTiming, MaxRate };   // identical semantics to
                                                        // FinancialTickSource
                                                        // (KLStream_Research.md
                                                        // Section 18)

struct BehaviorRow {
    std::uint64_t seq;
    std::uint64_t timestamp_ns;
    std::uint32_t user_id, item_id;
    std::uint16_t category_id;
    std::uint8_t  behavior_code;
    float         amount;            // 0 for Taobao
    std::uint8_t  label, label_valid;
    std::uint8_t  is_burst_period;
};

// Schema-aware loader — branches on DatasetMode because the two
// preprocessing scripts (Section 11) emit slightly different column sets
// (the ULB output has an extra `amount` column; Taobao's `behavior_code`
// values are meaningful 0-3, ULB's is always 0). One loader function
// keeps BehaviorSource's tick() itself dataset-agnostic.
inline std::vector<BehaviorRow> load_replay_csv(const std::string& path, DatasetMode mode) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("cannot open replay CSV: " + path);
    std::string line;
    std::getline(f, line); // header
    std::vector<BehaviorRow> rows;
    while (std::getline(f, line)) {
        std::stringstream ss(line);
        std::string cell;
        BehaviorRow r{};
        std::getline(ss, cell, ','); r.seq = std::stoull(cell);
        std::getline(ss, cell, ','); r.timestamp_ns = std::stoull(cell);
        std::getline(ss, cell, ','); r.user_id = static_cast<std::uint32_t>(std::stoul(cell));
        std::getline(ss, cell, ','); r.item_id = static_cast<std::uint32_t>(std::stoul(cell));
        std::getline(ss, cell, ','); r.category_id = static_cast<std::uint16_t>(std::stoul(cell));
        std::getline(ss, cell, ','); r.behavior_code = static_cast<std::uint8_t>(std::stoi(cell));
        if (mode == DatasetMode::ULB) {
            std::getline(ss, cell, ','); r.amount = std::stof(cell);
        } else {
            r.amount = 0.0f;
        }
        std::getline(ss, cell, ','); r.label = static_cast<std::uint8_t>(std::stoi(cell));
        std::getline(ss, cell, ','); r.label_valid = static_cast<std::uint8_t>(std::stoi(cell));
        std::getline(ss, cell, ','); r.is_burst_period = static_cast<std::uint8_t>(std::stoi(cell));
        rows.push_back(r);
    }
    return rows;
}

// ── BehaviorSource ────────────────────────────────────────────────────────
// Same generator-function wrapping pattern as FinancialTickSource
// (KLStream_Research.md Section 18) — bursty rows (is_burst_period=1)
// always replay at MaxRate regardless of configured mode, calm rows
// respect the configured mode. RawBehaviorEvent deliberately omits
// label/label_valid (Section 13.3's implementation note) — they are
// carried in a parallel, seq-indexed vector exposed via label_for_seq()
// for KeyedFeatureExtractOp to look up.
class BehaviorSource {
public:
    BehaviorSource(std::vector<BehaviorRow> rows, ReplayMode mode, double speed_factor = 1.0)
        : rows_(std::move(rows)), mode_(mode), speed_factor_(speed_factor)
    {
        labels_.reserve(rows_.size());
        for (const auto& r : rows_) labels_.push_back({r.label, r.label_valid});
    }

    bool operator()(Event<RawBehaviorEvent>& out, std::uint64_t /*unused_seq*/) {
        if (idx_ >= rows_.size()) return false;
        const BehaviorRow& r = rows_[idx_];
        bool burst = (r.is_burst_period != 0);
        if (mode_ == ReplayMode::PreserveTiming && !burst && idx_ > 0) {
            std::uint64_t gap_ns = r.timestamp_ns - rows_[idx_ - 1].timestamp_ns;
            auto scaled = std::chrono::nanoseconds(
                static_cast<std::int64_t>(static_cast<double>(gap_ns) / speed_factor_));
            if (scaled < std::chrono::milliseconds(1)) {
                std::this_thread::sleep_for(scaled);
            }
        }
        RawBehaviorEvent raw{ r.user_id, r.item_id, r.category_id, r.behavior_code, r.amount };
        out = Event<RawBehaviorEvent>{ r.timestamp_ns, /*key=*/r.user_id, r.seq, raw };
        ++idx_;
        return true;
    }

    // KeyedFeatureExtractOp's implementation-note workaround (Section 13.3):
    // look up ground truth by seq once the FeatureSnapshot is being built.
    std::pair<std::uint8_t, std::uint8_t> label_for_seq(std::uint64_t seq) const {
        return seq < labels_.size() ? labels_[seq] : std::make_pair<std::uint8_t,std::uint8_t>(0,0);
    }

    std::size_t remaining() const { return rows_.size() - idx_; }

private:
    std::vector<BehaviorRow> rows_;
    std::vector<std::pair<std::uint8_t,std::uint8_t>> labels_;
    ReplayMode mode_;
    double     speed_factor_;
    std::size_t idx_{0};
};

} // namespace klstream
```

---

## 19. `ResultSink` and Controller Trace Logging

Two sinks, mirroring Project 2's separation of concerns precisely: `ResultSink` writes one row per `ScoredResult` (joined offline against ground truth for Feature Regret computation, Section 25), and a second, lightweight `ControllerTraceSink`-style log (a simple `tick()`-driven CSV writer reading `AdaptiveFeatureWindowOp::controller()` and `KeyedFeatureExtractOp::last_alpha()` directly, sampled once per N ticks rather than once per event to keep its own overhead negligible) captures the `W[n]` and `α[n]` traces needed for Section 24's Z-domain analysis and Experiment 6's W↔α correlation check.

```cpp
// include/klstream/feature/result_sink.hpp
#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "types.hpp"
#include <fstream>
#include <iomanip>

namespace klstream {

class ResultSink : public IOperator {
public:
    using InQueue = SPSCQueue<Event<ScoredResult>>;

    ResultSink(std::string name, InQueue* input, std::string out_csv_path)
        : IOperator(std::move(name)), input_(input), out_(out_csv_path)
    {
        out_ << "seq,result_timestamp_ns,latency_ns,user_id,score,label,label_valid,"
                "window_size_used,alpha_used,staleness_sec,occupancy_at_decision\n";
    }

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }

    OpStatus tick() override {
        Event<ScoredResult> ev;
        if (!input_->try_pop(&ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }
        const auto& r = ev.data;
        out_ << ev.seq << ',' << ev.timestamp_ns << ',' << ev.latency_ns() << ','
             << r.user_id << ',' << std::setprecision(8) << r.score << ','
             << static_cast<int>(r.label) << ',' << static_cast<int>(r.label_valid) << ','
             << r.window_size_used << ',' << r.alpha_used << ','
             << r.staleness_sec << ',' << r.occupancy_at_decision << '\n';
        if (metrics_) metrics_->events_processed.increment();
        return OpStatus::Processed;
    }

    void shutdown() override { out_.flush(); }

private:
    InQueue*      input_;
    std::ofstream out_;
    OperatorMetrics* metrics_{nullptr};
};

// Sampled once every CONTROLLER_TRACE_SAMPLE_EVERY ticks of the worker loop
// (a free function called from main()'s outer harness loop, not an
// IOperator — it does not consume a queue, it just reads public state off
// two already-running operators, so it does not need tick()/OpStatus
// machinery at all).
inline void log_controller_trace(std::ofstream& out, std::uint64_t wall_ns,
                                  std::uint32_t w, double alpha, double occupancy) {
    out << wall_ns << ',' << w << ',' << alpha << ',' << occupancy << '\n';
}

} // namespace klstream
```

---

## 20. Offline Model Training — Logistic Regression, Native Export

Trained once, offline, on **oracle features** — recomputed in Python with `alpha` fixed at `alpha_max` (Section 7.2's most-reactive setting, i.e., effectively no smoothing-induced staleness) and `W` effectively 1 (every event published immediately, no batching delay) — over the full calm portion of the labeled dataset. This mirrors Project 2's "the same fitted forest is reused across all architectures; window strategy never changes what the model is, only what it's scored on" principle (`KLStream_Research.md` Section 7.5) exactly: the same fitted logistic regression weights are reused across all four architectures and every experiment; only the *features it gets scored against at runtime* differ by architecture.

```python
# preprocessing/train_classifier.py
"""
Recomputes oracle (alpha=alpha_max, W=1) features in pandas, trains a
logistic regression, exports weights in the plain-text format
LogisticModel::load() expects (Section 17).

Usage:
    python train_classifier.py --replay data/replay/replay_taobao_10k.csv \
        --out models/classifier_weights.txt
"""
import argparse
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import average_precision_score, roc_auc_score

ENGAGEMENT_WEIGHT = {0: 1.0, 1: 3.0, 2: 2.0, 3: 5.0}   # pv, cart, fav, buy — Section 13.2
ALPHA_MAX = 0.30   # oracle = most-reactive setting, Section 20's framing

def compute_oracle_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["user_id", "timestamp_ns"], kind="mergesort").reset_index(drop=True)
    out_rows = []
    for uid, g in df.groupby("user_id", sort=False):
        ema = 0.0
        pv = cart = fav = 0
        prev_ts = None
        for _, row in g.iterrows():
            w = ENGAGEMENT_WEIGHT[int(row["behavior_code"])]
            ema = ALPHA_MAX * w + (1 - ALPHA_MAX) * ema
            if row["behavior_code"] == 0: pv += 1
            elif row["behavior_code"] == 1: cart += 1
            elif row["behavior_code"] == 2: fav += 1
            recency = 0.0 if prev_ts is None else min((row["timestamp_ns"] - prev_ts) / 1e9, 3600.0) / 3600.0
            prev_ts = row["timestamp_ns"]
            out_rows.append({
                "seq": row["seq"], "ema_engagement": ema,
                "log_pv": np.log1p(pv), "log_cart_fav": np.log1p(cart + fav),
                "recency": recency, "label": row["label"], "label_valid": row["label_valid"],
            })
    return pd.DataFrame(out_rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    raw = pd.read_csv(args.replay)
    feats = compute_oracle_features(raw)
    feats = feats[feats["label_valid"] == 1]

    X = feats[["ema_engagement", "log_pv", "log_cart_fav", "recency"]].to_numpy()
    y = feats["label"].to_numpy()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    clf = LogisticRegression(class_weight="balanced", max_iter=1000)
    clf.fit(X_train, y_train)

    p_test = clf.predict_proba(X_test)[:, 1]
    print(f"oracle AUPRC: {average_precision_score(y_test, p_test):.4f}, "
          f"AUROC: {roc_auc_score(y_test, p_test):.4f}")

    with open(args.out, "w") as f:
        f.write(f"bias={clf.intercept_[0]:.10f}\n")
        for i, w in enumerate(clf.coef_[0]):
            f.write(f"w{i}={w:.10f}\n")
    print(f"wrote weights to {args.out}")

if __name__ == "__main__":
    main()
```

**Why oracle AUPRC, reported here, matters for Section 25.** This number is the denominator-defining reference point for Feature Regret — every architecture's online score is compared against what this same model *would have* produced given perfectly fresh features, not against the raw labels directly. Report this oracle number plainly in the paper's setup section before presenting any regret numbers, exactly as Project 2 reported the Isolation Forest's standalone validation metrics (Section 26 of `KLStream_Research.md`) before presenting pipeline-level results.

---

## 21. Repository Structure

Additive to the existing `KLStream` repository, parallel to `adaptive_window/` from Project 2 — every file below is new.

```text
KLStream/
├── (... everything from the Implementation Guide and the AdaptiveWindowOp
│        extension, unchanged ...)
│
├── include/klstream/
│   ├── feature/                                  # NEW
│   │   ├── types.hpp                              # Section 12
│   │   ├── user_state.hpp                         # Section 13.1
│   │   ├── engagement.hpp                         # Section 13.2
│   │   ├── keyed_feature_extract_op.hpp           # Section 13.3
│   │   ├── adaptive_feature_window_op.hpp         # Section 14
│   │   ├── drift_adaptive_window_op.hpp           # Section 15.2
│   │   ├── scoring_flush_op.hpp                   # Section 17
│   │   ├── behavior_source.hpp                    # Section 18
│   │   └── result_sink.hpp                        # Section 19
│   │
│   └── model/                                     # NEW
│       └── logistic_model.hpp                     # Section 17
│
├── preprocessing/                                  # NEW
│   ├── preprocess_taobao.py                       # Section 11
│   ├── preprocess_ulb.py                          # Section 11
│   └── train_classifier.py                        # Section 20
│
├── data/
│   ├── raw/                                       # UserBehavior.csv, creditcard.csv (gitignored)
│   └── replay/                                    # preprocessing outputs (small, committed)
│       ├── replay_taobao_10k.csv
│       └── replay_ulb.csv
│
├── models/                                         # NEW
│   └── classifier_weights.txt                     # train_classifier.py output
│
├── feature_flow/                                   # NEW — experiment driver, parallel
│   ├── CMakeLists.txt                              # to adaptive_window/'s structure
│   ├── main.cpp                                    # Section 23 — full pipeline wiring
│   └── harness.cpp                                 # Section 27 — runs all 4 architectures × loads
│
├── analysis/                                        # NEW
│   ├── compute_metrics.py                          # Section 25/26 — PATR, WOR, Feature Regret
│   ├── zdomain_feature_analysis.py                 # Section 24 — retargeted from Project 1
│   └── results_notebook.ipynb                      # plots for the paper
│
├── results/                                         # NEW (gitignored)
│   └── raw/                                        # per-run CSVs from ResultSink + controller traces
│
└── paper/                                            # NEW
    └── draft.md
```

---

## 22. CMake Integration

```cmake
# feature_flow/CMakeLists.txt
# Appended as a new add_subdirectory() call in the project root CMakeLists.txt,
# alongside the existing add_subdirectory(adaptive_window) call.

add_executable(feature_flow_main main.cpp)
target_link_libraries(feature_flow_main PRIVATE klstream::klstream)

add_executable(feature_flow_harness harness.cpp)
target_link_libraries(feature_flow_harness PRIVATE klstream::klstream)
```

No new external dependencies — `logistic_model.hpp` is pure `<fstream>`/`<cmath>`/STL, consistent with Decision 5. `target_link_libraries(... klstream::klstream)` already pulls in `-pthread` and the include path; nothing else is required.

---

## 23. Full Pipeline Wiring — `main.cpp` for Each Architecture

```cpp
// feature_flow/main.cpp
#include "klstream/core/runtime.hpp"
#include "klstream/core/spsc_queue.hpp"
#include "klstream/operators/source.hpp"
#include "klstream/operators/window.hpp"          // TumblingCountWindow, reused
#include "klstream/feature/types.hpp"
#include "klstream/feature/keyed_feature_extract_op.hpp"
#include "klstream/feature/adaptive_feature_window_op.hpp"
#include "klstream/feature/drift_adaptive_window_op.hpp"
#include "klstream/feature/scoring_flush_op.hpp"
#include "klstream/feature/behavior_source.hpp"
#include "klstream/feature/result_sink.hpp"
#include "klstream/model/logistic_model.hpp"
#include <string>
#include <iostream>

using namespace klstream;

enum class Architecture { Fixed, DriftAdaptive, RateThrottle, Adaptive };

int main(int argc, char** argv) {
    // ── CLI parsing (architecture, dataset, replay CSV path, model path,
    // output CSV path, replay mode/speed) elided here for brevity — wire
    // with a small flag parser; values below show the four architectures'
    // WIRING DIFFERENCES, which is the part that matters for correctness.
    Architecture arch = /* from --arch flag */ Architecture::Adaptive;
    DatasetMode  dataset = /* from --dataset flag */ DatasetMode::Taobao;
    std::string replay_path = /* from --replay flag */ "data/replay/replay_taobao_10k.csv";
    std::string model_path  = /* from --model flag */ "models/classifier_weights.txt";
    std::string out_path    = /* from --out flag */ "results/raw/run.csv";

    auto rows = load_replay_csv(replay_path, dataset);
    BehaviorSource behavior_src(std::move(rows), ReplayMode::MaxRate, /*speed_factor=*/1.0);
    LogisticModel model = LogisticModel::load(model_path);

    // ── Queues. Section 7.3-style sizing note (carried over from Project 2):
    // FeatureBatch is roughly (4 floats + small fields) * MAX_FEATURE_BATCH
    // bytes ≈ a few KB per slot — use a SMALL capacity (32-64) for the
    // window-stage -> ScoringFlushOp queue specifically, not the default
    // queue capacity, for the same memory-budget reason Section 7.3 of
    // KLStream_Research.md gives for WindowBatch.
    SPSCQueue<Event<RawBehaviorEvent>> q_raw(4096);
    SPSCQueue<Event<FeatureSnapshot>>  q_feat(4096);
    SPSCQueue<Event<FeatureBatch>>     q_batch(64);
    SPSCQueue<Event<ScoredResult>>     q_scored(4096);

    SourceOperator<RawBehaviorEvent> source("behavior_source", &q_raw,
        [&behavior_src](Event<RawBehaviorEvent>& out, std::uint64_t seq) {
            return behavior_src(out, seq);
        });

    BackpressureSignal signal;   // owned by main(); pointer shared between
                                  // KeyedFeatureExtractOp (reader) and
                                  // AdaptiveFeatureWindowOp (writer) — only
                                  // actually written to for arch == Adaptive

    Runtime rt;

    switch (arch) {
    case Architecture::Fixed: {
        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
            /*signal=*/nullptr, /*fixed_alpha=*/0.10);
        auto aggr = [](const std::vector<FeatureSnapshot>& buf) -> FeatureBatch {
            FeatureBatch fb{}; for (auto& s : buf) fb.push_back(s, 0); return fb;
        };
        TumblingCountWindow<FeatureSnapshot, FeatureBatch> window(
            "fixed_window", &q_feat, &q_batch, /*window_size=*/128, aggr);
        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model);
        ResultSink sink("sink", &q_scored, out_path);

        rt.register_op(&source); rt.register_op(&extract);
        rt.register_op(&window); rt.register_op(&scorer); rt.register_op(&sink);
        rt.run_until_source_exhausted();   // exact name TBD per Runtime's API,
                                            // Implementation Guide Section 7.10
        break;
    }
    case Architecture::DriftAdaptive: {
        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
            /*signal=*/nullptr, /*fixed_alpha=*/0.10);
        DriftAdaptiveWindowOp window("drift_window", &q_feat, &q_batch);
        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model);
        ResultSink sink("sink", &q_scored, out_path);

        rt.register_op(&source); rt.register_op(&extract);
        rt.register_op(&window); rt.register_op(&scorer); rt.register_op(&sink);
        rt.run_until_source_exhausted();
        break;
    }
    case Architecture::RateThrottle: {
        // Section 16's admission-control wiring lives INSIDE BehaviorSource's
        // generator callback or as a thin wrapper around it — apply the
        // EMAOccupancyTracker<SPSCQueue<Event<RawBehaviorEvent>>> +
        // TokenBucketRateLimiter pair against q_raw before each emit, then
        // wire FixedWindowOp downstream exactly as in the Fixed case.
        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
            /*signal=*/nullptr, /*fixed_alpha=*/0.10);
        auto aggr = [](const std::vector<FeatureSnapshot>& buf) -> FeatureBatch {
            FeatureBatch fb{}; for (auto& s : buf) fb.push_back(s, 0); return fb;
        };
        TumblingCountWindow<FeatureSnapshot, FeatureBatch> window(
            "fixed_window_throttled", &q_feat, &q_batch, /*window_size=*/128, aggr);
        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model);
        ResultSink sink("sink", &q_scored, out_path);

        rt.register_op(&source); rt.register_op(&extract);
        rt.register_op(&window); rt.register_op(&scorer); rt.register_op(&sink);
        rt.run_until_source_exhausted();
        break;
    }
    case Architecture::Adaptive: {
        KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat,
            /*signal=*/&signal);   // alpha_min/max/d_alpha_max default per Section 14.1
        AdaptiveFeatureWindowOp window("adaptive_window", &q_feat, &q_batch, &signal);
        ScoringFlushOp scorer("scorer", &q_batch, &q_scored, &model);
        ResultSink sink("sink", &q_scored, out_path);

        rt.register_op(&source); rt.register_op(&extract);
        rt.register_op(&window); rt.register_op(&scorer); rt.register_op(&sink);
        rt.run_until_source_exhausted();

        std::cout << "final W=" << window.controller().current()
                  << " direction_changes=" << window.controller().direction_changes()
                  << " final alpha=" << extract.last_alpha() << "\n";
        break;
    }
    }
    return 0;
}
```

Note for the agent: `occupancy_at_decision` on `ScoredResult` (left as `0.0f` in `ScoringFlushOp`'s construction, Section 17) must be filled in for the Adaptive architecture specifically by threading the EMA reading captured at window-start through `FeatureBatch` (add a `float occupancy_at_window_start` field to `FeatureBatch`, populated by `AdaptiveFeatureWindowOp` at the same `if (buffer_.count == 0)` point it already reads `tracker_.ema()`, Section 14) rather than re-reading the tracker from `ScoringFlushOp`, which has no access to it — this exactly mirrors how Project 2's wiring code filled in the equivalent field for its own Adaptive variant only (`KLStream_Research.md` Section 17.1's `out_ev.data = DetectionResult{... 0.0f /* filled in by wiring code */}` comment).

---

## 24. Z-Domain Post-Hoc Analysis — Closing the Loop With Project 1

This is what makes Section 7's theory section an empirical contribution rather than a restatement: the exact frozen-time machinery from `load-adaptive-iir` (pole-zero plot, magnitude/phase response via `H(e^{jω})`, group delay, swept across a representative range and stitched into a time-varying heatmap) is applied here to the **real, logged `alpha[n]` trace** from a genuine run of the Adaptive architecture against the Taobao replay — not to a synthetic signal.

```python
# analysis/zdomain_feature_analysis.py
"""
Reuses Project 1's frozen-time Z-domain analysis machinery (filters.py /
zdomain_analysis.py — import directly from the load-adaptive-iir repo
checkout if available, otherwise re-derive these three functions exactly
per Project 1's Section on frozen-time analysis), retargeted to the real
alpha[n] trace logged by ResultSink's controller-trace CSV (Section 19)
during a run of the Adaptive architecture.

Usage:
    python zdomain_feature_analysis.py \
        --trace results/raw/adaptive_controller_trace.csv \
        --out-heatmap results/figures/passband_narrowing_heatmap.png
"""
import argparse
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import freqz

def single_pole_response(alpha: float, n_freqs: int = 512):
    """H(z) = alpha / (1 - (1-alpha) z^-1); pole at z = 1-alpha. Identical
    transfer function Project 1 analyzes — see Project 1's frozen-time
    section for the full derivation this function operationalizes."""
    b = [alpha]
    a = [1.0, -(1.0 - alpha)]
    w, h = freqz(b, a, worN=n_freqs)
    return w, np.abs(h), np.unwrap(np.angle(h))

def group_delay(alpha: float, w: np.ndarray) -> np.ndarray:
    # Closed-form group delay for a single real pole at p = 1-alpha:
    # tau_g(omega) = p (p - cos(omega)) / (1 - 2 p cos(omega) + p^2)
    p = 1.0 - alpha
    return p * (p - np.cos(w)) / (1.0 - 2 * p * np.cos(w) + p ** 2)

def build_time_varying_heatmap(alpha_trace: np.ndarray, n_freqs: int = 256):
    """Stitches one frequency-response column per logged alpha[n] sample —
    the exact 'sweep alpha, stitch into a time-varying heatmap' procedure
    from Project 1, now driven by REAL controller output instead of a
    synthetic sweep grid."""
    heatmap = np.zeros((n_freqs, len(alpha_trace)))
    for i, a in enumerate(alpha_trace):
        a = max(a, 1e-4)   # guard against alpha=0 producing a degenerate H(z)
        _, mag, _ = single_pole_response(a, n_freqs)
        heatmap[:, i] = 20 * np.log10(np.maximum(mag, 1e-6))
    return heatmap

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True,
                     help="CSV with columns: wall_ns,w,alpha,occupancy (Section 19's log_controller_trace)")
    ap.add_argument("--out-heatmap", required=True)
    args = ap.parse_args()

    trace = np.genfromtxt(args.trace, delimiter=",", names=True)
    alpha_trace = trace["alpha"]
    occupancy_trace = trace["occupancy"]
    w_trace = trace["w"]

    heatmap = build_time_varying_heatmap(alpha_trace)

    fig, (ax_top, ax_main) = plt.subplots(2, 1, figsize=(10, 6),
                                            gridspec_kw={"height_ratios": [1, 3]}, sharex=True)
    ax_top.plot(occupancy_trace, label="queue occupancy EMA (L[n])", color="tab:red")
    ax_top.plot(alpha_trace / alpha_trace.max(), label="alpha[n] (normalized)", color="tab:blue")
    ax_top.legend(loc="upper right", fontsize=8)
    ax_top.set_ylabel("normalized")

    im = ax_main.imshow(heatmap, aspect="auto", origin="lower", cmap="magma",
                         extent=[0, len(alpha_trace), 0, np.pi])
    ax_main.set_ylabel("frequency (rad/sample)")
    ax_main.set_xlabel("window-firing index n")
    fig.colorbar(im, ax=ax_main, label="|H(e^{jω})| (dB)")
    fig.suptitle("Feature filter passband narrowing under real backpressure "
                  "(BPFeat, Adaptive architecture, Taobao replay)")
    fig.tight_layout()
    fig.savefig(args.out_heatmap, dpi=150)
    print(f"wrote {args.out_heatmap}")

    # W <-> alpha equivalence check (Experiment 6, Section 27) — the EWMA
    # span identity from Section 7.3, computed against the REAL traces.
    n_alpha_equiv = 2.0 / np.clip(alpha_trace, 1e-4, None) - 1.0
    corr = np.corrcoef(n_alpha_equiv, w_trace)[0, 1]
    print(f"Pearson correlation between N_alpha[n] (equivalent EMA span) "
          f"and W[n] (logged window size): {corr:.4f}")
    print("Report this number plainly in the paper regardless of its value "
          "(Decision 3 / Section 6, point 1's framing — this is a genuine "
          "empirical question, not a result to cherry-pick toward 1.0).")

if __name__ == "__main__":
    main()
```

---

## 25. Evaluation Methodology — Metrics in Full

All metrics are computed **offline, in Python**, from `results/raw/<run>.csv` (Section 19's `ResultSink` output), keeping `ScoringFlushOp`'s `tick()` free of any logic unrelated to the actual research question — the same separation-of-concerns argument Project 2's Section 23 makes.

### 25.1 Pressure-Adaptive Throughput Retention (PATR) — Reused Unmodified

```
PATR = throughput(during burst window) / throughput(during steady-state window)
```
Computed per architecture per run from `ResultSink`'s row arrival rate during `is_burst_period == 1` segments versus `is_burst_period == 0` segments — identical definition to Project 2's Section 23.1, included here for direct cross-project comparability of the same metric under a different actuator.

### 25.2 Window Oscillation Rate (WOR) — Reused Unmodified

```
WOR = controller.direction_changes() / run_duration_minutes
```
Exposed by `BPFeatController` (Section 14) and `DriftAdaptiveWindowOp` (Section 15.2) identically — a low, stable WOR under sustained marginal occupancy is evidence the deadband design works; report a high WOR honestly if observed.

### 25.3 Feature Regret (FR) — The Headline Accuracy Metric

```
FR(architecture, run) = mean over labeled, valid events of:
    BCE( ScoredResult.score , oracle_model.predict_proba(oracle_features_for_this_event) )
    minus
    BCE( ScoredResult.score , label )
```

More precisely, following RALF's formalization (Section 4.1) directly: for each scored event with `label_valid=1`, recompute the oracle's score for that exact event (Section 20's offline oracle feature reconstruction, joined by `seq`), and report

```
FR = mean_i [ loss(score_online_i, label_i) − loss(score_oracle_i, label_i) ]
```

using binary cross-entropy as `loss`. **FR ≥ 0 by construction is not guaranteed and should not be assumed** — an architecture could, in principle, outperform the oracle on a given finite sample by chance; report the raw signed quantity, do not clip it, and discuss any negative values honestly rather than treating them as a bug to be hidden.

### 25.4 Staleness — A Diagnostic, Not the Headline Metric

```
mean_staleness_sec(architecture) = mean over ScoredResult rows of staleness_sec (Section 10.4)
```

Reported alongside FR specifically to make Section 26's point concrete: an architecture with low staleness but high FR (or vice versa) is a real, reportable, and interesting finding, not a contradiction to be resolved by picking one number.

### 25.5 Controller Overhead

```
overhead_ns_per_tick(architecture) = wall-clock time spent inside the
    sizing-decision branch of AdaptiveFeatureWindowOp::tick() or
    DriftAdaptiveWindowOp::tick() (the `if (buffer_.count == 0) {...}`
    block specifically), divided by total ticks, EXCLUDING queue-call time
```
Identical measurement discipline to Project 2's Section 23.5.

### 25.6 Per-User Fairness Check (Supporting Section 6, Point 4)

```
fairness_gap(architecture) = staleness_sec averaged over the bottom-quartile
    users by event count, minus staleness_sec averaged over the top-quartile
    users by event count
```
A large positive gap indicates the global controller systematically under-serves low-traffic users relative to high-traffic ones — checked explicitly in Experiment 3 (Section 27), reported honestly regardless of outcome.

---

## 26. The Regret-Attribution Trap and How This Project Avoids It

This section is the direct structural analog of Project 2's Section 24 ("The Point-Adjustment Trap") — a named, deliberately-engaged-with evaluation pitfall, not an afterthought.

**The trap, stated plainly.** A naive evaluation could report Feature Regret (Section 25.3) computed only on the events the system actually chose to score and publish, without accounting for *how many* events that is, or for whether the architecture being evaluated is implicitly cherry-picking easy moments to publish. An architecture that publishes very rarely, but happens to publish during easy-to-classify moments, could show artificially low regret while providing far less practical utility than the numbers suggest — the direct analog of how a detector that fires one alert per anomalous segment can inflate point-adjusted F1 without actually detecting anomalies promptly (Project 2's exact concern).

**How this project avoids it, concretely:**

1. **Report regret per architecture over the FULL set of labeled, valid events that architecture's run produced a score for — never a filtered or cherry-picked subset** — and separately report what *fraction* of all valid labeled events each architecture actually scored (an architecture that publishes less often necessarily scores fewer of a user's events at all, and that coverage rate must be reported alongside regret, not hidden).
2. **A shuffled-features null baseline.** Before trusting any architecture's regret number, run the oracle model against deliberately shuffled (label-feature-mismatched) features and confirm the resulting regret is large and clearly distinguishable from every real architecture's regret — a basic sanity check that the regret computation pipeline itself is not silently broken (e.g., a `seq` join bug making "oracle" and "online" features secretly identical, which would report regret ≈ 0 for every architecture and falsely look like a perfect result).
3. **Report regret AND staleness AND coverage together, never regret alone**, exactly as Section 25.4 requires — a result section that shows only regret invites exactly the kind of selective reporting this section exists to prevent.
4. **Multiple independent runs with confidence intervals (Section 28)**, not a single run's point estimate — a single favorable run's regret number proves nothing on its own, the same standard Project 2 held its own headline numbers to.
5. **The fairness check (Section 25.6) is run as a standard part of every experiment, not only when a problem is suspected** — silently omitting it would be exactly the kind of convenient blind spot this section is named to prevent.

---

## 27. Experiment Design — Six Experiments in Full

Mirrors Project 2's five-experiment structure (`KLStream_Research.md` Section 25), extended by one to cover the W↔α equivalence question this project adds.

### Experiment 1 — Mechanism Validation (RQ1)

Run the Adaptive architecture against a replay with one clearly-defined synthetic burst injected (a short, sharp spike in arrival rate, separate from the natural-burst tagging used elsewhere, specifically so the causal chain's timing is unambiguous to inspect). Plot, on a shared time axis: raw arrival rate, `q_batch` occupancy, `W[n]`, `alpha[n]`. **Pass condition:** occupancy visibly rises during the injected burst, `W[n]` visibly falls shortly after, `alpha[n]` visibly rises shortly after, and both recover once the burst ends — directly demonstrating Section 8.2's causal chain happened as described, for both mechanisms, not just one.

### Experiment 2 — Latency and Throughput Retention Under Burst (RQ3, headline result #1)

All four architectures, same replay, same burst schedule. Report PATR (Section 25.1) and end-to-end p50/p99 latency (`Event::latency_ns()` at `ResultSink`) per architecture. **Expected (not guaranteed) result to report honestly either way:** the Adaptive architecture retains throughput closer to steady-state during bursts than Fixed and DriftAdaptive; RateThrottle may retain comparable throughput by a different mechanism (admitting fewer events rather than processing batches faster) — report this distinction explicitly if observed, since "retains throughput" via dropping/delaying admission is a materially different outcome from "retains throughput" via cheaper processing, and conflating them would understate RateThrottle's real cost (events simply arrive late) or overstate the Adaptive architecture's advantage.

### Experiment 3 — Feature Regret Cost of Adaptation and Fairness Check (RQ3, headline result #2 — report honestly)

All four architectures, same replay. Report Feature Regret, staleness, coverage (Section 26), and the fairness gap (Section 25.6), each with confidence intervals across multiple runs (Section 28). This is the experiment most likely to show a genuine trade-off rather than a clean win — report it as such if that is what the data shows; Project 2's own Experiment 3 explicitly modeled this "report honestly" discipline and this project inherits it directly.

### Experiment 4 — Sensitivity Sweep (RQ3, generalization check — not optional)

Sweep `occ_low`/`occ_high`, `shrink_factor`/`grow_factor`, and `alpha_min`/`alpha_max` independently around their Section 14.1 defaults (e.g., ±30%) on the Adaptive architecture only, holding everything else fixed. **Purpose:** confirm the qualitative result from Experiments 2–3 is not an artifact of one specific, possibly cherry-picked, parameter setting. Report the full sweep, not just the best-performing point in it.

### Experiment 5 — ULB Generalization Check (RQ4)

All four architectures, identical pipeline code, run against the ULB secondary dataset (Section 9.2, degenerate single-key mode, Section 10.5). Report the same metrics as Experiment 3. **Purpose:** test whether the qualitative finding from the Taobao experiments (favorable PATR-vs-regret trade-off for the Adaptive architecture) survives a structurally different workload (single global key, much higher per-key event rate, a domain — fraud — with a very different class balance and feature semantics than recsys purchase propensity). A negative or weaker result here is itself a legitimate, reportable finding about the boundary conditions of the mechanism — do not suppress it.

### Experiment 6 — W↔α Empirical Equivalence (RQ2)

Using the controller trace logged during Experiment 1 and Experiment 2's Adaptive runs, compute the Pearson correlation between the logged `W[n]` and the EWMA-equivalent span `N_alpha[n] = 2/alpha[n] − 1` (Section 24's `zdomain_feature_analysis.py`), and separately produce the time-varying frequency-response heatmap (Section 24) as the paper's flagship Z-domain figure, now annotated with the real burst timing from Experiment 1's known injection point. Report the correlation number plainly regardless of its magnitude — this experiment exists to answer a genuine open question (Section 6, point 1; Decision 3), not to confirm an assumed result.

---

## 28. Statistical Rigor — Runs, Warmup, Confidence Intervals

- **Minimum 5 independent runs per (architecture, dataset, experiment) cell**, varying only the random seed used for any synthetic burst placement or train/test split — not the underlying replay data itself, which stays fixed for a given dataset to keep cross-architecture comparisons paired (same exact event sequence seen by all four architectures within one seed).
- **Warmup discard:** exclude the first `W_max` (256) processed events from every metric computation — the controller has not reached steady state before then, and including this period would bias early-window architectures' averages.
- **Report mean ± 95% CI** (via a `t`-distribution or bootstrap CI for small `n`, your choice — state which is used) for every headline number (PATR, Feature Regret, WOR, staleness, p99 latency) in every results table, not point estimates alone — directly extending Project 2's own Section 27 discipline.
- **Pin all four architectures to the same replay file and the same seed within a single run**, so any difference observed is attributable to the control policy and not to incidental differences in which events each architecture happened to see.

---

## 29. Testing Strategy

Unit tests, mirroring Project 2's Section 12 structure:

- `test_bpfeat_controller.cpp` — `BPFeatController::update()` against synthetic occupancy traces: confirm shrink-on-high, grow-on-low, deadband-holds-steady, clamping at `w_min`/`w_max`, `direction_changes()` counts correctly on a hand-constructed oscillating trace.
- `test_alpha_controller.cpp` — `AlphaController::update()`: confirm the slew-rate bound is never violated for an adversarial step-function occupancy input, confirm the sign (rising occupancy → rising α, the opposite of Project 1's `load_adaptive_ema` test, which should be cited and explicitly contrasted in the test file's comments per Decision 3).
- `test_keyed_feature_extract_op.cpp` — confirm per-user state is correctly isolated (two interleaved users' EMAs do not leak into each other), confirm `MAX_TRACKED_USERS` overflow throws as specified (Section 13.3), confirm the ULB degenerate single-key path (Section 13.4) behaves identically to the general path with `N_USERS=1`.
- `test_scoring_flush_op.cpp` — confirm the multi-item Blocked-recovery (`has_pending_idx_`, Section 17) correctly resumes mid-batch after an artificially full output queue, with no event skipped or duplicated — this is the one place this project's Blocked-handling diverges from the established single-pending-event idiom and is the highest-risk piece of new control flow to get wrong.
- `test_drift_adaptive_window_op.cpp` — confirm window shrinks on an injected synthetic drift (a step change in engagement weight) and grows during a stable synthetic stream, independent of any queue-occupancy state (construct the test with an artificially saturated downstream to confirm `DriftAdaptiveWindowOp`'s behavior is unaffected by it — the property that makes it a fair "signal-driven, not load-driven" baseline).
- `test_pipeline_integration.cpp` — end-to-end run of all four architectures against a small synthetic replay (a few hundred events, hand-constructed with known bursts and known labels), confirming every architecture produces the same total row count in `ResultSink`'s output (modulo the trailing-`H`-events exclusion, Section 10.1) and that `ScoredResult.label`/`label_valid` correctly round-trip from the input CSV through `BehaviorSource`'s parallel label vector (Section 13.3's implementation note) to the final output row.

---

## 30. Risks and Honest Difficulty Assessment

- **The per-key hash map is the single highest engineering-risk new component.** `TumblingCountWindow` and `AdaptiveWindowOp` in Project 2 are stateless with respect to *which* stream they're processing; `KeyedFeatureExtractOp` is genuinely new state-management code with no direct precedent in either prior project. Budget real debugging time for it, particularly around the `MAX_TRACKED_USERS` boundary and the ULB degenerate-key edge case.
- **The multi-item Blocked-recovery pattern in `ScoringFlushOp` (Section 17) is a real deviation from the established single-pending-event idiom** used everywhere else in this codebase and in both prior projects. Treat it as the highest-risk piece of new control flow, test it explicitly (Section 29), and do not assume "it looks like the other operators" extends to its blocked-handling correctness.
- **Tianchi registration friction (Section 9.3) is a real, non-technical risk to the timeline** — start this step first, in parallel with early development on the synthetic fallback generator, not after the C++ pipeline is otherwise ready.
- **RQ2 (the W↔α equivalence) may simply come back negative** — the two control loops may not track each other well empirically (Section 7.5's worked example already shows their *static* endpoints don't match exactly). This is an acceptable, reportable outcome and should not be treated as a project failure if it occurs; Section 6's framing exists specifically so a negative Experiment 6 result is still a contribution (an honest answer to a real open question), not a null result to be hidden.
- **The downstream classifier's absolute predictive power may be modest** (a 4-feature logistic regression on a sparse, highly imbalanced purchase-propensity task is not going to be state-of-the-art) — this is acceptable and expected, since the paper's claim is about *regret relative to the oracle using the same model*, not about achieving a high absolute AUPRC. State the oracle AUPRC plainly (Section 20) so readers can calibrate what "low regret relative to a modest oracle" actually means.
- **Fairness findings (Section 25.6) could be unflattering to the contribution** — a global controller may plausibly be shown to disadvantage low-traffic users. This must be reported regardless of outcome (Section 26, point 5); treating this as a risk to manage rather than a result to suppress is itself part of this project's intended rigor.

---

## 31. Build Timeline (Suggested, 7 Weeks)

| Week | Milestone |
|---|---|
| 1 | Tianchi registration submitted; ULB data downloaded; `preprocess_taobao.py`/`preprocess_ulb.py` written and validated on a small subsample; synthetic fallback generator ready as a parallel-track safety net |
| 2 | `types.hpp`, `user_state.hpp`, `engagement.hpp`, `KeyedFeatureExtractOp` implemented and unit-tested in isolation (no queues needed for `AlphaController`'s own tests) |
| 3 | `BPFeatController`, `AdaptiveFeatureWindowOp`, `ScoringFlushOp` (including the multi-item Blocked-recovery path) implemented and unit-tested |
| 4 | `BehaviorSource`, `ResultSink`, `FixedWindowOp` wiring, `DriftAdaptiveWindowOp`, `RateThrottleSource` wiring — all four architectures running end-to-end on the synthetic fallback dataset |
| 5 | `train_classifier.py` run on real Taobao subsample; full pipeline run on real data; Experiment 1 (mechanism validation) and Experiment 2 (PATR/latency) executed and sanity-checked |
| 6 | Experiments 3–6 executed (regret, sensitivity sweep, ULB generalization, W↔α equivalence); `zdomain_feature_analysis.py` producing the flagship heatmap from real logged traces |
| 7 | Statistical rigor pass (multiple seeds, CIs), results notebook, paper draft assembled per Section 32's outline |

---

## 32. Paper Outline and Venue Guidance

**Suggested IEEE-style section structure:**

1. Introduction — the freshness-vs-cost trade-off as a static-configuration problem in current practice; the one-paragraph pitch (Section 3)
2. Related Work — Section 4 in full, anchored by Biathlon and RALF, with the gap table (Section 4.9) adapted into prose or kept as a table
3. System Design — Section 8's architecture and causal chain, with the pipeline diagram
4. Theoretical Foundation — Section 7, the EWMA span-α identity, the worked numeric example, framed honestly as a hypothesis tested in Section IV's experiments rather than an assumed equivalence
5. Implementation — brief; point to the open-source repository rather than reproducing full code in the paper body, with 1-2 key listings (the `BPFeatController`/`AlphaController` pair, and the causal-chain diagram) as the only inline code
6. Experimental Setup — datasets (Section 9, including the ULB limitation stated plainly), baselines (Section 4.9's row, condensed), metrics (Section 25), the oracle's standalone AUPRC (Section 20)
7. Results — Experiments 1–6 (Section 27), in order, each with its honest framing preserved from this document, not softened for the paper
8. Discussion — Decision 3's "why does α move in opposite directions across the two projects" discussion, the fairness finding, the generalization result, threats to validity
9. Conclusion

**Venue guidance.** IT4D (the venue used for Project 2, Kathmandu-based, matching the author's location) remains a reasonable, accessible option and keeps this work in the same venue track as the prior submission, which can be advantageous for a coherent author research narrative across submissions. Given this project's stronger general systems/ML-serving framing relative to Project 2's more narrowly financial-anomaly-detection scope, also consider any IEEE Xplore-indexed regional conference with an explicit data engineering / ML systems track, if accessible, since the related work (RALF, Biathlon, dynamic batching) skews toward a systems-for-ML audience rather than a financial-anomaly or general ICT4D audience specifically. Confirm current submission deadlines and scope for any venue under consideration directly on the venue's website before committing, since conference calls-for-papers change year to year.

---

## 33. Full Reference List

**Feature stores and ML serving:**
- RALF (feature store regret scheduling) — Russo et al., VLDB 2024 (verify exact author list and title against the published version before submission)
- [NEW] Biathlon — approximate feature aggregation with accuracy bounds for ML inference, VLDB 2024 (arXiv:2405.11191) — verify exact citation
- Feast, Tecton, Hopsworks, Chalk — industrial feature store documentation, cited as current-practice examples

**[NEW] Adjacent systems prior art found independently:**
- ADWISE — adaptive window-based streaming edge partitioning, IEEE ICDCS 2018
- US Patent 9,521,158 — "Feature Aggregation in a Computer Network"
- Clipper (Crankshaw et al.), NVIDIA Triton dynamic batching documentation, continuous-batching LLM serving literature — cited collectively as the dynamic-batching adjacent-but-distinct body of work

**Backpressure and active queue management:**
- RED — Floyd & Jacobson, 1993
- CoDel — Nichols & Jacobson, 2012
- Spark Streaming `PIDRateEstimator` (legacy DStream API — cite the correct API surface, not Structured Streaming)
- Flink credit-based flow control documentation

**Concept-drift-adaptive windowing:**
- ADWIN — Bifet & Gavaldà, SDM 2007
- Tolerance Tiers (arXiv:1906.11307)

**Datasets:**
- Taobao UserBehavior — Alibaba Tianchi, `https://tianchi.aliyun.com/dataset/649`
- ULB Credit Card Fraud — `mlg-ulb/creditcardfraud`, Kaggle / Université Libre de Bruxelles Machine Learning Group, Dal Pozzolo et al.

**This research program's own prior art:**
- Project 1 — `load-adaptive-iir`, the load-driven IIR filter and frozen-time Z-domain methodology this project's Mechanism B and Section 24 directly extend
- Project 2 — `KLStream` and `KLStream-AdaptiveWindow`, the runtime and the `EMAOccupancyTracker`-driven window-control mechanism this project's Mechanism A directly extends, including the point-adjustment-trap discipline (`KLStream_Research.md` Section 24) this project's Section 26 mirrors
- Project 2's own citation of Kim et al., AAAI 2022, on the point-adjustment trap in time-series anomaly detection evaluation — relevant as methodological precedent for this project's analogous regret-attribution-trap discussion (Section 26), even though this project's task is not detection

**A note on citation verification:** every citation above should be verified against its actual published form (exact authors, venue, year, and where relevant arXiv identifier) before submission — several were located via independent web search for this document and should be re-confirmed at write-up time rather than taken on faith from this document alone.

---

## 34. Glossary of New Terms

- **Mechanism A** — the discrete, AIMD-controlled window/batch-size actuator (`BPFeatController`, `W[n]`), controlling publish/refresh cadence.
- **Mechanism B** — the continuous, slew-rate-bounded IIR-pole actuator (`AlphaController`, `α[n]`), controlling per-key EMA feature memory/reactivity.
- **`BackpressureSignal`** — the shared, atomic, single-writer/multi-reader publish point connecting Mechanism A's controller to Mechanism B's controller.
- **Feature Regret (FR)** — RALF-style downstream-model loss degradation, this project's headline accuracy metric (Section 25.3).
- **Staleness** — per-publish elapsed time since a given key's feature was last refreshed (Section 10.4); a diagnostic, not the headline metric (Section 26).
- **Oracle features** — features computed at `alpha = alpha_max`, effectively `W = 1` (Section 20) — the maximally fresh, unapproximated reference point regret is measured against.
- **`N_alpha[n]`** — the EWMA-equivalent span of α[n] via `N = 2/α − 1` (Section 7.3), used to test the W↔α equivalence (Experiment 6).
- **Degenerate single-key case** — the ULB secondary dataset's `user_id = 0` mode (Section 10.5), exercising the keyed code path at key cardinality 1.

---

## 35. Appendix — Ordered Task Breakdown for a Coding Agent

1. Set up the repository structure (Section 21) inside the existing `KLStream` checkout; add `feature_flow/` and `add_subdirectory(feature_flow)` to the root `CMakeLists.txt`.
2. Begin Tianchi registration (Section 9.3, step 1) immediately — this has the longest external lead time of any task here. In parallel, download `creditcard.csv` and write the synthetic Taobao-shaped fallback generator (Section 9.3, step 4) so development is not blocked.
3. Implement `preprocess_taobao.py` and `preprocess_ulb.py` (Section 11); validate against the synthetic fallback data first, then against real data once available.
4. Implement `include/klstream/feature/types.hpp` (Section 12); confirm every `static_assert(std::is_trivially_copyable_v<...>)` passes.
5. Implement `user_state.hpp`, `engagement.hpp`, and `AlphaController` + `KeyedFeatureExtractOp` (Section 13); unit-test `AlphaController` in isolation first (no queues needed), then `KeyedFeatureExtractOp` with a tiny synthetic two-user stream.
6. Implement `BPFeatController` + `AdaptiveFeatureWindowOp` (Section 14); unit-test the controller against synthetic occupancy traces before wiring it to a real queue.
7. Implement `DriftAdaptiveWindowOp` (Section 15.2) and the `RateThrottleSource` wiring sketch (Section 16); confirm `DriftAdaptiveWindowOp`'s behavior is unaffected by an artificially saturated downstream queue (Section 29's test).
8. Implement `logistic_model.hpp` and `ScoringFlushOp` (Section 17), paying particular attention to the multi-item Blocked-recovery path (`has_pending_idx_`) — write its unit test before considering this operator done.
9. Implement `BehaviorSource` and `ResultSink` (Sections 18–19), including the parallel label-vector lookup (Section 13.3's implementation note).
10. Wire `feature_flow/main.cpp` for all four architectures (Section 23); run `test_pipeline_integration.cpp` (Section 29) against a small hand-constructed synthetic replay before touching real data.
11. Implement `train_classifier.py` (Section 20); run it once Taobao data is available; record the oracle AUPRC/AUROC plainly.
12. Run Experiment 1 (Section 27) first, specifically to validate the causal chain end to end (Section 8.2) — do not proceed to the remaining experiments until both halves of the causal chain (W and α both responding to a synthetic burst as described) are confirmed.
13. Implement `analysis/compute_metrics.py` (Section 25) including the shuffled-features null-baseline sanity check (Section 26, point 2) — run the sanity check before trusting any regret number from the real pipeline.
14. Run Experiments 2–5 (Section 27), each with the minimum 5 seeds (Section 28), recording confidence intervals throughout.
15. Implement `analysis/zdomain_feature_analysis.py` (Section 24) and run Experiment 6, reporting the W↔α correlation honestly regardless of magnitude.
16. Assemble the results notebook and paper draft per Section 32's outline, with every headline number traceable back to a specific experiment and run set logged under `results/raw/`.
