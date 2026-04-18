---
description: "Use when implementing or modifying the configuration manager or kitefs.yaml loading logic."
applyTo: "**/config/**,**/config.py"
---
# Configuration Manager — Module-Specific Additions

Follows all rules in `copilot-instructions.md`.

## Tier 0 — No Internal Dependencies

The configuration manager is a Tier 0 module. It must not import from any other KiteFS module. Other modules depend on it, not the other way around.

## Clear Errors on Invalid Config

If `kitefs.yaml` is missing or invalid, raise `ConfigurationError` with an actionable message: what field is wrong/missing, what the expected format is, and how to fix it (e.g., "Run `kitefs init` to create a project").

## Environment Variable Overrides

Configuration supports overrides via environment variables (e.g., `KITEFS_PROVIDER`, `KITEFS_STORAGE_ROOT`). Environment variables take precedence over `kitefs.yaml` values.
