# AI Software Factory v1.0.1
# Engineering Specification (Revised)

> **Document Version:** 1.0.1 (Revised)
>
> **Status:** Draft
>
> **Part:** 1/12

---

# Table of Contents

- 1. Introduction
- 2. Philosophy
- 3. Design Goals
- 4. Core Principles
- 5. Engineering Principles
- 6. Definitions
- 7. Factory State Machine
- 8. Roles and Responsibilities
- 9. Decision Ownership
- 10. Repository Architecture Overview

---

# 1. Introduction

## 1.1 Purpose

The AI Software Factory is a deterministic software engineering framework for developing high-quality software using multiple AI systems working under strict engineering constraints.

Unlike conventional AI workflows, the Factory explicitly separates planning, implementation, verification, review, and evolution into independent responsibilities. Every responsibility has a single owner, clearly defined inputs, expected outputs, and objective acceptance criteria.

The Factory is designed to make software engineering predictable, reproducible, auditable, and scalable across projects.

The Factory itself is a reusable engineering system.

Projects are temporary.

The Factory is permanent.

---

## 1.2 Scope

The Factory governs the complete lifecycle of a software project, including:

- Project initialization
- Research
- Requirements engineering
- Architecture design
- Project planning
- Chunk planning
- Contract generation
- Implementation
- Verification
- Review
- Reporting
- Continuous improvement
- Factory evolution

This specification defines how every participant interacts throughout that lifecycle.

---

## 1.3 Objectives

The Factory exists to achieve the following objectives, listed in order of priority.

### Objective 1

Produce correct software.

### Objective 2

Produce deterministic software.

### Objective 3

Preserve architectural integrity.

### Objective 4

Minimize AI hallucination.

### Objective 5

Maximize reproducibility.

### Objective 6

Enable independent verification.

### Objective 7

Provide complete engineering traceability.

### Objective 8

Accumulate reusable engineering knowledge across projects.

### Objective 9

Continuously improve the Factory itself through evidence.

### Objective 10

Improve implementation efficiency without sacrificing engineering quality.

---

## 1.4 Non-Objectives

The Factory is **not** designed to:

- maximize implementation speed
- minimize token usage
- replace engineering discipline with AI creativity
- reduce documentation
- optimize prompts instead of systems
- encourage implementation shortcuts

Whenever speed conflicts with engineering quality,

**engineering quality always takes priority.**

---

# 2. Philosophy

The Factory is founded upon a single engineering principle:

> **Software quality improves when decision-making is separated from implementation.**

Modern AI models are capable of planning, coding, reviewing, debugging, researching, and documenting.

They become less reliable when expected to perform all of those responsibilities simultaneously.

The Factory intentionally decomposes software engineering into isolated responsibilities.

Every participant performs exactly one responsibility.

Nothing more.

---

## 2.1 Separation of Responsibilities

Planning never writes code.

Implementation never invents requirements.

Verification never assumes correctness.

Review never rewrites architecture.

Evolution never modifies completed projects.

Every stage validates the previous stage before allowing progress.

---

## 2.2 Determinism Before Intelligence

Whenever a deterministic solution exists, it must always be preferred over AI reasoning.

Examples include:

- Schema validation
- Manifest validation
- File existence checks
- Dependency resolution
- Hash verification
- Repository cleanliness
- Execution order validation
- Unit tests
- Integration tests
- Static analysis
- Reproducibility verification

Artificial intelligence should never decide something that software can objectively prove.

---

## 2.3 Evidence Before Opinion

Engineering decisions require evidence.

Valid evidence includes:

- Benchmark results
- Performance profiling
- Published research
- Verification reports
- Reproducible failures
- Objective measurements
- Architectural analysis
- Experimental results

Preferences are not evidence.

Opinions are not evidence.

Experience without verification is not evidence.

---

## 2.4 Local Context

Every participant receives only the information necessary to perform its assigned responsibility.

Excess context increases ambiguity.

Excess context increases hallucination.

The Factory intentionally minimizes context loading.

---

## 2.5 Immutable Decisions

Once approved, the following artifacts become immutable:

- Architecture
- Invariants
- Contracts
- Acceptance criteria
- Execution manifests

These artifacts may only change through explicit change procedures.

Silent modification is prohibited.

---

## 2.6 Reproducibility

A competent engineer must be capable of recreating identical outputs using only:

- the repository
- approved specifications
- execution manifests
- configuration files
- documented dependencies

If identical outputs cannot be reproduced,

the implementation is considered incomplete.

---

# 3. Design Goals

The Factory optimizes for the following goals.

Goals are listed by priority.

