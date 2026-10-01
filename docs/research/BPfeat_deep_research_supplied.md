# Project AMOS/BPFeat Research Assessment

## A. Verdict on Research Direction

The AMOS project aims to investigate **streaming feature maintenance** and **adaptive batching** for online prediction serving.  It combines ideas of *streaming feature updates*, *approximate feature computation*, *workload admission control*, and *prediction serving*.  These are legitimate research topics, but the novelty and scope require scrutiny.  Key elements include: (1) **Feedback-driven feature adaptation** – using queue pressure to adjust feature-publishing effort or smoothing gains; (2) **Batch size control** – dynamically changing inference batch size under latency targets; and (3) **Streaming forecasting task** – predicting user purchases using the Taobao behavior logs (with a secondary credit-card fraud dataset).  

This direction is **not obviously novel** by itself. Adaptive batching and workload control have been studied (e.g. in Clipper [73] for query serving), and streaming feature stores (e.g. RALF [56]) are emerging topics.  The combination here – especially tying *queue backpressure* to *feature freshness and resource use* – is plausible but not yet established.  It is scientifically defensible **only if framed clearly**: e.g. “how can dynamic feedback improve the freshness-performance tradeoff in online feature computation?” or “under what conditions does adaptive smoothing (variable EMA) help serve predictive queries effectively?” Without strong framing and precise claims, there is risk of a “kitchen-sink” approach. 

We advise a **cautious stance**: The project should aim to **characterize** and **understand** the trade-offs and interactions in the proposed system, rather than assume a win.  A defensible contribution might be: an analytical and empirical study of **batching vs feature freshness vs prediction accuracy**, or a **negative-result demonstration** showing when queue-pressure control fails or yields no benefit.  Any positive claim (e.g. “our scheme extends the quality/latency frontier”) must be backed by rigorous comparisons.  Unproven components include the MIMD batch policy, adaptive EMA control, and the claim that queue pressure is an adequate signal.  These assumptions require evidence.  In sum: the direction could lead to a valid result (positive or negative), but only with *tight focus* and strong controls. We remain uncertain whether it will yield publishable insights without narrowing or re-scoping, but it is worth a systematic examination rather than taking anything for granted. 

## B. Threats to Validity

