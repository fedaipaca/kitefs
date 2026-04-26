# KiteFS — Copilot Instructions

## Hard Rules

These apply to all generated code — source files, tests, comments, docstrings, and user-facing messages. No exceptions.

1. **No internal references in code** — do not put doc paths (`docs/...`), document names, requirement IDs (`FR-*`, `NFR-*`), decision IDs (`KTD-*`), or building block IDs (`BB-*`) in source code, tests, comments, or docstrings. Describe behavior directly. These instruction files may reference docs; generated code may not. Task references (e.g., `Task 5`) are acceptable when genuinely needed.
2. **Type annotations everywhere** — Python 3.12+ syntax (`X | None`, `list[str]`) on all signatures, returns, and class attributes.
3. **Docstrings on everything** — every module, class, function, and method. Brief: one-line summary, parameters only when non-obvious.
4. **Actionable error messages** — every error must say what went wrong, what input caused it, and how to fix it.
5. **No bare exceptions** — use the hierarchy in `kitefs.exceptions`. Never raise `Exception` or `ValueError` for user-facing errors.
6. **Do not create commits** — make code changes only; the user handles git operations.

## Working Approach

- **Do not invent** — never fabricate APIs, modules, commands, or behavior that are not present in the code or clearly specified by the user.
- **Research before implementing** — read relevant docs to understand design intent, but apply engineering judgment. Docs are draft design references and may contain inconsistencies.
- **State uncertainty** — when unsure about a design decision, ask rather than guess. If you must proceed, state the assumption explicitly.
- **Flag conflicts** — when docs conflict with each other, with existing code, or with instructions, identify the conflict explicitly. Do not silently resolve it in either direction.
- **Reason from evidence** — base decisions on existing code, tests, and docs rather than assumptions.
- **When in doubt** — ask for clarification, reference official library docs using Context7 MCP, and make a reasonable decision taking into account your expertise and project goals. While doing so, document it in code comments and docstrings.

## Project Identity

KiteFS is a Python feature store library serving through a Python SDK and CLI: offline/online storage, registry, materialization, validation, and serving. Library-first — no server, no Docker, just `pip install kitefs`.

- **SDK**: `from kitefs import FeatureStore`
- **CLI**: Click-based (`kitefs init`, `kitefs apply`, `kitefs ingest`, …)

### Implementation Status

KiteFS is mid-build. The `docs/` directory describes the target architecture; the codebase represents partial progress toward that target. Key implications:

- **`FeatureStore`** is the documented SDK entry point but is **not yet implemented or exported**. It will be the root class that orchestrates all operations.
- When a documented module does not exist as code yet, treat the docs as the design spec and existing code conventions as the style guide. Do not assume unimplemented APIs exist — check the code first.

## Project Documentation

Docs are the **primary design reference** for product knowledge and architecture. They are draft and may contain internal inconsistencies or stale decisions. Consult them before implementing, but do not treat them as infallible specifications.

| Document                                   | Contents                                                     |
| ------------------------------------------ | ------------------------------------------------------------ |
| `docs/docs-00-01-reference-use-case.md`    | Real estate platform example; use for test data              |
| `docs/docs-00-02-flow-charts.md`           | Step-by-step flows for every command and method              |
| `docs/docs-01-project-charter.md`          | Vision, goals, personas, non-goals                           |
| `docs/docs-02-project-requirements.md`     | Functional requirements and non-functional requirements      |
| `docs/docs-03-01-architecture-overview.md` | Building blocks, dependency tiers, operational flows         |
| `docs/docs-03-02-internals-and-data.md`    | Registry schema, validation phases, behavioral rules         |
| `docs/docs-03-03-api-contracts.md`         | SDK/CLI signatures, exception hierarchy, internal interfaces |
| `docs/docs-04-implementation-guide.md`     | Phased task breakdown, dependency introduction order         |

When a task mentions a requirement, decision, or building block ID, look it up in the corresponding document.

## Source Precedence

- **Existing implemented modules** — current code and tests are the source of truth for behavior. Docs provide design intent and target state.
- **All modules not yet implemented** — docs are the design guide. Keep assumptions explicit.
- **When docs conflict with each other or with code** — flag the conflict explicitly. Prefer the least risky interpretation and state the assumption. Do not silently force code toward docs or vice versa.

## Tooling

- **Python >= 3.12** — use modern features (`|` unions, `match` statements)
- **`just`** — task runner (see `./justfile` for available commands and use those commands according to your need)
- **`uv`** — use uv to run commands not existing in `justfile`
- **`ruff`** — linter and formatter (configured in `pyproject.toml`); run `just format`
- **`pytest`** — tests in `tests/`, source in `src/kitefs/`

## Code Style

