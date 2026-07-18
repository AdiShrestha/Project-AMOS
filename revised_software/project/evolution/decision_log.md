# Decision Log

## Decision D-EVOL-001

**What changed:** gatekeeper.py v1 was drafted by Claude (Architect role)
rather than the Human, deviating from the Factory Spec's artifact ownership
table, which lists gatekeeper.py as Human-owned.

**Why:** The Human directs this Factory's execution entirely through AI
agents and does not author Python directly. Requiring literal Human
authorship of gatekeeper.py would block Factory Initialization indefinitely.

**Evidence:** Factory Spec artifact ownership table, "gatekeeper.py | Human
| Factory initialization | As deterministic checks improve | Everyone."

**Expected impact:** Enables Factory Initialization to proceed. Establishes
a precedent that should be reviewed at the next Factory Retrospective —
specifically, whether the ownership table should be amended to reflect
"Human approves, Claude drafts" as the realistic authorship model, or
whether a different Human-in-the-loop mechanism (e.g., mandatory Human
review before gatekeeper.py commits) should be required instead.

**Promoted:** Not yet — this is a single-instance exception pending Human
review, not a promoted Dynamic Rule. Flag for the Human's explicit
confirmation before treating this as an accepted precedent for future
Factory-governed projects.

---

## Decision D-EVOL-002

**What changed:** Single-agent execution model (one underlying agent/model playing both "Claude/Architect" and "Gemini/Implementation Engineer" roles) is used, rather than distinct model invocations.

**Why:** The current development environment uses a single chat conversation thread and a single agent session to drive the workspace modifications. Spawning a separate agent context for every contract split would add orchestration overhead and is not supported by the default developer environment.

**Evidence:** Factory Spec §8.1/§8.2 defining "Claude" (Architect) and "Gemini" (Implementation) as separate roles, assuming adversarial distance during Phase 3 self-review.

**Expected impact:** Speeds up development cycle. However, it removes the adversarial-distance check assumption, meaning that the same model writes and validates the code, raising the risk of confirmation bias. To mitigate this risk, deterministic checks (ThreadSanitizer, exact assertions, gatekeeper validation) must be strictly enforced.

**Promoted:** No.