| **Issue** | **Evidence / Observation** | **Affected Claim** | **Severity** | **Remedy** | **Independent Check** |
|---|---|---|---|---|---|
| **Temporal leakage**: Training/test overlap. | Legacy pipeline split history randomly, ignoring global time order. | Inflated accuracy, invalid CDF estimation. | **High**: Overlapping user histories leaks future labels into features. | Enforce strict time-based splits. Use “timestamp > threshold” for test. Disjoint user sets if needed. | Check that no training example has a timestamp ≥ earliest test label time. |
| **Label leakage**: Current-event in features and labels. | Features include “current observed event”; label counts purchases in (t,t+H] excluding same-timestamp. Hard to ensure exclusion. | Classifier may learn “if buy now, label likely soon”. | **High**: Introduces lookahead bias. | Exclude current-event from features (or ensure strict >t). Treat purchase at t as label=false. | Audit feature creation: ensure features use only data < t, and label computed only from > t. |
| **Censoring and dropouts**: Incomplete follow-up for users. | Follow-up “censored as unknown” not clearly handled. | Performance metrics skewed (false negatives etc.). | **Medium**: Users leaving may be mis-labeled negative. | Define evaluation only where full horizon data exists, or use survival analysis. Explicitly flag censored cases. | Report fraction of censored examples. Possibly hold out only users active for ≥H hours. |
| **Static vs streaming split**: Warm vs cold entities. | The platform has “no separate query stream” – effectively always one query per event. No plan for cold-start evaluation. | Overestimates performance (train and test share users and patterns). | **Medium**: Model may memorize user-specific patterns. | Perform both warm-start (allow same users) and cold-start (hold out some user IDs) evaluations. | Compare metrics for held-out users vs seen users. |
| **Non-independent sampling**: Key clustering. | Multiple events per user clustered; unknown mixing. | Variance underestimation if standard IID tests used. | **Medium**: Confidence bounds too optimistic. | Use hierarchical/block bootstrap (by user or time-blocks). Report intervals across user blocks. | Compute standard errors by resampling users or days. |
| **Class imbalance / rare positives**: <1% positives. | Taobao purchase events are sparse (e.g. 0.17% frauds in ULB). | Standard AUC or accuracy insensitive. | **Medium**: Need metrics (precision-recall AUC, etc.) and large sample for stable estimates. | Use stratified sampling to ensure enough positives. Plan large test sets. Use PR-AUC, F1. | Verify AUC confidence intervals; consider reporting precision at fixed recall. |
| **Batch control assumptions**: MIMD adaptation unproven. | Unlike TCP’s AIMD, using multiplicative increase/decrease (MIMD). | Potential oscillation or poor convergence. | **Medium**: Could destabilize throughput/latency. | Analyze stability theoretically (see section D). Experiment with alternative policies (e.g. fixed or AIMD) as ablation. | Plot time series of batch size and queue level. Look for limit cycles or divergence. |
| **EMA adaptation nonlinearity**: α changed by pressure. | If α changes in response to queue, EMA weight formula becomes nonlinear (state affects next state weighting). | Frequency-domain analysis invalid; possible unexpected dynamics. | **Medium**: Mischaracterization of filter behavior. | Treat α-update as control law, simulate or derive LTV analysis. Compare to linear predictions. | Provide examples where adaptive-α deviates from linear EMA (e.g. step response). |
| **Unsupported equivalences**: Span vs batch vs cadence. | Proposal implies possible trade-offs among EMA span, batch size, and update budget. | Misleading claims of “equivalence” across parameters. | **Low**: Conceptual confusion may lead to wrong baselines. | Keep these factors separate in analysis. Show counterexamples (sec D). | Demonstrate that e.g. doubling update rate does not match halving α in effect. |
| **Data quality issues**: Invalid domains/outliers in Taobao. | User noted timestamp outliers, invalid domain records. | Garbage in can skew feature stats and label alignment. | **Low**: If not cleaned, metrics and learned weights off. | Inspect data for anomalies. Filter or truncate extreme timestamps. Document data cleaning. | Provide summary stats (min/max times, behavior counts) and any cleaning done. |
| **Dataset authenticity/license**: Unclear provenance. | “Local hashes exist, terms unresolved.” | Risk of unauthorized use or data inconsistencies. | **Low**: Could restrict publishability but not technical. | Verify Kaggle/Tianchi terms for research use. Document data source (e.g. Kaggle link). | Attempt to find official data description. If closed, state uncertainty. |
| **Evaluation environment**: Hardware variability. | CPU threads on M3 Air, no known performance baseline. | Results may not generalize to real servers. | **Low**: Only affects absolute throughput numbers. | Focus on relative comparisons. Repeat experiments to account for timing jitter. | Measure CPU utilization, thread performance. Compare with simple work (e.g. empty loops) to gauge overhead. |
| **Software integrity checks**: Avoiding bypass or fake metrics. | Strict factory integrity (hashes, receipts) disallows data fudging. | Harder to “cheat” results, but requires honest implementation. | **N/A**: This is a guard, not a threat. | Ensure compliance. Use automated testing to catch schema violations. | Ensure final artifacts (hashes, logs) match code logs from pipeline runs. |

Each issue above should be clearly documented in the final writeup (e.g. in an appendix), with evidence (code audits or data profiles) where possible. Fixes should be implemented early so that any claims made later are on valid data/protocols.

## C. Primary-Literature Comparison Matrix

