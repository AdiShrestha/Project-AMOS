# Dynamic Rules

Factory Version

1.0.1

---

# Purpose

Dynamic Rules are the Factory's long-term memory.

Unlike the Constitution, which contains permanent universal engineering principles, Dynamic Rules contain proven improvements discovered through real projects.

Every rule exists because evidence showed it repeatedly prevented failures.

Ideas, opinions, and speculation never belong here.

This file is reusable across every project.

---

# Philosophy

The Constitution defines how every AI should behave.

Dynamic Rules define what the Factory has learned.

The Constitution changes very rarely.

Dynamic Rules evolve continuously.

Only evidence changes the Factory.

---

# Scope

Dynamic Rules may contain

- promoted engineering practices
- deterministic gate requirements
- workflow refinements
- proven prevention strategies
- repeated failure patterns
- reusable verification improvements

Dynamic Rules never contain

- project architecture
- project specific knowledge
- implementation details
- research methodology
- project reports
- temporary experiments

Those belong elsewhere.

---

# Rule Categories

Every Dynamic Rule belongs to exactly one category.

## G

Gate

A deterministic validation that can be automated.

Examples

- required verification script exists
- frozen files unchanged
- repository clean
- required report generated

---

## V

Verification

Improves correctness verification.

Examples

- verify generated metrics against raw artifacts
- compare adjacent evidence before reporting
- independent verification required

---

## W

Workflow

Improves execution efficiency.

Examples

- execution order refinement
- contract preparation improvements
- review timing improvements

---

## P

Preservation

Protects engineering knowledge.

Examples

- archive strategy
- logging improvements
- reproducibility enhancements

---

## R

Reporting

Improves engineering reports.

Examples

- raw evidence formatting
- provenance recording
- report consistency

---

# Rule Format

Every rule follows exactly the same structure.

```
Rule ID

Category

Status

Promoted From

Evidence

Description

Reason

Implementation

Verification

Date Added

Projects

Notes
```

Nothing else should be added.

---

# Rule Status

Every rule has one status.

ACTIVE

The rule is currently enforced.

---

PROPOSED

Evidence exists but promotion has not yet been approved.

---

DEPRECATED

Rule no longer recommended.

Never delete it.

Record why it became obsolete.

---

SUPERSEDED

Replaced by another rule.

Reference the replacement.

---

# Promotion Pipeline

No rule is promoted because it sounds useful.

Promotion always follows

```
Observation

↓

Repeated occurrence

↓

Evidence collected

↓

Root cause identified

↓

Candidate rule written

↓

Applied experimentally

↓

Improvement confirmed

↓

Human approval

↓

Promotion

↓

ACTIVE
```

Skipping any stage is not allowed.

---

# Promotion Requirements

A rule should normally satisfy all of the following.

- observed in multiple situations
- addresses root cause
- clearly prevents recurrence
- reusable across projects
- does not duplicate Constitution
- improves deterministic behavior whenever possible

---

# Evidence Requirements

Promotion evidence should include

- affected projects
- contracts involved
- failure frequency
- improvement observed
- verification method

If evidence cannot be presented

↓

The rule remains PROPOSED.

---

# Rule IDs

Rule IDs are permanent.

Format

```
D-001
D-002
D-003
```

Numbers are never reused.

Deleted rules keep their IDs.

---

# Rule Lifecycle

```
Observation

↓

Candidate

↓

PROPOSED

↓

ACTIVE

↓

SUPERSEDED

↓

ARCHIVED
```

Rules are never deleted.

Historical knowledge is valuable.

---

# Relationship to Constitution

Dynamic Rules never override the Constitution.

If a conflict exists

↓

The Constitution wins.

Dynamic Rules extend the Constitution.

They do not replace it.

---

# Relationship to Gatekeeper

Whenever possible

A Dynamic Rule should eventually become

- deterministic
- automated
- enforced by Gatekeeper

If automation is impossible

The rule remains guidance.

---

# Relationship to Invariants

Dynamic Rules

Universal.

Reusable.

Factory knowledge.

---

Invariants

Project specific.

Never promoted directly into Dynamic Rules.

Only reusable engineering lessons qualify.

---

# Relationship to Evolution Logs

The evolution folder records observations.

Dynamic Rules record conclusions.

Example

```
Evolution

Observed repeated accidental edits to frozen files.

↓

Dynamic Rule

Always verify frozen file hashes before commit.
```

Evolution records history.

Dynamic Rules record knowledge.

---

# Rule Review

Review occurs

- after chunk completion if required
- after project completion
- during Factory retrospectives

Review does not imply promotion.

Promotion requires evidence.

---

# Rule Retirement

A rule may become obsolete.

It must never be deleted.

Instead

Status becomes

```
SUPERSEDED
```

or

```
DEPRECATED
```

Reason must be documented.

---

# Rule Quality

Every Dynamic Rule should

- reduce future mistakes
- reduce AI decision making
- improve determinism
- simplify the workflow
- justify its own maintenance cost

Rules that create more work than value should not be promoted.

---

# Example Rule

```
Rule ID

D-001

Category

Gate

Status

ACTIVE

Promoted From

Three independent projects

Evidence

Repeated modification of frozen files.

Description

Verify hashes of every frozen file before commit.

Reason

Prevented accidental edits across multiple projects.

Implementation

Gatekeeper compares stored hashes.

Verification

Automatic.

Date Added

2026-07-14

Projects

3

Notes

First promoted Dynamic Rule.
```

---

# Factory Principle

The Factory evolves through evidence.

Every Dynamic Rule should move engineering one step closer to

```
Human Memory

↓

AI Memory

↓

Documentation

↓

Automation

↓

Deterministic Enforcement
```

The ideal Dynamic Rule eventually disappears into automation.

When the Factory no longer needs to remember a lesson because it is enforced automatically, the Factory has improved.

---

## Rule D-001

**Category:** V (Verification)

**Status:** ACTIVE

**Promoted From:** Two independent audit passes on the prior (pre-Factory)
BPFeat project.

**Evidence:** In the first audit pass, at least seven sections presented a
Verdict directly contradicted by the raw command output shown in the same
section (e.g., raw output proving a required file did not exist, verdict
claiming PASS with fabricated supporting reasoning). Root cause: verdicts
were assembled from a pre-written lookup structure independent of live
command execution. This recurred, in a different form, in a second audit
pass that used real live execution but silently substituted fabricated
checklist items for real ones from turn 3.4 onward, again producing
verdicts disconnected from the guide they claimed to satisfy.

**Description:** Every stated Verdict (PASS/FAIL/CONDITIONAL) in any
generated report must have a quoted, adjacent block of raw evidence
(command output, file diff, log excerpt) directly above it in the same
document, within a short distance, that a reader can point to as the
specific justification for that verdict.

**Reason:** A verdict with no adjacent evidence is unfalsifiable by
inspection — it can silently diverge from reality with no visible warning
sign, exactly as happened twice in this project's history.

**Implementation:** Encoded as `check_verdict_evidence_adjacency()` in
`gatekeeper.py` v1 (see Phase A.3 above). This automatically flags any
report containing a Verdict line with no evidence-referencing text in the
15 lines immediately preceding it.

**Verification:** Automatic, via Gatekeeper.

**Date Added:** 2026-07-17

**Projects:** 1 (BPFeat, pre-Factory; this Factory instance is the first to
encode it as enforcement)

**Notes:** This rule exists specifically because a *process* document
telling an AI agent "be careful to make verdicts match evidence" was tried
twice and failed twice. Moving the check into deterministic code, per
Constitutional principle EP-002 (Determinism Over Interpretation), is the
direct fix.