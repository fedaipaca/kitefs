# KiteFS — Copilot Instructions

## Project Identity

KiteFS (`kitefs`) is a Python feature store library providing offline/online feature storage, a registry, materialization, validation, and serving through a Python SDK and CLI. It is installed via `pip install kitefs` and designed for ML practitioners who need feature management with minimal operational overhead.

- **SDK**: Python API used in notebooks, scripts, and applications (`from kitefs import FeatureStore`)
- **CLI**: Command-line interface via Click (`kitefs init`, `kitefs apply`, `kitefs ingest`, etc.)
- **Library-first**: No running server, no Docker — just `pip install` and go

## Project Documentation

All project design documents live in the `docs/` directory. **Always consult them before implementing or making architectural decisions:**

- `docs/docs-00-01-reference-use-case.md` — Real estate listing platform example; use as test data source for integration tests
- `docs/docs-00-02-flow-charts.md` — Step-by-step flow charts for every CLI command and SDK method
- `docs/docs-01-project-charter.md` — Vision, goals, personas, non-goals
- `docs/docs-02-project-requirements.md` — Functional and non-functional requirements (FR-*, NFR-*)
- `docs/docs-03-01-architecture-overview.md` — Architecture principles, building blocks (BB-*), dependency tiers, operational flows
- `docs/docs-03-02-internals-and-data.md` — Registry JSON schema, validation phases, file naming conventions, behavioral rules (KTD-*)
- `docs/docs-03-03-api-contracts.md` — SDK/CLI method signatures, `where`/`select` parameter specs, exception hierarchy, internal interfaces
- `docs/docs-04-implementation-guide.md` — Phased task breakdown with traces to requirements; dependency introduction order

When a task references a requirement (e.g., FR-REG-001), a decision record (e.g., KTD-3), or a building block (e.g., BB-04), look it up in the corresponding document.

## Tooling

- **Python >= 3.12** — minimum version, use modern Python features (type unions with `|`, `match` statements where appropriate)
- **`uv`** — project tool for package management, virtual environments, and builds. Use `uv run` to execute commands, `uv sync` to install, `uv build` to package
- **`just`** — task runner. See `./justfile` for available commands
- **`ruff`** — linter and formatter (configured in `pyproject.toml`). Formatting enforced by ruff — run `just format`
- **`pytest`** — test runner. Tests in `tests/`, source in `src/kitefs/`

## Code Readability

- **Type annotations everywhere** — use Python 3.12+ syntax (`X | None`, `list[str]`, `dict[str, Any]`) on all function signatures, return types, and class attributes
- **Docstrings on all functions, classes, and methods** — public and internal alike. Keep them brief: one-line summary, parameters only when non-obvious
- **Module-level docstring** — every module should have a one-line docstring identifying its purpose
- **Descriptive names** — variables, functions, and classes should be self-explanatory. A reader should understand purpose without tracing back to the assignment
- **Comments explain *why*, not *what*** — don't restate what the code already says. Add comments for non-obvious trade-offs, workarounds, or business rules
- **Never reference internal doc paths in code** — no `docs/...` references in comments or docstrings. Code must be self-contained; instruction files handle doc navigation

## Code Style and Conventions

- **`src/kitefs/` layout** — all source code under `src/kitefs/`
- **Frozen dataclasses** for definition types (KTD-6) — `FeatureGroup`, `Feature`, `EntityKey`, etc. are immutable
- **ABC with `@abstractmethod`** for provider abstraction (KTD-14) — not Protocol
- **Thin CLI, Fat SDK** (KTD-4) — CLI is a thin wrapper that delegates to the SDK. Business logic lives in the SDK, never in CLI commands (exception: `kitefs init`)
- **All-or-nothing validation** (KTD-9) — collect all errors before raising, never fail on the first error alone
- **Deterministic registry output** — `json.dumps(sort_keys=True, indent=2)` for Git-versionable diffs
- **Actionable error messages** (NFR-UX-001) — every error must tell the user what went wrong and how to fix it
- **Exceptions** — use the hierarchy in `kitefs.exceptions`. Raise specific exceptions, never bare `Exception` or generic `ValueError` for user-facing errors
- **Public API re-exports** — all public symbols are importable from `from kitefs import ...` via `__init__.py`