| Priority | Goal |
|----------|------|
| 1 | Engineering correctness |
| 2 | Deterministic execution |
| 3 | Architectural consistency |
| 4 | Independent verification |
| 5 | Reproducibility |
| 6 | Auditability |
| 7 | Maintainability |
| 8 | Knowledge accumulation |
| 9 | Factory evolution |
| 10 | Implementation efficiency |

Efficiency is intentionally the lowest priority.

Correct software delivered later is preferable to incorrect software delivered sooner.

---

# 4. Core Principles

Every Factory implementation must satisfy these principles.

## Principle 1

Planning and implementation are separate responsibilities.

---

## Principle 2

Every engineering decision has exactly one owner.

---

## Principle 3

No implementation may exceed its approved scope.

---

## Principle 4

Every modification must be traceable.

---

## Principle 5

Every contract must be objectively verifiable.

---

## Principle 6

Verification always precedes review.

---

## Principle 7

Review always precedes approval.

---

## Principle 8

Approval always precedes freeze.

---

## Principle 9

Frozen artifacts cannot be modified.

---

## Principle 10

Factory evolution requires accumulated evidence across multiple projects.

One successful idea does not justify Factory changes.

Repeated evidence does.

---

# 5. Engineering Principles

The Factory adopts established software engineering principles wherever applicable.

## 5.1 Single Responsibility Principle

Every artifact has exactly one responsibility.

Examples:

| Artifact | Responsibility |
|-----------|---------------|
| `architecture.md` | Defines architecture |
| `roadmap.md` | Defines milestones |
| `contract.md` | Defines implementation scope |
| `gatekeeper.py` | Performs deterministic validation |
| `execution_manifest.yaml` | Controls execution order |
| `chunk_report.md` | Summarizes chunk completion |
| `evolution.md` | Records engineering observations |

Artifacts must never perform multiple unrelated responsibilities.

---

## 5.2 Explicit Ownership

Every decision has one owner.

Shared ownership is prohibited.

When ownership is ambiguous,

the process is ambiguous.

---

## 5.3 Immutable Interfaces

Interfaces between components must remain stable throughout implementation.

Breaking an approved interface requires:

1. Architecture review
2. Explicit approval
3. Updated documentation
4. Reverification of dependent contracts

---

## 5.4 Incremental Progress

Large changes increase risk.

The Factory therefore decomposes work into progressively smaller units:

```
Project
    ↓
Chunk
    ↓
Contract
    ↓
Implementation
    ↓
Verification
```

No participant skips levels.

---

## 5.5 Verification as a First-Class Citizen

Verification is not a final step.

Verification is part of implementation.

Every implementation must continuously verify:

- correctness
- invariants
- reproducibility
- acceptance criteria
- repository integrity

Verification occurs throughout development, not after it.

---

**End of Part 1/12**

# 6. Definitions

To ensure consistent interpretation across every project, the following terminology is used throughout the Factory.

---

## 6.1 Factory

The reusable engineering framework.

The Factory is **not** part of any project.

It contains:

- Constitution
- Dynamic Rules
- Gatekeeper
- Workflow Specifications
- Evolution Mechanisms
- Shared Templates

The Factory persists across every future project.

---

## 6.2 Project

A software system built using the Factory.

A project contains:

- Requirements
- Architecture
- Roadmap
- Chunks
- Contracts
- Source Code
- Reports

Projects never redefine the Factory.

---

## 6.3 Chunk

The largest implementation unit.

A chunk represents one complete engineering milestone.

Examples:

- Infrastructure
- Backend API
- AI Pipeline
- Training Pipeline
- Evaluation
- Deployment

Chunks must produce independently verifiable value.

---

## 6.4 Contract

The smallest independently executable engineering unit.

Every contract:

- has one objective
- owns one scope
- modifies only allowed files
- defines deterministic verification
- produces one report

Contracts are intentionally small enough to be reviewed independently.

---

## 6.5 Artifact

Any persistent output generated during development.

Examples:

- Markdown documents
- YAML manifests
- Python modules
- Test reports
- Verification reports
- Configuration files
- Diagrams
- Metrics

Artifacts are version controlled unless explicitly excluded.

---

## 6.6 Verification

Objective proof that an implementation satisfies its specification.

Verification may include:

- Unit tests
- Integration tests
- Benchmarks
- Static analysis
- Schema validation
- Hash validation
- Dataset validation
- Manual inspection (only if unavoidable)

---

## 6.7 Validation

Validation answers:

> Did we build the correct thing?

Verification answers:

> Did we build it correctly?

The Factory distinguishes these concepts explicitly.

---

## 6.8 Invariant

A condition that must never become false.

Examples:

- API compatibility
- Dataset integrity
- Mathematical assumptions
- Database constraints
- Research methodology
- Security guarantees

Violating an invariant immediately blocks progress.

---

## 6.9 Stop Condition

A deterministic condition that immediately terminates execution.