| **Method/System** | **Mechanism** | **Signal/Feedback** | **Workload Assumptions** | **Guarantees** | **Evaluation** | **Artifacts** | **Implications for AMOS** |
|---|---|---|---|---|---|---|---|
| **RALF** (feature store) | *Key-Value feature store with on-demand materialization.* Stores pre-computed features, serves them to queries. | None (static store). | Assumes large feature sets, read-heavy workloads (multiple models). | Fast access to features; no streaming updates considered. | Benchmarked on synthetic/small workloads. | Code (Ray-based), simulated workloads. | Highlights need for caching; but RALF **lacks streaming updates**. AMOS’s dynamic feature updates extend RALF’s static model. |
| **Clipper** (NSDI’17) | *Prediction-serving system with query caching, adaptive batching, ensemble models.* Batches queries up to latency targets. | Latency/throughput SLA feedback. Batch size tuned by measured latency. | Interactive ML queries (low QPS per model, strict tail-latency). | Up to 26× throughput improvement under latency bound. Tail-latency <= SLA. | Throughput and latency on ML models (image classification). | Open-source (Ray?), description only. | Demonstrates **adaptive batching**: AMOS uses similar feedback. Clipper’s success (26× speedup with tail-latency bound) sets a high bar. AMOS must ensure its MIMD scheme is at least as stable/effective. |
| **Biathlon** (VLDB’24) | *Approximate inference serving.* Dynamically loosens precision of heavy features (aggregation functions) to meet latency. | Model accuracy feedback: bound on permissible error. | Pipelines with expensive aggregation (e.g. counting over window). | Guarantees bounded accuracy loss by design. | Achieves 5–16× speedup on real pipelines, ~no accuracy drop. | Prototype code (slides, GitHub). | Conceptually similar to “approximate feature computation” in AMOS. Biathlon’s feedback is **per-feature error bound**, whereas AMOS uses queue-pressure. If AMS attempts similar approximation, it should follow Biathlon’s formal error guarantees. |
| **Adaptive-Window (ADWIN)** (Bifet et al., ECML 2007) | *Adaptive sliding window for change detection.* Grows/shrinks window based on observed distribution changes. | Statistical tests on recent vs older data. | Streaming data with concept drift. | Detects change when means differ beyond error bounds (with guarantees). | Synthetic and real data streams with known drift. | Open source in MOA toolkit. | ADWIN shows how “adaptive windowing” can track feature statistics. AMOS’s EMA adaptation is akin to variable window size. If pursuing **adaptive α**, borrow ADWIN’s rigor: derive statistical constraints under which to adjust α. |
| **AIMD Feedback Control** (Floyd & Jacobs et al.) | *Network congestion control.* Increase window additively, decrease multiplicatively on drop. | Packet loss signal. | Fluid/packet networks. | Fair convergence, stability (known TCP behavior). | Mathematical analysis + Internet deployments. | N/A (network protocols). | Clipper uses AIMD (additive inc) for fairness. AMOS uses *MIMD* (mult inc), which lacks proven stability. Guidance: prefer AIMD-like controls or justify MIMD mathematically. |
| **Hierarchical / Batch Scheduling** (e.g., TensorRT’s CUDA streams) | *Deep learning batching.* Schedules inference across GPU cores via grouping. | GPU utilization / latency. | Batch-friendly models (CNNs), high QPS. | Maximizes throughput on GPU; trade-off with latency. | Benchmarked on GPUs (CNN, RNN) workloads. | Libraries (TensorRT, TensorFlow Serving). | AMOS’s CPU-only environment means smaller batches; but GPU lessons apply: large batches boost throughput but harm latency. Compare to CPU: test small vs large batch trade-offs explicitly. |

Each entry above is grounded in the literature.  For example, Clipper and Biathlon demonstrate how feedback (latency or accuracy) is used to tune system behavior.  RALF shows feature-store baselines for data ingestion, and ADWIN (not cited) exemplifies rigorous adaptive-window methods.  These inform AMOS: we must specify how our mechanism (queue-pressure → batch/α) parallels or departs from known systems, and we must adopt similar evaluation rigor.

## D. Mathematical Analysis and Counterexamples

**EMA (Constant α):**  The simple exponential moving average is given by 
\[
s_t = \alpha\,x_t + (1-\alpha)\,s_{t-1}, \quad 0<\alpha<1,
\]
as in [60].  Expanding, the weight of input $x_{t-k}$ in $s_t$ is 
\[
w_k = \alpha\,(1-\alpha)^k,\quad k\ge 0.
\]
These weights sum to 1 (so it’s a valid filter).  Key derived properties: 

- **Average delay (mean age):**  $E[k] = \sum_{k=0}^\infty k\,w_k = \frac{1-\alpha}{\alpha}$.  In time units, the group delay of this filter is $(1-\alpha)/\alpha$.  For small $\alpha$, this is large, reflecting slow responsiveness. 

