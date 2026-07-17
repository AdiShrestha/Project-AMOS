# CHANGELOG

This document records the evolution of the AI Software Factory.

Its purpose is to preserve the history of the Factory itself.

It does **not** record project changes.

Project changes belong inside the project repository.

---

# Versioning Philosophy

The Factory evolves only through evidence.

Ideas do not justify a new version.

Completed projects, measured improvements, and reproducible engineering experience do.

Every version entry should answer

- What changed?
- Why was it changed?
- What evidence justified it?
- Is it backward compatible?

---

# Change Categories

Each change belongs to one of the following categories.

## Added

New Factory capability.

---

## Changed

Modification of existing behavior.

---

## Deprecated

Feature scheduled for removal.

---

## Removed

Feature removed from the Factory.

---

## Fixed

Correction of a defect.

---

## Documentation

Documentation only.

No Factory behavior changed.

---

## Internal

Refactoring or implementation improvements.

No user-visible behavior changed.

---

# Version Format

```
## vMajor.Minor.Patch

Release Date

YYYY-MM-DD
```

Every release contains the appropriate categories.

Unused categories may be omitted.

---

# Patch Releases

Patch releases

```
v1.0.x
```

May include

- bug fixes
- wording improvements
- clarification of specifications
- documentation improvements
- deterministic refinements

Patch releases must not introduce architectural changes.

---

# Minor Releases

Minor releases

```
v1.1

v1.2
```

Represent evidence-backed improvements to the Factory workflow.

Requirements

- at least one completed project
- measurable evidence
- retrospective review
- backward compatibility whenever practical

---

# Major Releases

Major releases

```
v2.0

v3.0
```

Represent architectural redesign.

Major releases may

- replace workflows
- redesign ownership
- replace major Factory components
- introduce incompatible changes

Major releases should preserve migration paths whenever practical.

---

# Backward Compatibility

Whenever possible

New Factory versions should continue understanding artifacts created by previous versions.

If compatibility cannot be preserved

The breaking change must be documented.

---

# Release Template

```
## vX.Y.Z

Release Date

YYYY-MM-DD

### Added

-

### Changed

-

### Deprecated

-

### Removed

-

### Fixed

-

### Documentation

-

### Internal

-

### Evidence

-

### Notes

-
```

---

# Release History

## v1.0.0

Release Date

2026-07-14

### Added

- Initial AI Software Factory architecture
- Constitution
- Factory Specification
- Dynamic Rules
- Project Architecture
- Contract-based workflow

### Notes

Initial Factory release.

---

## v1.0.1

Release Date

2026-07-14

### Added

- Evolution layer
- Bootstrap Manifest
- Project Bootstrap Specification
- Gatekeeper Specification
- Factory artifact lifecycle
- Ownership model
- Continuous telemetry
- Decision logging
- Metrics collection
- Experiment tracking

### Changed

- Moved Constitution completely to the Factory layer.
- Formalized repository bootstrap process.
- Clarified artifact ownership.
- Clarified project initialization responsibilities.

### Documentation

- Expanded Factory Specification.
- Expanded Dynamic Rules documentation.
- Defined Bootstrap procedure.
- Defined Gatekeeper responsibilities.

### Evidence

Derived from iterative design and review of the Factory architecture prior to the first production project.

### Notes

This release freezes Factory v1.0.1.

No further structural changes should be made until at least one complete project has been executed and reviewed through the Factory. Future improvements should be proposed, evaluated, and versioned according to the Factory's evidence-first philosophy.