Examples:

- Verification failure
- Missing dependency
- Frozen file modification
- Repository corruption
- Failed invariant
- Gatekeeper rejection

AI is never permitted to ignore a Stop Condition.

---

## 6.10 Frozen File

A file that cannot be modified during a contract.

Modification requires:

- architecture change
- approved change request
- updated manifests
- reverification

---

## 6.11 Allowed File

A file explicitly owned by the current contract.

No implementation may modify files outside this list.

---

## 6.12 Evidence

Objective information supporting an engineering decision.

Examples include:

- profiling
- benchmarks
- logs
- published literature
- reproducible bugs
- verification reports

Personal preference is not evidence.

---

# 7. Factory State Machine

Every project progresses through a deterministic sequence of states.

No state may be skipped.

```
Factory Initialization

↓

Project Planning

↓

Architecture Approval

↓

Roadmap Approval

↓

Chunk Planning

↓

Contract Generation

↓

Contract Execution

↓

Verification

↓

Review

↓

Approval

↓

Chunk Completion

↓

Next Chunk

↓

Project Completion

↓

Factory Retrospective

↓

Factory Evolution
```

---

## 7.1 State Transition Rules

Every state has:

- Entry Conditions
- Execution Rules
- Exit Conditions
- Failure Conditions

Progression occurs only after exit conditions are satisfied.

---

## 7.2 Entry Conditions

A state begins only when:

- previous state approved
- repository clean
- required artifacts exist
- gatekeeper passes
- dependencies satisfied

---

## 7.3 Execution Rules

While inside a state:

- only approved actions allowed
- ownership cannot change
- contracts remain immutable
- frozen files remain frozen

---

## 7.4 Exit Conditions

A state completes only after:

- verification passes
- reports generated
- artifacts updated
- repository validated
- approval recorded

---

## 7.5 Failure Conditions

Execution immediately stops when:

- verification fails
- invariant violated
- frozen file modified
- missing artifact
- execution order violated
- manifest invalid
- repository dirty (unless expected)

---

# 8. Roles and Responsibilities

The Factory deliberately separates responsibilities.

Every responsibility has one owner.

---

## 8.1 Claude

Claude is the Architect.

Claude makes engineering decisions.

Claude does **not** perform production implementation.

Responsibilities include:

- requirements engineering
- research synthesis
- architecture
- project planning
- chunk planning
- contract generation
- risk analysis
- acceptance criteria
- review
- fix package generation
- factory retrospective

Claude owns engineering decisions.

---

## 8.2 Gemini

Gemini is the Implementation Engineer.

Gemini executes approved engineering work.

Gemini never invents architecture.

Responsibilities:

- implementation
- refactoring
- documentation
- tests
- scripts
- verification
- self-review
- reporting

Gemini owns execution quality.

---

## 8.3 Gatekeeper

Gatekeeper is deterministic.

It performs no AI reasoning.

Responsibilities include:

- file hash validation
- manifest validation
- execution order validation
- frozen file checks
- required artifact checks
- repository cleanliness
- verification script execution
- report existence
- dependency validation

Gatekeeper either passes or fails.

There is no partial approval.

---

## 8.4 Human Engineer

The human owns strategic decisions.

Responsibilities include:

- project selection
- architecture approval
- final acceptance
- deployment approval
- factory evolution approval

The human is the final authority.

---

# 9. Decision Ownership

To eliminate ambiguity, every engineering decision has exactly one owner.

| Decision | Owner |
|-----------|-------|
| Requirements | Claude |
| Architecture | Claude |
| Technology Stack | Claude |
| Chunk Structure | Claude |
| Contracts | Claude |
| Acceptance Criteria | Claude |
| Risk Assessment | Claude |
| Implementation | Gemini |
| Tests | Gemini |
| Documentation | Gemini |
| Verification Execution | Gemini + Gatekeeper |
| Deterministic Validation | Gatekeeper |
| Final Approval | Human |

If ownership is unclear,

the process is incorrect.

---

# 10. Repository Architecture Overview

Every project follows the same directory layout.

```
AI_Software_Factory/

├── factory/
│
├── project/
│
├── data/
│
├── docs/
│
├── scripts/
│
├── configs/
│
├── tests/
│
├── source/
│
├── outputs/
│
└── logs/
```

The exact project structure may evolve, but every top-level directory must have a clearly defined responsibility.

No directory may become a miscellaneous storage location.

---

## 10.1 Design Rules

Repository organization follows these principles:

- predictable
- deterministic
- discoverable
- scalable
- language-independent

A new engineer should understand repository organization within minutes.

---

## 10.2 Separation of Concerns

Planning documents never mix with implementation.

Generated outputs never mix with source code.

Logs never mix with reports.

