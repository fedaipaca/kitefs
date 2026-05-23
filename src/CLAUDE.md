# Source Code Guidelines

Scope: these rules apply to source modules under `src/` (in addition to the root `CLAUDE.md` guardrails).

## Python Guidelines

Use Python 3.12-compatible idioms.

Prefer:

- precise type annotations
- PEP 604 unions (`X | None`)
- `dataclasses` when they reduce boilerplate
- `pathlib.Path` for paths
- small functions with explicit inputs and outputs
- standard library and existing dependencies before new packages
- explicit names over short or generic names
- use comments and docstrings generously but purposefully. They should help me and future maintainers understand intent, public behavior, edge cases, architecture boundaries, and non-obvious implementation decisions.

Avoid:

- speculative abstractions
- unused configuration knobs
- future-proofing without a concrete caller
- import-time I/O
- expensive imports in core modules
- provider-specific imports in storage-agnostic core modules

---

## Error Handling

- Expected user errors should not surface raw tracebacks.
- Error messages should be actionable.
- When possible, name the affected group, field, record, setting, path, or operation and indicate the next step.
- Public SDK methods and CLI-backed behavior should use the shared KiteFS exception hierarchy.

See `docs/06-api-and-cli-contracts.md`.

---

## CLI and SDK

- Keep SDK and CLI behavior aligned with `docs/06-api-and-cli-contracts.md`.
- Use Click 8.x patterns for CLI changes.
- Keep business logic in SDK/core modules, not CLI command handlers.
- Put presentation concerns in the CLI layer.
