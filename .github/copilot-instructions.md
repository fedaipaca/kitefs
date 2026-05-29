# KiteFS — Claude Instructions

KiteFS is a Python 3.12+ feature store **library** for storing, validating, retrieving, materializing, discovering, and serving precomputed ML feature values via an SDK and CLI. Library-first, store-first.

---

## Working Principles

These apply to every task, before and during implementation.

### Think before coding

- State your assumptions explicitly before implementing. If uncertain, ask.
- If multiple interpretations of the request exist, present them — don't pick silently.
- If a simpler approach exists than what was asked, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.
- Hidden confusion produces wasted work; surfaced confusion produces a better task.

### Simplicity first

- Ship the minimum code that solves the stated problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for scenarios that cannot occur given the contracts.
- If you wrote 200 lines and it could be 50, rewrite it. Ask yourself: "would a senior reviewer call this overcomplicated?" If yes, simplify before sending.

### Surgical changes

- Touch only what the task requires. Every changed line should trace directly to the request.
- Don't "improve" adjacent code, comments, or formatting while you're in the file.
- Don't refactor things that aren't broken.
- Match existing style, even if you would write it differently.
- If you notice unrelated dead code or issues, mention them — don't fix them silently.
- Clean up orphans **your** change created (now-unused imports, variables, helpers). Leave pre-existing dead code alone unless asked.

### Goal-driven execution

Turn every task into a verifiable goal before coding:

- "Add validation" → write tests for invalid inputs, then make them pass.
- "Fix the bug" → write a test that reproduces it, then make it pass.
- "Refactor X" → confirm tests pass before and after; behavior unchanged.

For multi-step tasks, state a short plan with a verification per step:

<step> → verify: <check>
<step> → verify: <check>
<step> → verify: <check>

Strong, verifiable success criteria let the work proceed without constant back-and-forth. If the criteria feel weak ("make it work"), tighten them before starting.

---

## Tech Stack

### Language & Packaging

- **Python 3.12+** — minimum and target.
- **uv** — env and deps. Use `uv add` and `uv run`. Never `pip install`.
- **uv_build** — build backend in `pyproject.toml`. Do not change.
- **just** — task runner. Prefer `just <recipe>`; run `just` to list recipes.

### Public Interfaces

- **click 8.x** — all `kitefs` CLI commands. Test with `CliRunner`. No business logic in handlers.
- **FeatureStore SDK** — single user-facing entry point: `from kitefs import FeatureStore`.

### Core Libraries

- **pandas** — `DataFrame` is the primary SDK input/output type.
- **pyarrow** — Parquet for offline store; `pyarrow.dataset` for partitioned reads.
- **PyYAML** — parses `kitefs.yaml`.

### Dev Toolchain

- **pytest** + **pytest-bdd** — tests (BDD in `tests/bdd/`).
- **Ruff** — `just lint`, `just lint-fix`, `just format`.
- **Pyright** — `standard` mode, Python 3.12. `just type-check`.

### Storage & Providers

Core stays storage-agnostic. Backend libraries are allowed **only** under `src/kitefs/providers/`.

| Backend          | Library             | Notes                                                |
| ---------------- | ------------------- | ---------------------------------------------------- |
| Offline — local  | `pyarrow`           | Parquet under `feature_store/data/offline_store/`    |
| Online — local   | `sqlite3` (stdlib)  | One table per online-capable feature group           |
| Registry — local | `json` (stdlib)     | `feature_store/registry.json`                        |
| Offline — AWS    | `pyarrow` + `boto3` | S3 Parquet, same partition layout as local           |
| Online — AWS     | `boto3`             | DynamoDB, one table per online-capable feature group |
| Registry — AWS   | `boto3`             | S3 `registry.json`                                   |

`boto3` imports are confined to `src/kitefs/providers/aws/`. The base package must import without AWS extras.

---

## Directory Layout

### Top-level

- `docs/` — feature definitions and contracts.
- `src/kitefs/` — library code.
- `tests/` — unit, integration, BDD, fixtures, helpers.
- `helpers/` — shared test support utilities.

### `src/kitefs/`