- **Half-life:**  Solve $(1-\alpha)^{k_{1/2}} = 1/2$.  This gives $k_{1/2} = \frac{\ln(1/2)}{\ln(1-\alpha)}$.  

- **Variance reduction:**  If input noise has variance $\sigma^2$, the output variance is $\Var[s] = \frac{\alpha}{2-\alpha}\,\sigma^2$.  Equivalently, one can define a **variance-equivalent window length** $N$ by $\sigma^2/N = \Var[s]$, giving 
\[
N \;=\; \frac{2-\alpha}{\alpha}\;\approx\;\frac{2}{\alpha}\quad (\alpha\ll1).
\]
Many libraries define “span” as $2/\alpha - 1$, which is essentially twice the mean age.

**EMA (Variable α):**  If $\alpha$ changes at each update, e.g.\ $\alpha_t$, then  
\[
s_t = \alpha_t x_t + (1-\alpha_t)\,s_{t-1}.
\]
Unfolding yields 
\[
s_t = \alpha_t x_t + (1-\alpha_t)\alpha_{t-1} x_{t-1} + (1-\alpha_t)(1-\alpha_{t-1})\alpha_{t-2} x_{t-2} + \cdots.
\]
In general the weight on $x_{t-k}$ is 
\[
w_k = \alpha_{t-k}\,\prod_{i=0}^{k-1}(1-\alpha_{t-i}),
\]
with $\prod_{i=0}^{-1}(\cdot)=1$ by convention for $k=0$.  Note this depends on the entire history of $\alpha$ values.  If $\alpha_t$ is determined by some signal (e.g. queue pressure), the process is *linear time-varying* when $\{\alpha_t\}$ is fixed, but becomes **nonlinear** if $\alpha_t$ depends on $s_t$ itself or on $x_t$ (feedback).  Thus, any analysis assuming time-invariance (like frequency response) is invalid.  For example, a step change in $\alpha$ causes a *non-stationary* response.

**Counterexample (EMA vs Event Timing):**  Consider two keys with infrequent events.  Using an event-count EMA gives the same update rule regardless of clock time.  If key A has 1 event per hour and key B has 10 events per hour, then an EMA with $\alpha$ defined per-event effectively “remembers” much more actual time for A than for B.  For example, after 3 events, A’s EMA covers 3 hours, B’s covers 0.3 hours.  Thus event-based EMA **does not correspond** to a fixed time-scale memory, and one cannot treat $\alpha$ as “time-decay” without adjusting for event rates.  This is a limitation when arrival rates vary.  (A remedy could be time-decay EMA, $s_t=\alpha x_t+(1-\alpha^{\Delta_t})s_{t-1}$ where $\Delta_t$= time gap.)

**Feedback adaptation (linear vs nonlinear):**  Suppose $\alpha_t$ is chosen by a controller observing queue length $q_t$, e.g. $\alpha_t = f(q_t)$.  Then $s_t$ depends on past $s_{t-1},q_{t-1},\dots$.  The system $(x_t,q_t)\to s_t$ is not a simple linear filter: the superposition principle fails.  For instance, if queue spikes cause $\alpha$ to drop suddenly, the same input stream $x_t$ can yield different $s_t$ trajectories depending on past $q_t$.  Hence analyses like frozen-time frequency response (treating $\alpha$ as constant) are **not generally valid** once adaptation is on.  

**EMA span vs publication cadence vs batching:**  These are **not interchangeable**.  The EMA **span** (memory) is set by $\alpha$.  The **publication cadence** $U$ (e.g. how often features are recomputed) and **batch size** $B$ affect how many updates are done per wall-clock time but do not change $\alpha$’s effect per update.  For example, doubling $U$ (updating twice as often) with fixed $\alpha$ does *not* halve the effective span: it just outputs two updated EMA states in the same time.  One might mistakenly think that more frequent updates or larger batches mimic a different $\alpha$, but mathematically the EMA recursion is the same per event.  Indeed, one can create a counterexample: feed identical data at half the frequency (doubling idle time) and apply the same $\alpha$; the resulting $s_t$ (sampled at events) is identical, even though the calendar time spanned is double.  Thus, **only $\alpha$ controls time-memory**, not $U$ or $B$.