Configurations never mix with datasets.

Every category has a dedicated location.

---

## 10.3 Naming Convention

All files should use consistent naming.

Examples:

```
project_description.md
architecture.md
roadmap.md
execution_manifest.yaml
chunk_report.md
contract_report.md
verification_report.md
```

Names should describe purpose, not implementation.

Avoid ambiguous names such as:

```
notes.md
misc.md
stuff.md
temp.py
draft_final_v3.py
```

---

**End of Part 2/12**

# 11. Project Initialization

Project initialization establishes every document required before implementation begins.

No implementation may begin before initialization is complete.

---

## 11.1 Objectives

Initialization must produce a project that is:

- reproducible
- deterministic
- fully documented
- architecture driven
- implementation independent

The initialization phase exists to eliminate ambiguity before code is written.

---

# 12. Required Project Artifacts

Every project begins with the following files.

```
project/

├── project_description.md
├── architecture.md
├── roadmap.md
├── project_knowledge.md
├── invariants.md
└── chunks/
```

Every file has a unique purpose.

No file duplicates another.

---

# 13. project_description.md

This is the project's highest-level specification.

It answers:

- What are we building?
- Why are we building it?
- What problems does it solve?
- What are the success criteria?
- What is explicitly out of scope?

This becomes the project's primary source of truth.

---

## Required Sections

### Executive Summary

A concise description of the project.

---

### Motivation

Why the project exists.

---

### Objectives

Functional objectives.

Non-functional objectives.

Research objectives (if applicable).

---

### Scope

Clearly defines:

Included

Excluded

Future work

---

### Functional Requirements

Every required feature.

Each requirement should be uniquely numbered.

Example

```
FR-001

System shall support...

FR-002

System shall...
```

---

### Non-functional Requirements

Performance

Reliability

Maintainability

Scalability

Security

Reproducibility

Portability

---

### Constraints

Examples

Hardware

Operating System

Python Version

Libraries

Licenses

Compute Budget

Time Budget

Storage Budget

---

### Success Criteria

Every objective should have measurable completion criteria.

Avoid vague statements such as:

> "Good performance"

Instead use:

```
Accuracy ≥ 95%

Latency ≤ 200ms

Memory < 2GB

Training reproducible
```

---

# 14. architecture.md

Architecture defines **how** the project is organized.

It never contains implementation.

---

## Required Sections

### System Overview

High-level explanation.

---

### Architectural Principles

Examples

- modularity
- deterministic execution
- reproducibility
- loose coupling
- high cohesion

---

### Component Diagram

Describe every subsystem.

Example

```
Frontend

↓

API

↓

Service Layer

↓

Data Layer

↓

Database
```

---

### Module Responsibilities

Every module must have exactly one responsibility.

Example

```
Authentication

Authorization

Dataset Loader

Training Pipeline

Evaluation

Visualization
```

---

### External Dependencies

List every dependency.

Reason for inclusion.

Version constraints.

---

### Interfaces

Define module interfaces.

Inputs

Outputs

Data ownership

Communication method

---

### Data Flow

Describe how information moves through the system.

---

### Error Boundaries

Where failures are isolated.

Recovery strategy.

---

### Future Extension Points

Planned locations for future work.

---

# 15. roadmap.md

Roadmap divides work into architectural milestones.

Never chronological weeks.

Never implementation tasks.

---

Example

```
Chunk 01

Environment

Chunk 02

Infrastructure

Chunk 03

Core Backend

Chunk 04

AI Models

Chunk 05

Training Pipeline

Chunk 06

Evaluation

Chunk 07

Deployment
```

Each chunk should produce meaningful engineering value.

---

## Chunk Requirements

Every chunk includes

- Objective
- Deliverables
- Dependencies
- Estimated complexity
- Success criteria

Nothing more.

Implementation belongs elsewhere.

---

# 16. project_knowledge.md

Stable project knowledge.

This document minimizes repeated prompting.

Examples include:

- terminology
- domain concepts
- abbreviations
- datasets
- mathematical definitions
- external standards
- regulatory requirements
- glossary

This file changes rarely.

---

## Recommended Sections

### Glossary

Define important terms.

---

### Domain Knowledge

Important concepts.

---

### Datasets

Origin

Purpose

Licensing

Known limitations

---

### Standards

Relevant RFCs

Academic papers

Industry standards

---

### Assumptions

Stable assumptions.

---

### References

Canonical references only.

---

# 17. invariants.md

Invariants are permanent truths.

Breaking an invariant immediately blocks implementation.

---

Examples

Database schema

API contracts

Research protocol

Mathematical assumptions

Evaluation methodology

Dataset integrity

Security guarantees

---

## Invariant Format

Each invariant should contain

```
ID

Description

Reason

Verification Method

Failure Impact
```

