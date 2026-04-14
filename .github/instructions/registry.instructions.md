---
description: "Use when implementing or modifying the registry manager, apply logic, or registry schema."
applyTo: "**/registry/**,**/registry.py"
---
# Registry Manager Conventions

## Full Rebuild, Not Incremental (KTD-3)

`apply()` always regenerates the entire registry from definitions. The only value preserved from the previous registry is `last_materialized_at`. This ensures no drift between definitions and registry state.

## All-or-Nothing with Collected Errors (KTD-9)

Validate all definitions and collect all errors before deciding. If any error exists, the registry remains unchanged. The user fixes all issues in one pass — never fail-fast on the first error.

## Discovery via importlib (KTD-8)

Scan the `definitions/` directory, dynamically import `.py` files, and find `FeatureGroup` instances via `isinstance()` on module-level attributes. No decorators, naming conventions, or registration calls required.

## Deterministic Output

Write `registry.json` with `json.dumps(sort_keys=True, indent=2)` for Git-versionable, diff-friendly output.

## Schema and Contracts

See `docs/docs-03-02-internals-and-data.md` for the registry JSON schema. See `docs/docs-03-03-api-contracts.md` (BB-04) for registry manager method contracts.