**Batching control (delay & hysteresis):**  The inherited MIMD rule (multiply batch size up or down by fixed factors) is a form of *discrete feedback*.  If the queue never empties, batches will shrink to minimum; if queue is idle, batches grow to maximum.  Without any “additive” component, MIMD can oscillate.  For example, if thresholds are crossed quickly, batch size may flip-flop.  A more stable design uses **hysteresis** (different thresholds for growing vs shrinking) or smoother controllers (PID control).  A simple counterexample: suppose the queue signal is a square wave (on/off) at period comparable to the sampling window.  MIMD can overshoot: each cycle it multiplies batch by factor $>1$ then $<1$, which may not exactly cancel, causing drift.  In contrast, AIMD (as in TCP) has well-known convergence properties, but MIMD does not guarantee stability.  We therefore treat the current rule as a *heuristic* and will test its behavior empirically rather than assume any control-theoretic guarantee.

## E. Causal Task, Target Architecture, and Measurement Contract

**Prediction Task:**  From the Taobao logs, the natural task is **next-purchase prediction**.  At each event time $t$ for a user, given the user’s features up to (but excluding) $t$, predict whether the user will make a purchase in the *next $H$ hours* (strictly after $t$ and up to $t+H$).  We set $H=2$ hours (provisionally) as suggested, but will validate later.  Same-timestamp purchases are excluded (so a purchase exactly at $t$ is not counted).  Each event thus generates a binary label (purchase in $(t,t+H]$ or not), unless the user’s log ends less than $H$ hours after $t$, in which case the label is *censored* (unknown).  We must handle this censoring explicitly.  A simpler approach is to discard events too near the end of a user’s history; more formally, this is a survival analysis setting.  

**Evaluation Splits and Protocol:**  We will impose a **time-based split**.  E.g. pick a cutoff time $T_{\text{cut}}$ near the end of the available data.  All events (and their features) with timestamps $<T_{\text{cut}}$ go to training; those $\ge T_{\text{cut}}$ to testing.  Crucially, no user appearing in test should have any events in train *after* $T_{\text{cut}}$, so the training and testing periods are temporally disjoint.  We can allow users to appear in both sets if their events cross $T_{\text{cut}}$, but we must be careful about “warm-start” leakage: features for user in test period should only use their train-period data (not vice versa).  To be rigorous, we will do two modes: (a) **Warm evaluation** – users are not separated, but predictions are always on *future* events; (b) **Cold evaluation** – hold out a set of user IDs entirely (their entire history) for testing, to simulate new users.  Comparing (a) and (b) will show how well models generalize to unseen keys.  

**Feature Causality:**  All features must be computable from events strictly before $t$.  For example, the “Engagement EMA” (which weights prior clicks, carts, favorites, buys by [1,3,2,5]) will be updated up to time $t^-$.  We will verify in code that $s_{t-}$ does not include the event at $t$.  

**Temporal Warm-Start vs Cold:**  For warm-start, one can initialize a user’s feature state at the start of training (e.g. assume zero history) and run the streaming pipeline up to $T_{\text{cut}}$ to get warm-state for test.  For cold-start, we must simulate a true new user with *no history*: drop all their training events and only use a default start state at test time.  Evaluation metrics (AUC, etc.) should be reported separately for warm vs cold cases to avoid confusing them.  This distinguishes the model’s adaptation to recurring users from its one-shot performance on new users.

**ULB Dataset (Credit Fraud):**  The ULB (kaggle credit card fraud) data is **not a streaming key-based workload**. It is a flat table of anonymous transactions (no user identifier), taken over 2 days. It has very imbalanced classes (492 frauds of 284,807 total). It cannot naturally support “feature publication” by key, since there is no evolving state per cardholder (identities are not provided). Thus **we cannot legitimately claim to use it for key-wise streaming experiments**. We can only use it as a static classification benchmark: e.g., for model testing under batch setting. If the project claimed ULB as a “keyed serving” case, that claim is invalid. Our plan: either drop ULB from the streaming claims, or restrict its role to a sanity check on binary classification (ensuring our pipeline can at least match known baselines on a well-known dataset).  