Example

```
INV-004

Every dataset split must remain deterministic.

Reason

Ensures reproducibility.

Verification

Hash comparison.

Failure

Immediate stop.
```

---

# 18. Project Approval Gate

Before planning begins:

The following checklist must pass.

```
✓ project_description complete

✓ architecture complete

✓ roadmap complete

✓ project_knowledge complete

✓ invariants complete

✓ repository initialized

✓ factory present

✓ version recorded

✓ gatekeeper available
```

If any item fails,

planning cannot begin.

---

# 19. Chunk Planning

Chunk planning is performed exclusively by Claude.

Claude transforms architecture into executable engineering work.

No implementation occurs here.

---

## Chunk Planning Objectives

Each chunk should:

- deliver one architectural milestone
- minimize cross-contract dependencies
- maximize verification independence
- minimize context size
- preserve repository integrity

---

## Chunk Structure

Each chunk contains:

```
chunkXX/

├── chunkXX.md
├── execution_manifest.yaml
└── contracts/
```

Nothing else is mandatory.

---

# 20. chunkXX.md

This is the engineering specification for one chunk.

It defines exactly what Gemini will implement.

---

## Required Sections

### Objective

One clear engineering objective.

---

### Scope

Included work.

Excluded work.

---

### Repository State Required

Expected repository condition before execution.

Examples

- clean git status
- previous chunk approved
- datasets available
- dependencies installed

---

### Deliverables

Every expected artifact.

---

### Success Criteria

Objective completion requirements.

---

### Acceptance Criteria

Human-readable completion checklist.

---

### Contracts

Ordered list of contracts.

---

### Risks

Known implementation risks.

---

### References

Relevant project documents.

---

**End of Part 3/12**

---

# Contract Execution Lifecycle (Gemini)

Every contract is executed independently.

Gemini must never infer work outside the current contract.

Only the context explicitly defined by the Factory may be loaded.

---

## Context Loading Order

Load context strictly in the following order.

```
1. factory/constitution.md

↓

2. factory/dynamic_rules.md

↓

3. project/project_description.md

↓

4. project/architecture.md

↓

5. project/project_knowledge.md

↓

6. project/invariants.md

↓

7. Current Contract

↓

8. Referenced External Specifications (only if explicitly listed)
```

No additional files may be loaded.

No hidden context.

No assumptions.

---

# Context Isolation Rules

Gemini may not:

- inspect future contracts
- inspect previous contract implementations unless explicitly referenced
- modify unrelated modules
- perform repository-wide refactoring
- optimize unrelated code
- update documentation outside Allowed Files

Every contract is executed in isolation.

---

# Phase 1 — Planning

Implementation has not started.

Gemini must produce:

## Repository Understanding

- current repository state
- required inputs
- dependency availability
- contract prerequisites

---

## Execution Plan

Step-by-step implementation plan.

Every planned modification must reference an Allowed File.

---

## File Impact Analysis

List:

Modified files

Created files

Generated artifacts

Temporary files

---

## Risk Assessment

Identify:

- predicted failure modes
- dependency risks
- invariant risks
- verification risks

---

## Verification Plan

Specify:

tests to execute

expected outputs

success conditions

failure conditions

---

## Stop Condition Acknowledgement

Gemini must explicitly acknowledge every Stop Condition defined by the contract.

If planning identifies an impossible requirement:

STOP

No implementation begins.

---

# Phase 2 — Implementation

Implementation begins only after planning succeeds.

---

## Implementation Rules

Gemini must:

implement only the contract

never modify Frozen Files

never bypass verification

never weaken tests

never disable assertions

never suppress failures

never fabricate outputs

---

## Continuous Verification

Verification is continuous.

Do not wait until implementation ends.

After every meaningful change:

- execute relevant tests
- inspect outputs
- verify invariants
- update telemetry

---

## Intermediate Failure

If verification fails:

Stop implementation.

Identify root cause.

Fix.

Reverify.

Continue only after clean verification.

---

# Evidence Collection

Every implementation step should collect evidence.

Examples:

- command output

- hashes

- generated manifests

- test results

- validation reports

- benchmark numbers

Evidence is preferred over explanation.

---

# Phase 3 — Self Review

Implementation is complete.

Gemini now changes roles.

Reviewer only.

No assumptions.

No optimism.

---

## Completion Review

Verify:

every objective completed

every output exists

every acceptance criterion satisfied

every verification script passed

---

## Constitution Review

Verify:

Constitution compliance

Dynamic Rule compliance

Factory compliance

Repository integrity

---

## Invariant Review

Every invariant must be evaluated.

For each invariant:

Status

PASS

or

FAIL

No partial credit.

---

## Predicted Failure Review

Compare implementation against:

Predicted Failure Modes

