---
description: "Use when implementing or modifying the validation engine (schema validation, data validation, ValidationMode)."
applyTo: "**/validation/**,**/validation.py"
---
# Validation Engine Conventions

## Stateless Engine

The validation engine receives data and configuration as arguments and returns results. It performs no I/O and holds no state. All storage access is the caller's responsibility.

## Two-Phase Validation

- **Phase 1 (Schema)**: Always runs with ERROR semantics, not mode-controlled. Checks column presence and null structural fields. If Phase 1 fails, Phase 2 never runs.
- **Phase 2 (Data)**: Respects `ValidationMode` (`ERROR`, `FILTER`, `NONE`). Checks type conformance and `Expect` constraints.

## Separation of Concerns (KTD-5)

Definition validation (Python object correctness) is handled by the registry manager (BB-04). Data validation (DataFrame content correctness) is handled here (BB-05). These are separate activities with different inputs and purposes.

## Full Specification

See `docs/docs-03-02-internals-and-data.md` for the complete validation phases specification. See `docs/docs-03-03-api-contracts.md` (BB-05) for method contracts.
