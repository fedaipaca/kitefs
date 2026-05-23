# KiteFS — Copilot Instructions

KiteFS is a Python 3.12+ feature store **library** for storing, validating, retrieving, materializing, discovering, and serving precomputed ML feature values via an SDK and CLI. Library-first, store-first.

Treat these as guardrails. For behavior, contracts, and shapes, follow `docs/`.

---

## Source of Truth

- Start at `docs/README.md` for the doc map and authority rules.
- `docs/02-product-requirements.md` … `docs/06-api-and-cli-contracts.md` are authoritative for requirements, behavior, architecture, storage, SDK, CLI, and exceptions.
- Do not invent APIs, flags, formats, workflows, or behavior — verify in docs or code.
- On conflict between docs / code / these instructions: surface the conflict, do not silently pick one.

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

- `docs/` — authoritative documentation and contracts.
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

## Product Boundary

**DO**:

- Implement documented SDK, CLI, storage, registry, validation, retrieval, materialization, discovery, and serving behavior.

**DO NOT** (unless explicitly required by docs or user request):

- Add servers, daemons, workers, background services, containers, or network service layers.
- Add feature computation engines, DAG schedulers, SQL orchestrators, model training, or model serving systems.
- Design around manual registry edits.

See `docs/00-project-context.md` and `docs/04-architecture.md`.

---

## Architecture Guardrails

- Core logic is storage-agnostic and depends on provider interfaces only.
- Provider-specific imports and behavior stay in provider layers.
- Validation and point-in-time join logic are stateless and perform no storage I/O unless docs require it.
- Treat feature definitions as source code; the registry is a deterministic derived artifact.
- Preserve point-in-time correctness. Event timestamps are the temporal anchor; future values must never leak into training data.
- All datetimes are UTC: treat naive as UTC, accept aware UTC, reject non-UTC aware datetimes, never convert zones.
- Keep local and AWS providers logically aligned; physical differences live inside their provider layers.

See `docs/03-system-behavior.md`, `docs/04-architecture.md`, `docs/05-data-and-storage-contracts.md`.

---

## Testing Strategy

- Use `pytest`; use `pytest-bdd` for BDD.
- Pick the narrowest layer that proves the contract:
  - `tests/unit/` — one module/class/function.
  - `tests/integration/` — cross-module flows (config, providers, stores, registry, SDK, CLI).
  - `tests/bdd/` — documented, user-visible SDK/CLI behavior and observable outcomes only.
- Add integration tests only when a unit test cannot verify the contract. Add BDD only for user-visible behavior or when the task is BDD-scoped.
- Reuse `tests/fixtures/` and `helpers/` before adding new utilities.
- Keep coverage proportional to the change. No speculative or ceremonial tests.
- Run narrowly first: `just test-unit`, `just test-integration`, `just test-bdd`, or `just test-file <path>`.

---

## Implementation Workflow

- One refined, single-purpose task at a time, aligned with `docs/02-product-requirements.md` through `docs/07-implementation-plan.md`.
- Read only the authoritative docs needed for the task before coding.
- Ship the smallest vertical slice that satisfies the task. No speculative abstractions or unrelated cleanup.
- Update or add matching tests in the same change (except BDD-only tasks, which use a dedicated prompt).
- If a BDD scenario fails against current code, treat it as an implementation gap — never weaken the scenario.
- Validate narrowly first; finish with `just clean-build` before declaring done.
- If docs are missing, ambiguous, or conflicting, stop and surface the gap.

---

## Tooling

- Prefer `just` recipes; check `justfile` or run `just`.
- Fall back to `uv` if no recipe exists.
- Use `just format` and `just lint-fix` instead of manual formatting edits.
- Completion gate: `just clean-build` passes.

---

## Change Boundaries

Unless the task explicitly requires otherwise, do not:

- broaden the public API,
- introduce runtime services,
- move business logic into the CLI,
- couple core logic to a specific storage backend,
- change storage contracts or serialization formats without matching docs and tests,
- silently resolve doc/code conflicts.

---

## When Unsure

- Check docs
- Check code
- Preserve contracts
- Keep the change small and explicit
- Surface uncertainty instead of guessing.