Document:

Occurred?

Prevented?

Still possible?

---

## Repository Review

Verify:

No unrelated file changes

No accidental modifications

No debug artifacts

No temporary files

No generated garbage

Repository is clean.

---

## Determinism Review

Re-run deterministic processes.

Verify identical outputs.

Examples:

hashes

manifests

generated datasets

reports

Deterministic means identical.

---

## Security Review

Verify:

no secrets committed

no credentials stored

no API keys

no passwords

no temporary authentication files

---

## Documentation Review

Verify:

documentation matches implementation

examples still work

commands are correct

paths are correct

---

## Final Self Review Decision

Possible results only:

PASS

or

FAIL

If FAIL:

Return to Phase 2.

Claude must never receive failed work.

---

# Phase 4 — Contract Reporting

Generate

```
contract_report.md
```

Automatically.

---

## Required Sections

Contract ID

Objective

Implementation Summary

Modified Files

Created Files

Verification Results

Invariant Results

Constitution Compliance

Dynamic Rule Compliance

Predicted Failure Review

Known Risks

Repository Status

Evidence

Final Decision

---

## Evidence Section

Include:

executed commands

test summaries

verification outputs

generated artifacts

hashes (if relevant)

timings (if relevant)

---

## Report Quality Rules

Reports must describe facts.

Never speculate.

Never exaggerate.

Never hide failures.

---

# Local Validation

Run

```
factory/gatekeeper.py
```

Gatekeeper performs deterministic validation only.

Never AI reasoning.

---

## Required Validation

Repository clean

Required reports

Manifest integrity

Required artifacts

Frozen files

Execution order

Contract completion

Verification reports

Hashes

Generated outputs

Repository state

---

## Validation Failure

Immediately stop.

No commit.

No approval.

No continuation.

Fix the repository first.

---

# Commit Policy

A commit occurs only after:

Phase 3 PASS

Gatekeeper PASS

Repository Clean

Contract Report Generated

---

Commit message format:

```
[C1-04] Environment compatibility verification
```

or

```
[C2-03] Graph encoder implementation
```

One contract.

One commit.

---

# Chunk Completion

After every contract succeeds:

Generate automatically:

```
chunk_report.md
```

---

## Chunk Report Structure

Chunk Summary

Completed Contracts

Verification Summary

Evidence Summary

Metrics Summary

Repository Status

Outstanding Risks

Lessons Learned

Recommendation

---

# Claude Review

Claude reviews only after:

Entire chunk complete.

Never earlier.

Claude reviews:

```
chunk_report.md
```

and supporting artifacts if required.

---

## Claude Decision

Possible outcomes only:

```
APPROVED
```

or

```
FIX PACKAGE
```

No third option.

---

# Fix Package

If review fails:

Claude generates

```
fix_package.md
```

---

Contains

Affected Contracts

Exact Problems

Evidence

Acceptance Criteria

Verification Requirements

Stop Conditions

Allowed Files

Frozen Files

No ambiguity.

Gemini executes only the Fix Package.

Nothing else.

---

# Chunk Completion Criteria

A chunk is complete only if:

✓ All contracts PASS

✓ All reports generated

✓ Gatekeeper PASS

✓ Repository clean

✓ Claude APPROVED

Only then may the Factory proceed to the next chunk.

---

 ---

# Continuous Evolution Logging

The evolution system exists solely to improve the Factory.

It is **never** part of the project deliverable.

It records engineering evidence that can later justify changes to the Factory.

The Factory evolves through evidence, never opinion.

---

# Evolution Logging Policy

Logging is continuous.

Do **not** wait until:

- contract completion
- chunk completion
- project completion

Every meaningful engineering event should be recorded as it happens.

Examples:

- implementation decisions
- failed experiments
- verification failures
- successful optimizations
- repeated AI mistakes
- contract ambiguities
- unnecessary workflow steps
- Gatekeeper failures
- review findings

---

# Evolution Directory

```
project/evolution/

├── evolution.md
├── telemetry.jsonl
├── experiments.yaml
├── decision_log.md
├── metrics.csv
└── lessons_learned.md
```

---

# evolution.md

Human-readable engineering journal.

Append-only.

Never rewrite history.

---

## Record

Each entry contains:

Date

Chunk

Contract

Observation

Reasoning

Outcome

Evidence

Potential Factory Improvement

---

Example

```
Observation

Gemini repeatedly modified unrelated helper files.

Reason

Allowed Files list appeared after implementation instructions.

Evidence

Occurred in 4 contracts.

Potential Improvement

Move Allowed Files before Instructions.

Promote after project completion.
```

---

# telemetry.jsonl

Machine-readable execution log.

One JSON object per event.

Never edit previous entries.

---

## Suggested Fields

