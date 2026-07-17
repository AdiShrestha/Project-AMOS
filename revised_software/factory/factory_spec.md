# Factory Specification

Version

1.0.1

---

# Purpose

The Factory Specification defines **how the AI Software Factory operates**.

Unlike the Constitution, which defines universal engineering principles, this document defines the implementation of the Factory itself.

The Constitution answers

> What rules govern every project?

The Factory Specification answers

> How does the Factory execute projects?

This document contains no behavioral rules.

Behavior belongs exclusively in `constitution.md`.

---

# Factory Objectives

The Factory exists to

- maximize software quality
- maximize reproducibility
- maximize continuity between AI sessions
- minimize unnecessary AI decision making
- minimize ambiguity
- preserve engineering knowledge
- evolve through evidence instead of intuition

---

# Ownership Model

Every artifact has one owner.

Ownership prevents ambiguity.

---

## Claude

Responsibilities

- project planning
- architecture
- research
- chunk planning
- contract generation
- invariant definition
- review
- fix package generation
- project level decisions

Never performs implementation.

---

## Gemini

Responsibilities

- implementation
- verification
- testing
- reporting
- continuous logging
- contract execution

Never redesigns architecture.

Never invents requirements.

---

## Gatekeeper

Responsibilities

- deterministic validation
- repository verification
- frozen file checks
- manifest verification
- report existence
- repository cleanliness

Never performs AI reasoning.

---

## Human

Responsibilities

- approve architecture
- approve factory evolution
- approve workflow changes
- manage repositories
- provide external resources
- resolve stop conditions requiring human judgement

---

# Repository Specification

```
AI_Software_Factory/

factory/

project/

source/
```

The Factory directory contains reusable infrastructure.

The Project directory contains project specific artifacts.

Source contains implementation.

---

# Factory Artifacts

---

## constitution.md

Purpose

Universal engineering principles.

Owner

Human

Created

Factory initialization.

Modified

Rarely.

---

## factory_spec.md

Purpose

Factory operating manual.

Owner

Human

Created

Factory initialization.

Modified

Only when Factory workflow changes.

---

## dynamic_rules.md

Purpose

Evidence backed improvements promoted from completed projects.

Owner

Human

Modified

Only after promotion.

---

## gatekeeper.py

Purpose

Deterministic validation.

Owner

Human.

Modified

As deterministic checks improve.

---

## CHANGELOG.md

Purpose

Factory evolution history.

Owner

Human.

Append only.

---

## VERSION

Purpose

Current Factory version.

Owner

Human.

---

# Project Initialization

Claude creates

```
project_description.md

architecture.md

roadmap.md

project_knowledge.md

invariants.md
```

These become the initial project knowledge.

Only one chunk exists initially.

```
chunk01/
```

Remaining chunks are generated later.

---

# Chunk Specification

Each chunk represents one engineering milestone.

A chunk contains

```
chunkNN/

chunkNN.md

execution_manifest.yaml

contracts/

reports/

notes/

scripts/
```

Claude generates

- chunkNN.md
- execution_manifest.yaml

Automation creates

- contracts/

Gemini creates

- reports/

---

# Contract Specification

Every contract must contain

```
Contract ID

Objective

Context

Dependencies

Allowed Files

Frozen Files

Inputs

Outputs

Implementation Instructions

Verification Scripts

Invariant Checklist

Predicted Failure Modes

Definition of Done

Stop Condition
```

Claude owns every field.

Contracts become immutable after generation.

---

# Execution Manifest Specification

The manifest defines

- dependency order
- execution order
- required reports
- verification sequence
- repository preconditions
- clean worktree requirement
- completion dependencies

It is the Factory control plane.

---

# Execution Pipeline

Factory execution always follows this order.

```
Project Initialization

↓

Chunk Planning

↓

Contract Split

↓

Contract Execution

↓

Validation

↓

Reporting

↓

Chunk Review

↓

Knowledge Promotion

↓

Next Chunk
```

No stage may be skipped.

---

# Phase Specification

## Phase 1

Purpose

Planning.

Outputs

- execution plan
- affected files
- risks
- verification strategy

No implementation.

---

## Phase 2

Purpose

Implementation.

Only Allowed Files may be modified.

Verification should occur continuously.

---

## Phase 3

Purpose

Self Review.

Review

- verification scripts
- invariant compliance
- contract completion
- constitution compliance

Failures return execution to Phase 2.

---

## Phase 4

Purpose

Reporting.

Generate

```
contract_report.md
```

Containing

- work completed
- modified files
- verification
- risks
- unresolved issues
- evidence
- clean pass explanation

---

# Report Specification

Reports are engineering artifacts.

Every report prioritizes

- raw evidence
- reproducibility
- commands executed
- generated artifacts
- failures
- deviations
- verification

Narrative follows evidence.

---

# Evolution Specification

The evolution folder improves the Factory.

Never the project.

Contains

```
evolution.md

telemetry.jsonl

decision_log.md

experiments.yaml

metrics.csv
```

Logging is continuous.

Never delayed until project completion.

---

## evolution.md

Human readable engineering journal.

---

## telemetry.jsonl

Machine readable event stream.

One JSON object per event.

Append only.

---

## decision_log.md

Records

- decision
- reason
- alternatives
- expected benefit

Append only.

---

## experiments.yaml

Tracks Factory experiments.

Each experiment records

- hypothesis
- implementation
- success metric
- outcome
- conclusion

---

## metrics.csv

Tracks

- chunk
- contract
- sessions
- verification time
- violations
- approvals
- first pass success

Append only.

---

# Gatekeeper Specification

