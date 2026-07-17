# Gatekeeper Specification

Factory Version

1.0.1

---

# Purpose

Gatekeeper is the Factory's deterministic enforcement engine.

Its purpose is to verify that every completed contract satisfies all deterministic requirements before work is accepted.

Gatekeeper never performs AI reasoning.

Gatekeeper never evaluates software quality.

Gatekeeper only determines whether predefined, objective conditions are satisfied.

---

# Philosophy

The Factory prefers deterministic verification over AI judgement whenever possible.

Every responsibility moved from AI reasoning into Gatekeeper reduces future ambiguity.

Gatekeeper is the final automated checkpoint before work is considered complete.

---

# Responsibilities

Gatekeeper is responsible for

- repository validation
- artifact validation
- execution validation
- integrity verification
- deterministic rule enforcement
- contract completion verification

Gatekeeper is not responsible for

- code review
- architecture review
- design decisions
- implementation quality
- research evaluation
- writing reports
- generating fixes

---

# Inputs

Gatekeeper reads

```
constitution.md

factory_spec.md

dynamic_rules.md

bootstrap_manifest.yaml

execution_manifest.yaml

contract_report.md

chunk_report.md

verification scripts

repository state

git metadata
```

Only deterministic artifacts are consumed.

---

# Outputs

Gatekeeper produces

```
PASS
```

or

```
FAIL
```

It also generates

```
gatekeeper_report.md
```

containing

- executed checks
- passed checks
- failed checks
- warnings
- execution time
- Factory version
- repository state

---

# Execution Order

Gatekeeper always executes in the same order.

```
Bootstrap Validation

↓

Repository Validation

↓

Manifest Validation

↓

Artifact Validation

↓

Verification Scripts

↓

Report Validation

↓

Dynamic Rule Validation

↓

Repository Integrity

↓

Final Decision
```

Execution order is fixed.

---

# Bootstrap Validation

Verify

- bootstrap_manifest.yaml exists
- manifest is valid
- required directories exist
- required files exist

Failure

↓

STOP

---

# Repository Validation

Verify

- repository is initialized
- required directories exist
- required project files exist
- chunk structure is valid

Missing artifacts

↓

FAIL

---

# Manifest Validation

Verify

- execution_manifest.yaml exists
- dependency order valid
- required contracts listed
- verification scripts declared
- reports declared

Invalid manifest

↓

FAIL

---

# Contract Validation

Verify

- contract exists
- contract completed
- Definition of Done satisfied
- Stop Condition not violated

Failure

↓

FAIL

---

# Frozen File Validation

Verify

- every frozen file hash matches
- no unauthorized modification occurred

Hash mismatch

↓

FAIL

---

# Allowed File Validation

Verify

Only Allowed Files were modified.

Unexpected modification

↓

FAIL

---

# Verification Script Validation

Verify

- required verification scripts exist
- scripts executed successfully
- exit code equals zero

Non-zero exit code

↓

FAIL

---

# Report Validation

Verify

Required reports exist.

Required sections exist.

Mandatory evidence exists.

Missing report

↓

FAIL

---

# Dynamic Rule Validation

Verify

Every ACTIVE Dynamic Rule that can be checked deterministically.

Examples

- required files exist
- provenance recorded
- required reports generated
- frozen hashes verified

Rules requiring judgement are skipped.

---

# Repository Integrity

Verify

- clean working tree
- no merge conflicts
- no unresolved files
- no temporary artifacts
- no forbidden files

Failure

↓

FAIL

---

# Bootstrap Compliance

Verify repository matches

```
bootstrap_manifest.yaml
```

Missing required artifact

↓

FAIL

Unexpected files

↓

WARNING

Unknown files are never deleted automatically.

---

# Git Validation

Verify

- repository clean
- commit possible
- required tag exists if specified
- current commit recorded

History is never rewritten.

Gatekeeper never performs Git operations.

---

# Verification Principles

Gatekeeper verifies only facts.

Never interpretations.

Examples

Allowed

```
File exists

Exit code equals zero

Hash matches

Report exists

Directory exists
```

Forbidden

```
Architecture is good

Research is correct

Code looks clean

Algorithm is elegant
```

---

# Failure Policy

Any FAILED check blocks completion.

Gatekeeper never ignores failures.

No partial pass exists.

---

# Warning Policy

Warnings indicate

- non-critical inconsistencies
- unexpected artifacts
- deprecated structures
- obsolete reports

Warnings never override failures.

---

# Exit Codes

```
0

PASS
```

```
1

Bootstrap Failure
```

```
2

Repository Failure
```

```
3

Manifest Failure
```

```
4

Contract Failure
```

```
5

Verification Failure
```

```
6

Report Failure
```

```
7

Dynamic Rule Failure
```

```
8

Repository Integrity Failure
```

```
9

Unexpected Internal Error
```

Exit codes are stable across Factory versions whenever practical.

---

# Gatekeeper Report

Every execution generates

```
gatekeeper_report.md
```

Minimum contents

- Factory version
- project name
- chunk
- contract
- execution timestamp
- checks executed
- checks passed
- checks failed
- warnings
- execution duration
- exit code
- final status

---

# Extensibility

New deterministic checks may be added over time.

Every new check must

- be deterministic
- have measurable inputs
- produce a boolean result
- avoid AI reasoning

---

# Relationship to Dynamic Rules

Whenever an ACTIVE Dynamic Rule becomes fully deterministic

↓

Implement it inside Gatekeeper.

Dynamic Rules are knowledge.

Gatekeeper is enforcement.

---

# Relationship to Constitution

The Constitution defines behavior.

Gatekeeper enforces only the portions that can be verified objectively.

Behavior requiring judgement remains outside Gatekeeper.

---

# Performance

Gatekeeper should

- minimize execution time
- avoid unnecessary filesystem scans
- reuse existing verification artifacts when safe
- fail fast on critical errors

Correctness always takes priority over speed.

---

# Security

Gatekeeper must never

- modify project files
- rewrite Git history
- execute destructive commands
- delete artifacts
- overwrite reports

Gatekeeper is read-only except for generating

```
gatekeeper_report.md
```

---

# Design Philosophy

Gatekeeper exists to eliminate preventable human and AI mistakes through deterministic verification.

The long-term goal of the Factory is that every reusable engineering lesson eventually becomes

```
Observation

↓

Dynamic Rule

↓

Gatekeeper Check

↓

Automatic Enforcement
```

When a mistake becomes impossible instead of merely unlikely, the Factory has improved.