```json
{
  "timestamp": "...",
  "chunk": "...",
  "contract": "...",
  "phase": "...",
  "event": "...",
  "status": "...",
  "duration_seconds": 0,
  "verification": "...",
  "violations": [],
  "approved": true
}
```

---

## Example Events

Contract started

Planning complete

Verification passed

Verification failed

Gatekeeper passed

Gatekeeper failed

Claude approved

Fix package generated

Chunk complete

---

# experiments.yaml

Tracks controlled Factory experiments.

Every experiment must answer:

Hypothesis

Why?

How measured?

Result

Conclusion

Promote?

---

Example

```yaml
experiment:
  id: EXP-004

  hypothesis:
    Moving verification before reporting reduces review failures.

  success_metric:
    Claude review failures decrease.

  result:
    Success

  evidence:
    Review failures reduced from 18% to 4%.

  promote:
    true
```

---

# decision_log.md

Records why Factory changes occurred.

Never record project decisions.

Only Factory decisions.

---

Every entry answers:

What changed?

Why?

Evidence?

Expected improvement?

Promoted?

Version introduced?

---

Example

```
Decision D-012

Changed:

Contract schema now requires Repository State.

Reason:

Gemini repeatedly assumed repository conditions.

Evidence:

Occurred in 6 contracts.

Expected Improvement:

Fewer invalid assumptions.

Version

1.1
```

---

# metrics.csv

Machine-readable performance metrics.

Append continuously.

Never overwrite previous rows.

---

## Suggested Columns

```
Chunk

Contract

Planning Time

Implementation Time

Verification Time

Review Time

Total Time

Gemini Sessions

Claude Reviews

Verification Failures

Gatekeeper Failures

Constitution Violations

Dynamic Rule Violations

First Pass Success

Final Approval
```

---

# lessons_learned.md

Human-readable retrospective notes.

Unlike evolution.md, this summarizes patterns rather than individual events.

Updated after every chunk.

Contains:

Repeated mistakes

Repeated successes

AI behavior

Human bottlenecks

Factory bottlenecks

Potential promotions

---

# Knowledge Promotion

The Factory promotes knowledge cautiously.

Ideas are not promoted.

Evidence is required.

---

## Promotion Pipeline

```
Observation

↓

Repeated Evidence

↓

Experiment

↓

Validation

↓

Promotion

↓

Dynamic Rule
```

No shortcuts.

---

# Dynamic Rule Promotion Requirements

A rule may only be promoted if:

Occurred multiple times

Evidence collected

Improvement measurable

Improvement reproducible

No regressions introduced

---

Example

```
Rule D-011

Require repository state summary before implementation.

Reason

Reduced invalid assumptions by 42%.

Evidence

Observed across 5 completed projects.

Status

PROMOTED
```

---

# Invariant Promotion

Project invariants are separate.

Only update when:

Architecture changes

Protocols change

Mathematical assumptions change

External specifications change

Never promote temporary implementation details.

---

# Factory Retrospective

Conducted **only after the entire project completes.**

Never after individual chunks.

Purpose:

Improve the Factory itself.

Not the project.

---

## Retrospective Questions

Which contracts repeatedly caused failures?

Which contract sections were ignored?

Which Dynamic Rules prevented failures?

Which predicted failure modes were accurate?

Which predicted failure modes never occurred?

Which verification scripts were unnecessary?

Which Gatekeeper checks never triggered?

Which reports were never useful?

Which reports lacked information?

Which implementation instructions caused ambiguity?

Which AI mistakes repeated?

Which manual reviews were unnecessary?

Which automation should be added?

Which artifacts should be removed?

What should become a Dynamic Rule?

---

# Retrospective Outputs

Generate:

```
factory_retro.md
```

Contains:

Executive Summary

Evidence

Metrics

Recommendations

Promotion Candidates

Rejected Ideas

Architectural Changes

Version Recommendation

---

# Factory Evolution Policy

Factory evolution is conservative.

Projects never redefine the Factory.

Only retrospective evidence may.

---

# Versioning Policy

Factory versions communicate architectural maturity.

---

## Patch Version

```
v1.0.x
```

Allowed:

Bug fixes

Documentation improvements

Clarifications

Typos

Additional examples

No workflow changes.

---

## Minor Version

```
v1.1
```

Requires:

At least one completed project

Retrospective

Evidence

Validated improvements

Workflow enhancements

Dynamic Rule promotions

New deterministic automation

---

## Major Version

```
v2.0
```

Requires:

Architectural redesign

Workflow redesign

Responsibility changes

New execution model

Factory restructuring

Evidence collected across multiple completed projects

Never based on ideas alone.

---

# Factory Maturity Levels

Level 1

Initial deterministic workflow.

Level 2

Evidence-driven improvements.

