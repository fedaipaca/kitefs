---
description: "Use when implementing or modifying the registry manager, apply logic, or registry schema."
applyTo: "**/registry/**,**/registry.py"
---
# Registry Manager — Module-Specific Additions

Follows all rules in `copilot-instructions.md`.

## Discovery via importlib

Scan the `definitions/` directory, dynamically import `.py` files, and find `FeatureGroup` instances via `isinstance()` on module-level attributes. No decorators, naming conventions, or registration calls required.

## Schema

See `docs/docs-03-02-internals-and-data.md` for the registry JSON schema.