- **`src/kitefs/` layout** — all source under `src/kitefs/`
- **Frozen dataclasses** for definition types — `FeatureGroup`, `Feature`, `EntityKey`, etc. are immutable
- **ABC with `@abstractmethod`** for provider abstraction — not Protocol
- **Thin CLI, Fat SDK** — CLI delegates to the SDK. No business logic in CLI commands (exception: `kitefs init`)
- **All-or-nothing validation** — collect all errors before raising, never fail on the first error alone
- **Deterministic registry output** — `json.dumps(sort_keys=True, indent=2)`
- **Public API re-exports** — all public symbols importable from `from kitefs import ...`
- **Comments explain _why_, not _what_** — no restating what code already says
- **Descriptive names** — a reader should understand purpose without tracing back
- **Follow best practices** — follow clean code principles, community best practices, industry standards, and Python idioms. Do not over-engineer or over-abstract — prefer simplicity, clarity, and readability.

## Exception Hierarchy

All exceptions live in `kitefs.exceptions` and inherit from `KiteFSError`:

```
KiteFSError
├── ConfigurationError
├── DefinitionError
├── RegistryError
├── FeatureGroupNotFoundError
├── ValidationError
│   ├── SchemaValidationError
│   └── DataValidationError
├── IngestionError
├── RetrievalError
├── MaterializationError
├── JoinError
└── ProviderError
```

## Naming Conventions

| Entity                              | Convention                                      | Example                                |
| ----------------------------------- | ----------------------------------------------- | -------------------------------------- |
| Feature group / feature names       | `snake_case`                                    | `listing_features`, `net_area`         |
| Entity key / event timestamp fields | `snake_case`                                    | `listing_id`, `event_timestamp`        |
| Exception classes                   | `PascalCase` + `Error`                          | `DefinitionError`                      |
| Enum values                         | `SCREAMING_SNAKE_CASE`                          | `OFFLINE_AND_ONLINE`                   |
| Parquet files                       | `{source}_{YYYYMMDDTHHMMSS}_{short_id}.parquet` | `ing_20250101T120000_a1b2c3d4.parquet` |
| CLI options                         | `kebab-case`                                    | `--format json`                        |

## Module Organization

- Each major concern maps to its own module under `src/kitefs/` (definitions, config, registry, validation, join, etc.)
- `FeatureStore` is the SDK orchestration layer — it delegates to the appropriate manager or engine:
  - Registry operations → registry manager
  - Validation → validation engine
  - Offline read/write → offline store manager
  - Online read/write → online store manager
  - Joins → join engine
- Providers in `providers/` subpackage (base ABC + per-backend implementations)
- No circular imports
- Tier 0 modules (definitions, config, validation engine, join engine) have no internal dependencies; higher tiers depend only on lower tiers

## Architecture Principles

- **Provider abstraction** — all storage I/O goes through the provider layer. Never access filesystem or cloud storage directly from SDK, CLI, or engine code. Never import provider-specific libraries (`boto3`, `sqlite3`) outside the provider modules.
- **SDK as thin orchestrator** — `FeatureStore` delegates all work to managers and engines. It must never contain validation logic, storage I/O, or join algorithms directly.
- **Registry as full rebuild** — `apply()` regenerates the entire registry from definitions, preserving only `last_materialized_at`
- **Stateless engines** — validation and join engines receive data and config as arguments, return results. No I/O, no state
- **Append-only offline store** — ingestion never overwrites existing Parquet files. New data is written as new files in the partition

## Validation Behavior

Two phases: schema validation (Phase 1) always runs with ERROR semantics; data validation (Phase 2) respects `ValidationMode` (`ERROR`, `FILTER`, `NONE`). Phase 2 never runs if Phase 1 fails.

## Common Patterns

```python
# DO: Frozen dataclass
@dataclass(frozen=True)
class Feature:
    name: str
    dtype: FeatureType

# DON'T: Mutable dataclass
@dataclass
class Feature:
    name: str
    dtype: FeatureType
```

```python
# DO: Actionable error
raise FeatureGroupNotFoundError(
    f"Feature group '{name}' not found in registry. "
    f"Run `kitefs apply` to register your definitions."
)

# DON'T: Generic error
raise ValueError("Not found")
```

## Testing

- Write tests for every new module and feature
- Tests are organized into subdirectories mirroring `src/kitefs/` modules: `tests/cli/`, `tests/config/`, `tests/definitions/`, `tests/registry/`, `tests/providers/`, `tests/feature_store/`, `tests/exceptions/`, etc. Each subdirectory has an `__init__.py`
- Within each subdirectory, split tests by concern: `test_<concern>.py` (e.g., `tests/cli/test_init.py`, `tests/cli/test_apply.py`)
- `tests/e2e/` contains end-to-end tests that exercise cross-module workflows through the SDK and CLI — use these for integration-level coverage, not unit-level assertions
- Shared helpers live in `tests/helpers.py`; shared fixtures in `tests/conftest.py` — both at the top level
- Use descriptive test names: `test_<function>_<scenario>_<expected>`
- Always use `tmp_path` fixture for any test that reads/writes files — never write to the real project directory
- Test both **success paths** and **error paths** for every public function
- For error paths: validate that the correct exception type is raised with an actionable message
- Use the real estate reference use case entities (`listing_features`, `town_market_features`) as realistic test fixtures
- For unit tests, prefer minimal inline data over shared fixtures
- Run `just test` (or `uv run pytest`); `just check` (lint + tests) before considering work complete

## Dependencies

Introduce dependencies incrementally — do not add packages not yet needed by the current task.
