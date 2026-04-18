# KiteFS — Copilot Instructions

## Hard Rules

These apply to all generated code — source files, tests, comments, docstrings, and user-facing messages. No exceptions.

1. **No internal references in code** — do not put doc paths (`docs/...`), document names, requirement IDs (`FR-*`, `NFR-*`), decision IDs (`KTD-*`), or building block IDs (`BB-*`) in source code, tests, comments, or docstrings. Describe behavior directly. These instruction files may reference docs; generated code may not.
2. **Type annotations everywhere** — Python 3.12+ syntax (`X | None`, `list[str]`) on all signatures, returns, and class attributes.
3. **Docstrings on everything** — every module, class, function, and method. Brief: one-line summary, parameters only when non-obvious.
4. **Actionable error messages** — every error must say what went wrong, what input caused it, and how to fix it.
5. **No bare exceptions** — use the hierarchy in `kitefs.exceptions`. Never raise `Exception` or `ValueError` for user-facing errors.
6. **Do not create commits** — make code changes only; the user handles git operations.

## Project Identity

KiteFS is a Python feature store library serving through a Python SDK and CLI: offline/online storage, registry, materialization, validation, and serving. Library-first — no server, no Docker, just `pip install kitefs`.

- **SDK**: `from kitefs import FeatureStore`
- **CLI**: Click-based (`kitefs init`, `kitefs apply`, `kitefs ingest`, …)

## Project Documentation

Consult docs **before** implementing or making architecture decisions. These are for your research only — do not surface them in generated code.

| Document                                   | Contents                                                      |
| ------------------------------------------ | ------------------------------------------------------------- |
| `docs/docs-00-01-reference-use-case.md`    | Real estate platform example; use for test data               |
| `docs/docs-00-02-flow-charts.md`           | Step-by-step flows for every command and method               |
| `docs/docs-01-project-charter.md`          | Vision, goals, personas, non-goals                            |
| `docs/docs-02-project-requirements.md`     | Functional (FR-_) and non-functional (NFR-_) requirements     |
| `docs/docs-03-01-architecture-overview.md` | Building blocks (BB-\*), dependency tiers, operational flows  |
| `docs/docs-03-02-internals-and-data.md`    | Registry schema, validation phases, behavioral rules (KTD-\*) |
| `docs/docs-03-03-api-contracts.md`         | SDK/CLI signatures, exception hierarchy, internal interfaces  |
| `docs/docs-04-implementation-guide.md`     | Phased task breakdown, dependency introduction order          |

When a task mentions a requirement, decision, or building block ID, look it up in the corresponding document.

## Tooling

- **Python >= 3.12** — use modern features (`|` unions, `match` statements)
- **`just`** — task runner (see `./justfile` for available commands)
- **`uv`** — Use uv to run commands not existing in `justfile`
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
- **Follow best practices** — Follow clean code principles, community best practices, industry standards, and Python idioms. While doing so, do not over-engineer or over-abstract — prefer simplicity, clarity and readability.
- **When in doubt** - You can ask for clarification, or you can reference offical docs using Context7 MCP, or you can make a reasonable decision and document it in code comments and docstrings.

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

- Each building block (BB-01 through BB-10) maps to its own module under `src/kitefs/`
- Providers in `providers/` subpackage (base ABC + per-backend implementations)
- No circular imports
- Tier 0 modules (definitions, config, validation engine, join engine) have no internal dependencies; higher tiers depend only on lower tiers

## Architecture Principles

- **Provider abstraction** — all storage I/O goes through the provider layer. Never access filesystem or cloud storage directly from SDK, CLI, or engine code
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
- Run `just test` (or `uv run pytest`); `just check` (lint + tests) before considering work complete
- See testing.instructions.md for conventions

## Dependencies

Introduce dependencies incrementally — do not add packages not yet needed by the current task.

## Git Workflow

- One branch per task: `feat/task-{n}/{short-description}`
- Each task produces a self-contained, demonstrable outcome