**Data Sources and Terms:**  The Taobao dataset comes from Alibaba’s competition (Tianchi/Kaggle) and is widely used (BetaRecSys docs). We assume research use is allowed (it was free to download in competition). The ULB data is Kaggle’s “Credit Card Fraud Detection” with PCA features. We will cite these sources for factual details.  We should not **invent cardholder IDs** in ULB; rather, we either treat each row independently or align by trivial features (like time).  

**Target Architecture:**  The next-architecture plan suggests separating the following components: 
- **Feature update stream:** asynchronously update user feature-state on each new event.  
- **Feature publication budget (cadence $U$):** schedule how often to publish/refresh features (might decouple from events).  
- **Inference batch size ($B$):** number of queries grouped for scoring.  
- **EMA gain ($\alpha$):** weight of new events in exponential smoothing.  
- **Query processing:** receiving prediction queries (could be same as events stream or separate).  
We propose to implement at least a **two-stage pipeline**: (i) event ingestion and state update; (ii) inference serving.  Initially they may run in one process, but logically they are separate.  We will record timestamps to measure queue lengths, processing times, and feature freshness (e.g. how long ago each feature was updated).  

**Measurement/Accounting:**  For any experiment, we will log for each event/query: arrival time, admit time, finish time, batch size, queue length, features used.  We will measure tail latency (e.g. 95th percentile end-to-end time), throughput (events/sec), CPU usage, memory use, and model performance (ROC-AUC, PR-AUC).  Since work is CPU-bound, wall-clock time (from ingestion to output) is key.  We also record “freshness”: how much time has passed since last feature update before scoring.  This allows analysis of the freshness-vs-latency trade-off.

This contract (temporal splits, state updates, logging) ensures *no label leakage* and *clear causal timing*.  We will write unit tests to enforce that no feature uses future info (e.g. feature for event at time $t$ only depends on events $<t$).  Data integrity checks (e.g. hash of input data) will ensure reproducibility.

## F. Baseline/Ablation Matrix and Experimental Protocol

We will consider the following models/policies:

- **Simple static features (Baseline):** A logistic regression (or small neural net) trained on non-adaptive features.  For example, use static window counts or EMAs with fixed $\alpha$ as features, but do *not* adjust $\alpha$, $B$, or $U$.  This is a minimal benchmark.  
- **Adaptive-policy model:** The same learning algorithm, but with the dynamic feature/batching policies under test (queue-driven $B,\alpha,U$).  Critically, for a fair comparison we will run both models on the **same sequence of prediction queries**. Since AMOS schedules or drops some work under high load, we must ensure the baseline gets the same queries and computational resources. One way: simulate offering the same event arrival process to both (if one system rejects an event to control load, the other should also drop it).  This ensures paired comparison.  
- **Retrained vs frozen:** We must distinguish (1) retraining the model after each policy change vs (2) using a model trained under one fixed policy.  For example, we can train one logistic model on features extracted by the *baseline policy*, and evaluate it on data collected by the *adaptive policy*, and vice versa.  This checks if adaptive features require retraining or can reuse the same model.  Another alternative: train separate models for each policy scenario (fairer but more costly).  

- **Out-of-sample reference:** Use a classic "no-feature" predictor as a lower bound (e.g. predict purchase at overall base rate). Also consider a “historical average” model that predicts probability = historical purchase frequency per user (requires long past, but still an out-of-sample concept).  

- **Hindsight/oracle:** We can define an **oracle feature**: e.g. count of purchases in the interval $(t,t+H]$ (the label itself) and see how well a predictor could do.  While not implementable, this sets an upper bound on achievable AUC (which can be 1.0 trivially).  A more realistic oracle: all current event features plus knowledge of a hidden latent segmentation (if any).  These oracles help interpret whether, for instance, an AUC of 0.6 is near-optimal or very far.  

We will **tune hyperparameters** (regularization, threshold, etc.) for each model using the same budget (e.g. grid search up to X runs) on a validation set.  All models must have equal training data and same model capacity.  For example, if baseline uses 100 gradient steps, the adaptive policy model also uses 100 steps.  If deep nets are used, ensure both policies get identical network architecture and training epochs.  

We also will attempt to **reproduce or adapt techniques** mentioned: 
- **RA**LF-inspired caching: if time permits, test a strategy that caches only a subset of features in memory (as in the RALF caching work) and evicts old entries (e.g. LRU) instead of our EMA strategy.  
- **Clipper-style AB** (already part of adaptive batching). 
- **ADWIN**: test a version where we detect drift in each feature stream and reset EMA, to see if pure statistical methods outperform queue-feedback.  

