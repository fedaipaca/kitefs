# Source Code Guidelines

Scope: these rules apply to source modules under `src/` (in addition to the root `CLAUDE.md` guardrails).

## Python Style

Target Python 3.12 idioms.

Prefer:

- precise type annotations and PEP 604 unions (`X | None`)
- `dataclasses` when they reduce boilerplate
- `pathlib.Path` for filesystem paths
- small functions with explicit inputs and outputs
- explicit names over short or generic ones
- standard library and existing dependencies before new packages
- use docstrings and comments generously but purposefully. Explain intent, public behavior, edge cases, architecture boundaries, and non-obvious decisions.

Avoid:

- speculative abstractions and unused configuration knobs
- future-proofing without a concrete caller
- import-time I/O and expensive imports in core modules
- provider-specific imports in storage-agnostic core modules

## Error Handling

- Do not surface raw tracebacks for expected user errors.
- Make messages actionable: name the affected group, field, record, setting, path, or operation, and indicate the next step.
- Public SDK methods and CLI-backed behavior raise from the shared KiteFS exception hierarchy.

See `docs/06-api-and-cli-contracts.md`.

## CLI and SDK

- Keep SDK and CLI behavior aligned with `docs/06-api-and-cli-contracts.md`.
- Use Click 8.x patterns for CLI changes.
- Business logic lives in SDK/core modules; CLI handlers hold presentation only.
