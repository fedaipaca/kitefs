---
description: "Use when implementing or modifying the validation engine (schema validation, data validation, ValidationMode)."
applyTo: "**/validation/**,**/validation.py"
---
# Validation Engine — Module-Specific Additions

Follows all rules in `copilot-instructions.md`.

## Separation of Concerns

Definition validation (Python object correctness) is handled by the registry manager. Data validation (DataFrame content correctness) is handled by the validation engine. These are separate activities with different inputs and purposes.

## Phase Details

- **Phase 1 (Schema)**: Checks column presence and null structural fields. Not mode-controlled — always ERROR semantics.
- **Phase 2 (Data)**: Checks type conformance and `Expect` constraints. Respects `ValidationMode`.