Level 3

Highly automated verification.

Level 4

Self-improving deterministic engineering system.

The objective is not simply to complete projects.

The objective is to continuously improve the Factory while maintaining deterministic, reproducible, and evidence-based software engineering.

---

# Appendix A — Operational Standards

This appendix defines mandatory operational behavior that applies throughout the Factory.

These standards remove ambiguity that would otherwise require AI judgment.

---

# Context Loading Policy

AI models must never load the entire repository unless explicitly instructed.

Only the minimum required context shall be loaded.

Default loading order:

```
constitution.md

↓

dynamic_rules.md

↓

project_description.md

↓

architecture.md

↓

project_knowledge.md

↓

invariants.md

↓

Current Chunk

↓

Current Contract
```

Additional files may only be loaded when:

- listed as an Input
- listed as a Dependency
- required by verification
- explicitly requested

Loading unnecessary files increases hallucination risk.

---

# Context Priority

If two artifacts disagree:

Highest priority wins.

Priority order:

```
Constitution

↓

Dynamic Rules

↓

Project Invariants

↓

Architecture

↓

Project Description

↓

Current Contract

↓

Implementation Files
```

Implementation never overrides planning.

---

# AI Responsibility Matrix

## Claude

Responsible for:

- architecture
- planning
- contracts
- reviews
- research
- acceptance decisions
- fix packages
- project evolution

Never writes production implementation unless explicitly requested.

---

## Gemini

Responsible for:

- implementation
- deterministic execution
- testing
- verification
- reporting
- implementation fixes

Never changes architecture.

Never invents requirements.

Never expands contract scope.

---

## Gatekeeper

Responsible for:

- deterministic validation
- execution order
- frozen files
- manifests
- repository state
- reports
- verification evidence

Never performs reasoning.

---

# Human Responsibilities

The human remains the final authority.

Responsibilities include:

- approving architecture
- approving roadmap
- approving chunk plans
- reviewing Claude decisions
- merging pull requests
- promoting Factory improvements

---

# Communication Rules

AI responses should always distinguish between:

Facts

Assumptions

Evidence

Recommendations

Unknowns

Never present assumptions as facts.

---

# Repository State Policy

Every contract assumes one repository state.

Before implementation begins, verify:

- clean git status
- correct branch
- dependencies installed
- previous contract approved
- required reports exist
- Gatekeeper passes

Otherwise:

STOP.

---

# Modification Policy

Files fall into four categories.

## Editable

May be modified freely.

Listed in Allowed Files.

---

## Frozen

Never modified.

Unless explicitly unfrozen.

---

## Generated

Generated automatically.

May only be regenerated.

Never manually edited.

Examples:

```
reports

metrics

telemetry

generated manifests
```

---

## Protected

Factory files.

Only Claude may modify.

Examples:

```
constitution.md

dynamic_rules.md

factory_spec.md
```

---

# Failure Recovery Policy

If implementation fails:

1.

Stop.

2.

Identify root cause.

3.

Record evidence.

4.

Retry only after correction.

Never continue through failures.

---

# Partial Completion Policy

Incomplete contracts are never reported as complete.

Allowed statuses:

```
NOT STARTED

IN PROGRESS

BLOCKED

FAILED

COMPLETE
```

Nothing else.

---

# Review Philosophy

Reviews verify.

They do not redesign.

Claude should reject:

missing evidence

contract violations

scope creep

untested code

missing verification

broken invariants

Claude should ignore:

style preferences

personal opinions

alternative implementations

unless explicitly required.

---

# Evidence Requirements

Every important claim should be backed by evidence.

Examples:

Verification passed

↓

pytest output

Repository clean

↓

git status

Performance improved

↓

benchmark

Invariant maintained

↓

verification script

---

# Automation Preference

Whenever deterministic automation can replace AI reasoning:

Prefer automation.

Examples:

Instead of asking AI:

"Did every required report exist?"

Run:

```
ls reports/
```

Instead of asking:

"Did every contract execute?"

Read:

execution_manifest.yaml

---

# Factory Goals

The Factory exists to produce:

Deterministic software.

Reproducible engineering.

Minimal ambiguity.

Evidence-backed decisions.

Reusable workflows.

Continuous improvement.

---

# Success Criteria

The Factory is successful when:

Claude never reviews unfinished work.

Gemini never invents requirements.

Gatekeeper catches deterministic failures.

Every project remains reproducible.

Factory improvements are evidence-based.

The same Factory can execute multiple projects without modification.

---

# End of Specification

**Factory Version**

```
v1.0.1
```

Status:

```
Stable

Deterministic

Evidence-driven

Reusable
```

This document is the authoritative specification for AI Software Factory v1.0.1.

Any behavior not explicitly described here must not be assumed.