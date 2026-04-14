---
description: "Use when creating or modifying exception classes in the KiteFS exception hierarchy."
applyTo: "**/exceptions.py"
---
# Exception Conventions

## Hierarchy

All exceptions inherit from `KiteFSError`. Always raise specific exception types — never bare `Exception` or generic `ValueError` for user-facing errors. See `docs/docs-03-03-api-contracts.md` for the full hierarchy.

## Actionable Messages (NFR-UX-001)

Every error message must include three things:

1. **What went wrong** — the nature of the failure
2. **What input caused it** — the specific value, name, or path that triggered the error
3. **How to fix it** — a concrete action the user can take

## Error Collection

For operations that validate multiple items (e.g., `apply()` validating all definitions), collect all errors before raising. Never fail on the first error alone (KTD-9).