For each variant, we will measure:
- Prediction quality (AUC, precision@k).  
- Latency metrics (mean/95% response time for features and inference).  
- Throughput (events/sec processed).  
- Feature freshness (average age of data).  

The **baseline/ablation matrix** can be tabulated (rows = scenarios, columns = model, feature policy, batch policy, performance metrics).  We will specifically ensure: “same query coverage” (same test keys/times) and “same resources” (if needed, throttle baseline to match CPU used by adaptive run for a fair time-comparison).

Statistical protocol: We will treat each user (or day) as a block and do paired tests (e.g. Wilcoxon signed-rank) between policies to assess significance in AUC. We will use *95% confidence intervals* rather than single-run values.  For noninferiority, we specify a margin (e.g. “adaptive policy within 1% AUC of baseline”) and test accordingly.  We will explicitly report cases of equivalence (Δ < margin) vs positive difference vs inconclusive (when CI spans zero effect).  

## G. Implementation Roadmap (Staged, with Gates)

1. **Data Validation & Preprocessing:** (Gate: Clean datasets)  
   - Profile Taobao CSV for anomalies (check timestamps globally sorted, remove impossible events, fix missing values).  
   - Ensure label construction is correct (no use of future, handle censoring).  
   - Validate ULB data (confirm 284,807 rows, 492 frauds).  
   *Stop/Go:* If data irregularities (e.g. time gaps or corrupt rows) persist or licenses unclear, reconsider using the dataset.

2. **Baseline Framework (Factory Integration):** (Gate: Correct static pipeline)  
   - Use the provided software factory to implement a static pipeline: streaming ingestion (but without adaptation), fixed batch size and fixed α.  
   - Confirm event-by-event scoring matches expectations (test on synthetic data).  
   - Add logging of all required metrics (timestamps, queue length, features).  
   *Gate:* Verify output matches simple offline results (e.g. produce same scores as batch logistic regression). If static pipeline fails basic tests, fix before proceeding.

3. **Feature Computation Worker:** (Gate: Verified features)  
   - Implement the seven Taobao features (Engagement EMA, log1p counts, gap features, etc.) and the ULB features (if any).  
   - Unit-test feature computations on a few synthetic user histories (with known results).  
   - Integrate with the ingestion worker (features keyed by user).  
   *Gate:* Check that features update correctly at each event and that label timing matches definitions. Compare on a tiny sample with a reference script.

4. **Adaptive Control Logic:** (Gate: Functional adaptivity)  
   - Implement feedback loop: measure queue pressure at each batch boundary, adjust batch size $B$ and EMA α accordingly (as described). Also implement $U$ control if specified.  
   - Validate that under artificial queue signals (e.g. simulated high load), $B$ decreases and α maybe adjusts.  
   - Provide a debug mode to fix $B,\alpha$ to constant values.  
   *Gate:* Show that controller reacts qualitatively correctly (e.g. in low load B grows, high load B shrinks). Check no crashes or oscillations from zero/overflow.

5. **Prediction/Model Worker:** (Gate: Model integration)  
   - Connect the pipeline to the model-training and scoring module of the factory (e.g. logistic regression or sklearn).  
   - Ensure seeds are fixed for comparability, and that metrics are computed by user-block.  
   *Gate:* Run an end-to-end with baseline (no adaptivity) and verify that metrics (e.g. AUC) are reasonable (e.g. >0.5, not NaN).

6. **Experiment Automation & Logging:** (Gate: Reproducible experiments)  
   - Script batch experiments varying policies (static vs adaptive vs others). Use unique seed for each run.  
   - Record all configurations and random seeds for reproducibility.  
   - Automate statistical analysis (paired tests, CI).  
   *Gate:* Re-run a known experiment multiple times; confirm low variance under seed control. Check analysis code.

7. **Scaling and Stress Testing:** (Gate: Resource usage check)  
   - Measure CPU, memory usage under expected loads. Adjust code if exceeding hardware (e.g. use streaming/batching to not load entire dataset).  
   - If needed, sample the data (e.g. random subset of users) to fit memory, while maintaining statistical representativeness.  
   *Gate:* Ensure experiments finish in reasonable time (<2 hours per run). Optimize or downsample if not.

