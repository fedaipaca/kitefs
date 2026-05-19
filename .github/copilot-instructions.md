# KiteFS — Copilot Instructions

## Purpose

KiteFS is a Python 3.12+ feature store library for storing, validating, retrieving, materializing, discovering, and serving precomputed ML feature values through an SDK and CLI.

Use these instructions as project guardrails. For detailed behavior, contracts, storage formats, and API shapes, follow the files in `docs/`.

---

## Source of Truth

- Start with `docs/README.md` for the documentation map, reading order, and authority rules.
- Treat `docs/02-product-requirements.md` through `docs/06-api-and-cli-contracts.md` as authoritative for requirements, behavior, architecture, storage, SDK, CLI, and exception contracts.
- If docs, code, and these instructions conflict, call out the conflict instead of silently choosing one.
- Do not invent APIs, flags, storage formats, workflows, or behavior. Verify them in docs or code first.

---

## Project Directory Structure

### Top-level

- `docs/` - Authoritative project documentation, contracts, and implementation guidance.
- `src/kitefs/` - Main Python package for the library code.
- `tests/` - Unit, integration, BDD, fixtures, and test helper coverage.
- `helpers/` - Shared test support utilities used across the test suite.

### Source package

- `src/kitefs/cli/` - CLI entry points and presentation-layer command handling.
- `src/kitefs/config/` - Project configuration loading and runtime target selection.
- `src/kitefs/definitions/` - Feature definition types and related schema objects.
- `src/kitefs/errors/` - Shared KiteFS exception hierarchy.
- `src/kitefs/join_engine/` - Stateless point-in-time join logic.
- `src/kitefs/offline_store/` - Offline store coordination logic behind provider interfaces.
- `src/kitefs/online_store/` - Online store coordination logic behind provider interfaces.
- `src/kitefs/providers/` - Provider boundary plus local and AWS implementations.
- `src/kitefs/registry/` - Definition discovery, registry generation, and registry lookups.
- `src/kitefs/sdk/` - User-facing SDK orchestration.
- `src/kitefs/validation/` - Stateless structural and feature-value validation.

### Tests

- `tests/unit/` - Fast, isolated tests for individual modules and behaviors.
- `tests/integration/` - Cross-module tests for end-to-end library flows.
- `tests/bdd/` - Behavior-driven scenarios, features, and step definitions.
- `tests/fixtures/` - Reusable test data, definitions, and registry fixtures.
- `tests/helpers/` - Shared utilities and builders for test setup.

---

## Product Boundary

KiteFS is library-first and store-first.

- Do implement documented SDK, CLI, storage, registry, validation, retrieval, materialization, discovery, and serving behavior.
- Do not add servers, daemons, workers, background services, containers, or network service layers unless the docs explicitly require them.
- Do not add feature computation engines, DAG schedulers, SQL orchestration systems, model training systems, or model serving systems.
- Do not design workflows around manual registry edits.

See `docs/00-project-context.md` and `docs/04-architecture.md`.

---

## Architecture Guardrails

- Keep core logic storage-agnostic.
- Core modules depend on provider interfaces, not concrete local/AWS/vendor implementations.
- Keep provider-specific imports and behavior inside provider-specific layers.
- Keep validation and point-in-time join logic stateless where the architecture requires it.
- Validation and join engines must not perform storage I/O unless the docs explicitly require it.
- Treat feature definitions as source code and the registry as a deterministic derived artifact.
- Preserve point-in-time correctness for historical joins.
- Event timestamps are the temporal anchor. Future values must never leak into training data.
- All datetimes are UTC. Treat timezone-naive datetimes as UTC, accept timezone-aware UTC datetimes, reject non-UTC timezone-aware datetimes, and never convert between zones.
- Keep local and AWS providers logically aligned; differences should stay in provider-specific layers and physical read/write protocols.

See `docs/03-system-behavior.md`, `docs/04-architecture.md`, and `docs/05-data-and-storage-contracts.md`.

---

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

## Dependencies

- Prefer existing project dependencies.
- If a new dependency is justified, add it with `uv add`.
- Do not use `pip install` for project dependency changes.

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

---

## Testing

- Use `pytest` for all tests. Use `pytest-bdd` for BDD coverage.
- Keep tests proportional to the change. Add enough coverage to verify the documented behavior with confidence, but do not add speculative or ceremonial tests.
- Use `tests/unit/` for fast, isolated checks of one module, class, or function.
- Use `tests/integration/` for cross-module library flows that exercise collaboration between configuration, providers, stores, registry, SDK, and CLI layers.
- Always use `tests/README.md` Unit and Integration Test Style Guidelines, when working on unit tests and integration tests.
- Use `tests/bdd/` for documented, user-visible SDK and CLI behavior. Scenarios must describe public behavior and observable outcomes, not implementation detail.
- Prefer the narrowest test layer that proves the behavior. Add integration tests only when a unit test cannot verify the contract. Add BDD tests only for user-visible behavior or when the task is explicitly BDD-scoped.
- Reuse fixtures and helpers from `tests/fixtures/` and `helpers/` before introducing new test utilities.
- During development, run the narrowest relevant command first: `just test-unit`, `just test-integration`, `just test-bdd`, or `just test-file <path>`.

---

## Implementation Workflow

- Work one refined task at a time. Keep scope single-purpose and aligned with `docs/02-product-requirements.md` through `docs/07-implementation-plan.md`.
- Before coding, read only the authoritative docs needed for the task: requirements, behavior, architecture, storage contracts, API/CLI contracts, and task scope.
- Implement the smallest vertical slice that satisfies the task. Do not broaden APIs, add speculative abstractions, or bundle unrelated cleanup.
- For implementation tasks, write or update the matching tests in the same change, following the Testing section and the task's documented surface.
- For BDD-only tasks, their implementation will taken care with help of a separete and special prompt. Intentionally skipping instructions for that in this line.
- During implementation workflow, if a BDD scenario fails against the current codebase, treat that as a separate implementation gap. Do not weaken the scenario to fit the code.
- Validate with the narrowest relevant checks first, then finish with `just clean-build` before considering the task complete.
- If the docs are missing, ambiguous, or conflicting, stop and surface the gap instead of inventing behavior.

---

## Tooling and Commands

- Prefer `just` recipes first. Check `justfile` or run `just` to list available recipes.
- If a command is not available via `just`, use `uv`.
- Use project commands instead of manual formatting or lint-only edits:
  - `just format`
  - `just lint-fix`

### Verification of Completion

- Before considering a change complete, `just clean-build` should pass.

---

## Change Boundaries

Unless the task explicitly requires otherwise:

- do not broaden the public API
- do not introduce new runtime services
- do not move business logic into the CLI
- do not couple core logic to a specific storage backend
- do not change storage contracts or serialization formats without matching docs and tests
- do not silently resolve documentation/code conflicts

---

## If Unsure

- Check the docs.
- Check the existing code.
- Preserve existing contracts.
- Keep the implementation small and explicit.
- Call out uncertainty or conflicts instead of guessing.