- `cli/` — CLI entry points and presentation.
- `config/` — config loading and runtime target selection.
- `definitions/` — feature definition types and schemas.
- `errors/` — shared exception hierarchy.
- `join_engine/` — stateless point-in-time joins.
- `offline_store/` — offline coordination behind provider interfaces.
- `online_store/` — online coordination behind provider interfaces.
- `providers/` — provider boundary; local and AWS implementations.
- `registry/` — definition discovery, generation, lookup.
- `sdk/` — user-facing orchestration.
- `validation/` — stateless structural and value validation.

### `tests/`

- `unit/` — fast, isolated module tests.
- `integration/` — cross-module library flows.
- `bdd/` — Gherkin scenarios, features and step definitions for user-visible SDK/CLI behavior.
- `fixtures/` — reusable test data, definitions, registries.
- `helpers/` — shared builders and setup utilities.

---

## Implementation Workflow

- One refined, single-purpose feature at a time. Feature definitions live in the relevant `docs/implementation_plan/feature-N.md` file.
- Contracts and structures used throughout the library live in `docs/implementation_plan/contracts.md`.
- If the feature is not clear or is ambiguous or conflicting with existing behavior, stop and surface the gap.
- Restate the task as a verifiable goal (see _Goal-driven execution_ section in this document) before writing code.
- Ship the smallest implementation that satisfies the feature. No speculative abstractions or unrelated cleanup.
- Update or add matching tests in the same change.
- Prefer `just` recipes; check `justfile` or run `just`.
- Fall back to `uv` if no recipe exists.
- Use `just format` and `just lint-fix` instead of manual formatting edits.
- Validate narrowly first; finish with `just clean-build` before declaring done.

---

## When to Read Specs

- **Do not** blindly read all specs.
- **Do** read the relevant sections when the feature definition is pointing for a reason.
- If the feature definition or contract is unclear, ambiguous, or conflicting with existing behavior, read the relevant spec sections to clarify before implementation. Then ask the user to clarify and verify your approach before implementation.

---

## Testing Strategy

- Use `pytest`; use `pytest-bdd` for BDD.
- Pick the narrowest layer that proves the contract:
  - `tests/unit/` — one module/class/function.
  - `tests/integration/` — cross-module flows (config, providers, stores, registry, SDK, CLI).
  - `tests/bdd/` — documented, user-visible SDK/CLI behavior and observable outcomes only.
- Add integration tests only when a unit test cannot verify the contract.
- Add BDD only for user-visible behavior or when the task is BDD-scoped.
- Reuse `tests/fixtures/` and `helpers/` before adding new utilities.
- Keep coverage proportional to the change. No speculative or ceremonial tests.

### BDD Tests

- BDD scenarios are defined in the feature definitions.
- Write feature scenarios and step definitions.
- Do not add speculative scenarios.
- Use concrete example data.
- Prefer existing fixtures and helpers before adding new support code.
- Keep step definitions deterministic, minimal, and readable.
- Use strong assertions; do not weaken tests to match current implementation.
- Run the narrowest relevant BDD validation command.
- If tests fail and tests correctly match the feature definition; then stop and report the failure. Do not edit the tests to force a pass.
- If a BDD scenario fails against current code, treat it as an implementation gap — never weaken the scenario.

---

## Change Boundaries

Unless the feature definition explicitly requires otherwise, do not:

- broaden the public API,
- introduce runtime services,
- move business logic into the CLI,
- couple core logic to a specific storage backend,
- change storage contracts or serialization formats without a reason,
- silently resolve conflicts.

---

## Architecture Guardrails

- Core logic is storage-agnostic and depends on provider interfaces only.
- Provider-specific imports and behavior stay in provider layers.
- Validation and point-in-time join logic are stateless and perform no storage I/O.
- Treat feature group definitions as source code; the registry is a deterministic derived artifact.
- Preserve point-in-time correctness. Event timestamps are the temporal anchor; future values must never leak into training data.
- All datetimes are UTC: treat naive as UTC, accept aware UTC, reject non-UTC aware datetimes, never convert zones.
- Keep local and AWS providers logically aligned; physical differences live inside their provider layers.