Gatekeeper performs deterministic validation only.

Allowed

- file hashes
- required files
- manifest integrity
- repository cleanliness
- verification scripts
- frozen files
- report existence
- execution order

Forbidden

- AI reasoning
- code review
- architecture judgement
- quality scoring
- semantic interpretation

---

# Artifact Lifecycle

Every artifact has one owner.

| Artifact | Owner | Created | Modification Policy | Primary Consumer |
|----------|---------|----------|---------------------|------------------|
| constitution.md | Human | Factory creation | Rare | Everyone |
| factory_spec.md | Human | Factory creation | Rare | Claude |
| dynamic_rules.md | Human | Promotion | Append only | Everyone |
| project_description.md | Claude | Project init | Frozen | Everyone |
| architecture.md | Claude | Project init | Frozen | Everyone |
| roadmap.md | Claude | Project init | Frozen | Claude |
| project_knowledge.md | Claude | Project init | Append if needed | Everyone |
| invariants.md | Claude | Project init | Claude controlled | Everyone |
| chunkNN.md | Claude | Chunk planning | Frozen | Splitter |
| contractNN.md | Splitter | Contract split | Frozen | Gemini |
| execution_manifest.yaml | Claude | Chunk planning | Frozen | Gatekeeper |
| contract_report.md | Gemini | Phase 4 | Frozen after completion | Claude |
| chunk_report.md | Gemini | Chunk completion | Frozen | Claude |
| AI_Note.md | Claude | Review | Append only | Gemini |
| telemetry.jsonl | Gemini | Continuous | Append only | Factory |
| decision_log.md | Gemini Claude | Continuous | Append only | Future Projects |
| experiments.yaml | Gemini | Continuous | Append only | Factory |
| metrics.csv | Gemini | Continuous | Append only | Factory |

---

# Knowledge Promotion

Promotion occurs only after evidence.

Pipeline

```
Observation

↓

Repeated Pattern

↓

Evidence

↓

Promotion Proposal

↓

Human Approval

↓

dynamic_rules.md
```

Ideas never qualify.

Evidence is mandatory.

---

# Factory Retrospective

Performed only after project completion.

Questions

- Which rules prevented failures?
- Which reports were unused?
- Which contracts caused repeated problems?
- Which automation saved the most work?
- Which manual steps remain?
- Which Dynamic Rules deserve promotion?
- Which gatekeeper checks never triggered?
- Which Factory components should be simplified?

The retrospective improves the Factory.

Not the completed project.

---

# Versioning

Patch

```
v1.0.x
```

Clarifications.

Bug fixes.

No workflow change.

---

Minor

```
v1.1
```

Evidence backed workflow improvements.

---

Major

```
v2.0
```

Architectural redesign.

---

# Backward Compatibility

Whenever practical,

new Factory versions should continue understanding artifacts generated by previous versions.

Older projects should remain reproducible without migration whenever possible.

---

# Design Philosophy

The Factory minimizes future decision making.

Every reusable improvement should move from

Human memory

↓

AI memory

↓

Documentation

↓

Automation

↓

Deterministic verification

The highest maturity is achieved when correctness no longer depends on remembering to do the right thing.

# Project Bootstrap Specification

The Project Bootstrap Specification defines how every new project is initialized.

Its purpose is to ensure every project begins from a known, reproducible structure.

Initialization is deterministic.

No project-specific assumptions are made during bootstrapping.

---

# Responsibilities

Claude is responsible for bootstrapping the project.

Bootstrapping includes

- creating the required directory structure
- generating required artifacts
- verifying existing artifacts
- reporting missing or inconsistent artifacts

Bootstrapping does not include implementation.

---

# Bootstrap Manifest

Every project begins with

```
bootstrap_manifest.yaml
```

This manifest defines the required repository structure.

It is the single source of truth for project initialization.

---

# Bootstrap Procedure

Initialization always follows this order.

```
Read bootstrap_manifest.yaml

↓

Verify repository structure

↓

Create missing directories

↓

Create missing files

↓

Verify existing artifacts

↓

Report inconsistencies

↓

Project Initialization
```

No implementation may begin before bootstrap succeeds.

---

# Directory Creation

Directories listed in the manifest must exist.

If missing

↓

Create them.

If already present

↓

Leave unchanged.

Directories must never be recreated if they already exist.

---

# File Creation

Required artifacts listed in the manifest must exist.

If missing

↓

Generate them.

If already present

↓

Do not overwrite.

Instead

↓

Verify consistency.

---

# Existing Projects

When bootstrapping an existing repository

- never overwrite existing work
- never regenerate completed artifacts
- create only missing components
- report inconsistencies

Bootstrap must always be safe to run.

---

# Idempotency

Project Bootstrap is idempotent.

Running bootstrap multiple times must produce the same repository state.

Repeated execution must never

- delete files
- duplicate artifacts
- overwrite completed work
- modify frozen artifacts

---

# Verification

Bootstrap verifies

- required directories exist
- required artifacts exist
- manifest integrity
- factory version compatibility
- repository structure

Verification is deterministic.

---

# Bootstrap Report

After initialization Claude reports

- directories created
- files generated
- files already present
- inconsistencies detected
- actions skipped

No hidden modifications are allowed.

---

# Ownership

Bootstrap Manifest

Owner

Human

Bootstrap Execution

Owner

Claude

Verification

Owner

Gatekeeper

Approval

Owner

Human

---

# Failure Conditions

Bootstrap fails if

- manifest cannot be parsed
- required artifact cannot be generated
- repository structure is inconsistent
- factory version is incompatible

Implementation must not begin until bootstrap succeeds.