## Exception Hierarchy

All exceptions live in `kitefs.exceptions` and inherit from `KiteFSError`. Always raise specific exception types — never bare `Exception` or generic `ValueError` for user-facing errors. Every error message must include: **what went wrong**, **what input caused it**, and **how to fix it** (NFR-UX-001). See `docs/docs-03-03-api-contracts.md` for the full hierarchy.

## Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Feature group / feature names | `snake_case` | `listing_features`, `net_area` |
| Entity key / event timestamp fields | `snake_case` | `listing_id`, `event_timestamp` |
| Exception classes | `PascalCase` + `Error` suffix | `DefinitionError` |
| Enum values | `SCREAMING_SNAKE_CASE` | `OFFLINE_AND_ONLINE`, `DATETIME` |
| Parquet files | `{source}_{YYYYMMDDTHHMMSS}_{short_id}.parquet` | `ing_20250101T120000_a1b2c3d4.parquet` |
| CLI options | `kebab-case` | `--format json`, `--storage-target` |

## Module Organization

- Each building block (BB-01 through BB-10) maps to its own module under `src/kitefs/`
- Exceptions live in a dedicated `exceptions.py` module
- Providers live in a `providers/` subpackage with a base ABC and per-backend implementations
- Keep modules focused: one building block per module, no circular imports
- Follow the dependency tier order in `docs/docs-03-01-architecture-overview.md` — Tier 0 modules (definitions, config, validation engine, join engine) have no internal dependencies; higher tiers depend only on lower tiers

## Validation Behavior

Two-phase validation: schema validation (Phase 1) always runs with ERROR semantics and is not mode-controlled; data validation (Phase 2) respects `ValidationMode` (`ERROR`, `FILTER`, `NONE`). Phase 2 never runs if Phase 1 fails. See `docs/docs-03-02-internals-and-data.md` for the full specification.

## Common Patterns

```python
# DO: Frozen dataclass for definitions (KTD-6)
@dataclass(frozen=True)
class Feature:
    name: str
    dtype: FeatureType

# DON'T: Mutable dataclass — definitions must be immutable
@dataclass
class Feature:
    name: str
    dtype: FeatureType
```

```python
# DO: Actionable error message (NFR-UX-001)
raise FeatureGroupNotFoundError(
    f"Feature group '{name}' not found in registry. "
    f"Run `kitefs apply` to register your definitions."
)

# DON'T: Generic error
raise ValueError("Not found")
```

All storage I/O **must** go through the provider layer (BB-09) — never access the filesystem or cloud storage directly from SDK, engine, or CLI code. See `docs/docs-03-03-api-contracts.md` (BB-09) for provider method contracts.

## Testing

- Write tests for every new module and feature
- Run `just test` (or `uv run pytest`) to verify changes; `just check` (lint + tests) before considering work complete
- See `.github/instructions/testing.instructions.md` for detailed testing conventions

## Architecture Principles

- **Provider abstraction** — all storage I/O goes through the provider layer (BB-09). Never access the filesystem or cloud storage directly from SDK or CLI code
- **Registry as full rebuild** (KTD-3) — `apply()` always regenerates the entire registry from definitions, preserving only `last_materialized_at`
- **Stateless engines** — the validation engine (BB-05) and join engine (BB-08) receive data and config as arguments, return results. No I/O, no state
- **Append-only offline store** — ingestion never overwrites existing Parquet files. New data is written as new files in the partition

## Dependencies

Introduce dependencies incrementally — do not add dependencies that are not yet needed by the current task. See `docs/docs-04-implementation-guide.md` for the phased dependency introduction order.

## Git Workflow

- One branch per task: `feat/task-{n}/{short-description}`
- Each task produces a self-contained, demonstrable outcome
- **Do not create commits** — make code changes only; the user handles all git operations