8. **Final Experiments and Analysis:** (Gate: Conclusive results)  
   - Conduct full designed experiments (e.g. multiple train/test splits, policy comparisons).  
   - Populate threat table (B) and literature matrix (C).  
   - Derive final conclusions.  

At each gate, we explicitly verify assumptions (e.g. no label leakage, controller behavior) before proceeding. If a gate fails (e.g. static baseline performs worse than chance), we debug rather than advance. This avoids building complexity on a flawed foundation.

**Claims requiring more resources:** If results show tiny differences or heavy noise, we may need larger datasets or more runs. For example, rare events might need all 100M rows; if that cannot fit, we would down-sample with caution. We do **not** plan on GPU use, as the code is CPU-bound; no specialized instrumentation (like energy profiling) is needed per instructions.

## H. Publication Plans for Outcomes

- **Positive Results:**  If we find a clear regime where adaptive batching and feature tuning *significantly* improve the latency-vs-accuracy tradeoff, the contribution could be a **systems paper** (e.g. **USENIX ATC/SysML** or an ML systems track) focusing on the new mechanism.  We would present the system design, analytical insights (from sec D), and end-to-end gains.  Required evidence: robust gains in throughput or latency under controlled workloads, with ablation to show each component’s benefit (e.g. batch adaptation vs α adaptation).  Comparison to fair baselines (as in C-F) is crucial.  Data and code release would be expected (artifact avail.).

- **Negative/Null Results:**  If adaptive control shows little or no advantage, or even degrades accuracy, the contribution might be a **negative results paper** in a venue like **PODS/ICDE short papers** or an ML workshop.  It would highlight the rigorous evaluation and why the intuition failed (e.g. “Backpressure is a poor signal for freshness,” with evidence).  Requirements: solid analysis (possibly more emphasis on section D and threat table B), careful debugging logs to prove the experiment was fair, and suggestions for alternate directions.  Even if not accepted to top venues, such a write-up could be valuable as a technical report or data-ops conference (e.g. IEEE DAWAK, LIDTA). 

- **Inconclusive:**  If we find that any differences are within noise or dependent on fragile conditions (e.g. only works for this dataset), the outcome might be a **benchmark or data artifact paper** (e.g. on dataset quirks or a benchmark of streaming evaluation methods).  We could still target workshops or journals like *Data Mining and Knowledge Discovery (DMKD)* for analysis results.  

In all cases, we will aim to align with calls for artifact evaluation and reproducibility (e.g. ACM’s open artifacts policy).  Before choosing a venue, we will match our emphasis: systems/architecture vs experimental analysis.  We will **not guarantee acceptability** anywhere; the goal is to present our findings honestly.

## I. Unresolved Questions

1. **Cadence vs Load Scheduling:**  How exactly should `U` (feature publication rate) be controlled? Should it adapt like $B$?  
2. **EMA Initialization:**  How to handle new users’ EMA state? Zero? Warm-start from population average?  
3. **Multiple Feedback Loops:**  If we adapt both $B$ and $\alpha$, they may interact (e.g. small $B$ = less frequent $\alpha$ updates). How to coordinate?  
4. **Alternative Signals:**  Is queue pressure the best feedback? Would queue *arrival rate* or *processing latency* be better?  
5. **Statistical Tests:**  Which nonparametric test is most appropriate given our blocking? Wilcoxon? Bootstrap?  
6. **Evaluation Horizon:**  Is 2 hours the right $H$ for Taobao? How sensitive are results to this choice?  
7. **Adversarial Workloads:**  Should we test worst-case patterns (bursty keys) or stick to the empirical distribution? If adversarial, how?  
8. **Cold Start Extent:**  In practice, how many cold-users should we simulate for a meaningful evaluation?  

We will seek clarification on these (especially the first two) from the project sponsor before diving into implementation.  They may refine the hypotheses (e.g. if they intended a different feedback design). 

**Sources:** We have cited relevant prior work above, and all claims in this report are either supported by these sources or by clear derivation. Any statements without citations are our original analysis or plan. 

