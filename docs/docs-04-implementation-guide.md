# Kite Feature Store — Implementation Guide

> **Document Purpose:**
> This document is a step-by-step guide for building KiteFS from
> scratch. It is organized into phases, each grouping related tasks.
> Every task maps to a single feature branch and produces a
> demonstrable, self-contained outcome.
>
> After each merge, everything built so far is coherent and
> demonstrable. If the project stops at any task, what's merged
> still makes sense as a standalone piece of work.
>
> **Approach:**
>
> - **Vertical slices** over horizontal layers — each task delivers
>   an end-to-end outcome (even if narrow), not just an internal
>   module with no visible surface.
> - **Incremental dependencies** — each task lists only the packages
>   it introduces. No front-loading.
> - **Solo developer, MVP focus** — tasks are scoped for one person.
>   No over-engineering.
>
> **Constraints:**
>
> - **Python ≥ 3.12** (CON-001)
> - **`uv`** as the project tool (package management, virtual env, build)
> - Phases 1–5 cover all **Must Have** requirements
> - Phase 6 covers **Should Have** features — build if time permits
>
> **Relationship to other documents:**
>
> - Traces to: [Project Charter (docs-01)](docs-01-project-charter.md),
>   [Requirements (docs-02)](docs-02-project-requirements.md),
>   [Architecture Overview (docs-03-01)](docs-03-01-architecture-overview.md),
>   [Internals & Data (docs-03-02)](docs-03-02-internals-and-data.md),
>   [API Contracts (docs-03-03)](docs-03-03-api-contracts.md),
>   [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)
> - References the building block dependency tiers from
>   [docs-03-01 §3.3](docs-03-01-architecture-overview.md) to determine
>   task ordering
>
> **Owner:** Fedai Paça
> **Last Updated:** 2026-04-13
> **Status:** Draft

---

## Phase 1 — Project Foundation

**Phase goal:** An installable `kitefs` package with a working `kitefs init` command. By the end of this phase, anyone can `pip install kitefs` (from TestPyPI) and run `kitefs init` to scaffold a new project.

**What this phase covers:**

- Project tooling and package structure (Task 1)
- Exception hierarchy — the error contract for the entire system (Task 2)
- Definition types — the foundational data model all modules reference (Task 3)
- Configuration loading — how `kitefs.yaml` is parsed and validated (Task 4)
- The first runnable CLI command: `kitefs init` (Task 5)
- Proof that the package is pip-installable (Task 6)

**Building blocks touched:** BB-01 (CLI, partial), BB-03 (Definition Module), BB-10 (Configuration Manager)

---

### Task 1 — Project Scaffold & Tooling

|                     |                                                                                            |
| ------------------- | ------------------------------------------------------------------------------------------ |
| **Branch**          | `feat/task-1/project-setup`                                                                |
| **Goal**            | A buildable, lintable, testable Python package — the foundation everything else builds on. |
| **Building blocks** | None (infrastructure only)                                                                 |

**What to implement:**

- Initialize a `uv` project with Python ≥ 3.12.
- Create `pyproject.toml` with:
  - Package name: `kitefs`
  - `src/kitefs/` layout with an empty `__init__.py`
  - `tests/` directory with an empty `conftest.py`
- Configure `ruff` for linting (in `pyproject.toml`).
- Configure `pytest` as the test runner.
- Create `.gitignore` (Python defaults, `.venv/`, `dist/`, `*.egg-info`).
- Create a minimal `README.md`.

**Dependencies introduced:**

| Package  | Scope | Purpose                |
| -------- | ----- | ---------------------- |
| `ruff`   | dev   | Linting and formatting |
| `pytest` | dev   | Test runner            |

**Demonstrable outcome:**

- `uv run pytest` passes (empty test suite).
- `uv run ruff check` passes.
- The project structure is clean and ready for code.

**Traces:**

| Document                                                         | Look for                            | What you'll find                          |
| ---------------------------------------------------------------- | ----------------------------------- | ----------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §2.5 Constraints — CON-001, CON-002 | Python ≥ 3.12, single pip package         |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §1 Design Principles — AP-7         | Single-developer sustainability principle |

---

### Task 2 — Exception Hierarchy

|                     |                                                                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-2/exceptions`                                                                                                              |
| **Goal**            | The full exception tree (base class + 12 subclasses), importable from `kitefs.exceptions` — the error contract for the entire system. |
| **Building blocks** | None (cross-cutting concern)                                                                                                          |

**What to implement:**

Implement all exception classes defined in [API Contracts §4](docs-03-03-api-contracts.md):

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

Create `src/kitefs/exceptions.py` with these classes. Each exception carries an actionable message (NFR-UX-001). Write tests verifying:

- All exceptions are importable from `kitefs.exceptions`.
- Inheritance tree is correct (e.g., `SchemaValidationError` is a `ValidationError` is a `KiteFSError`).
- All are catchable via the base `KiteFSError`.

**Dependencies introduced:** None.

**Demonstrable outcome:**

- `from kitefs.exceptions import KiteFSError, ConfigurationError, ...` works.
- Tests pass.

**Traces:**

| Document                                                  | Look for                    | What you'll find                                     |
| --------------------------------------------------------- | --------------------------- | ---------------------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md) | §2.2 Usability — NFR-UX-001 | Actionable error messages requirement                |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md) | §4 Exception Hierarchy      | Full tree: classes, inheritance, when each is raised |

---

### Task 3 — Definition Module (BB-03)

|                     |                                                                                                                 |
| ------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-3/definition-module`                                                                                 |
| **Goal**            | All definition types importable from `kitefs` — the foundational data model that every other module depends on. |
| **Building blocks** | BB-03 (Definition Module)                                                                                       |

**What to implement:**

Implement the types defined in [API Contracts §1](docs-03-03-api-contracts.md) and detailed in [Internals §2.3](docs-03-02-internals-and-data.md):

- **Frozen dataclasses** (KTD-6): `FeatureGroup`, `Feature`, `EntityKey`, `EventTimestamp`, `JoinKey`, `Metadata`
- **Enums:** `FeatureType` (`STRING`, `INTEGER`, `FLOAT`, `DATETIME`), `StorageTarget` (`OFFLINE`, `OFFLINE_AND_ONLINE`), `ValidationMode` (`ERROR`, `FILTER`, `NONE`)
- **`Expect` fluent builder:** Frozen dataclass with `.not_null()`, `.gt(v)`, `.gte(v)`, `.lt(v)`, `.lte(v)`, `.one_of(v)` — each returns a new instance (immutable chain). Internal representation: tuple of constraint dicts.
- **`FeatureGroup.__post_init__`:** Normalize `features` list to a tuple sorted alphabetically by `name` (KTD-16).
- **Top-level `kitefs/__init__.py` re-exports:** All public symbols importable from `from kitefs import ...` per [API Contracts §1.1](docs-03-03-api-contracts.md).

Write tests covering:

- Immutability (frozen enforcement).
- `features` normalization (sorted tuple).
- `Expect` chaining produces correct constraint tuples.
- `dataclasses.asdict()` serialization roundtrip.
- Reference use case definitions are instantiable (`listing_features`, `town_market_features` from [docs-00-01](docs-00-01-reference-use-case.md)).

**Dependencies introduced:** None.

**Demonstrable outcome:**

- `from kitefs import FeatureGroup, Feature, EntityKey, EventTimestamp, Expect, JoinKey, Metadata, FeatureType, StorageTarget, ValidationMode` works.
- The reference use case feature groups can be instantiated.

**Traces:**

| Document                                                            | Look for                                       | What you'll find                                                       |
| ------------------------------------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------------------- |
| [Reference Use Case (docs-00-01)](docs-00-01-reference-use-case.md) | Full document                                  | Example definitions: listing_features, town_market_features            |
| [Requirements (docs-02)](docs-02-project-requirements.md)           | §1.1 Feature Group Definition — FR-DEF-001–007 | Requirement-level acceptance criteria                                  |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)          | §2.3 Definition Module (BB-03)                 | Behavioral rules, KTD-6 (frozen dataclasses), KTD-16 (sorted features) |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)           | §1 Public API Surface                          | Public imports, type signatures, Expect builder                        |

---

### Task 4 — Configuration Manager (BB-10)

|                     |                                                                                                           |
| ------------------- | --------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-4/configuration-manager`                                                                       |
| **Goal**            | Load and validate `kitefs.yaml` — the configuration foundation that the provider layer and SDK depend on. |
| **Building blocks** | BB-10 (Configuration Manager)                                                                             |

**What to implement:**

Implement BB-10 as described in [Internals §2.10](docs-03-02-internals-and-data.md):

- YAML loader that reads `kitefs.yaml` from a given path.
- Field validation:
  - `provider` — required, must be `local` or `aws`.
  - `storage_root` — required, path relative to project root (default: `./feature_store/`).
  - `aws.*` fields — required when `provider: aws` (`s3_bucket`, `s3_prefix`, `dynamodb_table_prefix`).
- Environment variable overrides (FR-CFG-005).
- Raises `ConfigurationError` (from Task 2) on invalid config with actionable messages identifying the specific issue (FR-CFG-003, FR-CFG-004).

Write tests covering: valid local config, valid AWS config, missing required fields, invalid provider value, malformed YAML, env var overrides.

**Dependencies introduced:**

| Package  | Scope   | Purpose             |
| -------- | ------- | ------------------- |
| `pyyaml` | runtime | Parse `kitefs.yaml` |

**Demonstrable outcome:**

- Config loads from a test fixture YAML file.
- Clear `ConfigurationError` on every invalid input case.

**Traces:**

| Document                                                   | Look for                            | What you'll find                                      |
| ---------------------------------------------------------- | ----------------------------------- | ----------------------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.9 Configuration — FR-CFG-001–006 | Requirement-level acceptance criteria                 |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §2.10 Configuration Manager (BB-10) | Internal structure, behavioral rules, error scenarios |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)  | §5.1 Configuration Manager          | Interface contract                                    |

---

### Task 5 — CLI Entry Point + `kitefs init`

|                     |                                                                                                           |
| ------------------- | --------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-5/cli-init`                                                                                    |
| **Goal**            | `kitefs init` is a runnable command that scaffolds a new KiteFS project — the first user-visible feature. |
| **Building blocks** | BB-01 (CLI, partial — `init` only)                                                                        |

**What to implement:**

Implement the CLI entry point and the `init` command as defined in [API Contracts §3.1](docs-03-03-api-contracts.md) and [Architecture §4.2](docs-03-01-architecture-overview.md):

- Click command group (`kitefs`) as the CLI entry point.
- `kitefs init [path]` subcommand that creates:
  - `kitefs.yaml` — default configuration (`provider: local`, `storage_root: ./feature_store/`).
  - `feature_store/definitions/` — with `__init__.py` and a minimal `example_features.py` (using definition types from Task 3).
  - `feature_store/data/offline_store/` — empty directory.
  - `feature_store/data/online_store/` — empty directory.
  - `feature_store/registry.json` — seeded as `{ "version": "1.0", "feature_groups": {} }`.
  - `.gitignore` — created or appended with `feature_store/data/`.
- If `kitefs.yaml` already exists → abort with error: "KiteFS project already initialized at this location."
- Register `kitefs` as a console script entry point in `pyproject.toml` (`[project.scripts]`).
- Exit code `0` on success, `1` on error. Errors to stderr, no tracebacks.

Write tests covering: successful init (verify all files/dirs created), re-init error, init at a custom path.

**Dependencies introduced:**

| Package | Scope   | Purpose       |
| ------- | ------- | ------------- |
| `click` | runtime | CLI framework |

**Demonstrable outcome:**

- `kitefs init` creates the full project scaffold.
- `kitefs init` again fails with a clear error.
- `kitefs --help` shows the available commands.

**Traces:**

| Document                                                         | Look for                           | What you'll find                                             |
| ---------------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------------ |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)            | §1.1 `kitefs init`                 | Detailed flow with .gitignore branching, key decisions table |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.10 CLI — FR-CLI-001, FR-CLI-002 | Requirement-level acceptance criteria                        |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §4.2 Initialize Project            | Sequence diagram, why init bypasses the SDK                  |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §3.4 KTD-4 (Thin CLI, Fat SDK)     | Decision record: why init is the exception to the pattern    |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.1 CLI (BB-01)                   | Behavioral rules, error scenarios table                      |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §3.1 `kitefs init`                 | CLI signature, args, scaffolded files, success/error output  |

---

### Task 6 — Package Build & Publish

|                     |                                                                                                 |
| ------------------- | ----------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-6/package-publish`                                                                   |
| **Goal**            | Prove that `kitefs` is pip-installable — the library-first distribution promise (AP-1) is real. |
| **Building blocks** | None (packaging concern)                                                                        |

**What to implement:**

- Finalize `pyproject.toml` metadata:
  - `description`, `license`, `classifiers`, `urls`, `python_requires = ">=3.12"`.
  - `[project.optional-dependencies]` section with `aws = ["boto3"]` placeholder for future Task 20.
- Verify `uv build` produces a valid wheel and sdist.
- Publish to **TestPyPI**.
- Validate in a **fresh virtual environment**:
  - `pip install -i https://test.pypi.org/simple/ kitefs`
  - `kitefs --help` shows commands.
  - `kitefs init` creates the scaffold.
- Document the publish workflow (brief note in README or a small CI step).

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- Install from TestPyPI in a clean environment → `kitefs init` produces a working project scaffold.
- This proves: AP-1 (library-first), CON-002 (single pip package), CON-005 (no running server).

**Traces:**

| Document                                                         | Look for                            | What you'll find                                  |
| ---------------------------------------------------------------- | ----------------------------------- | ------------------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §2.5 Constraints — CON-002, CON-005 | Single pip package, no running server             |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.10 CLI — FR-CLI-001              | CLI accessible via `kitefs` command after install |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §1 Design Principles — AP-1         | Library-first distribution principle              |

---

## Phase 2 — Define & Register

**Phase goal:** Users write feature definitions as Python code, register them via `kitefs apply`, and discover them via `kitefs list` / `kitefs describe`. The registry is a deterministic, Git-versionable JSON file.

**What this phase covers:**

- Provider abstraction layer with registry I/O (Task 7)
- Definition discovery, validation, and registry generation (Task 8)
- Feature group inspection commands (Task 9)

**Building blocks touched:** BB-09 (Provider Layer, partial), BB-04 (Registry Manager), BB-02 (SDK, partial)

---

### Task 7 — Provider Interface + Local Provider (Registry I/O)

|                     |                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------ |
| **Branch**          | `feat/task-7/provider-registry-io`                                                   |
| **Goal**            | The provider abstraction exists; `LocalProvider` can read and write `registry.json`. |
| **Building blocks** | BB-09 (Provider Layer — registry methods only)                                       |

**What to implement:**

Implement the provider interface as defined in [Internals §2.9](docs-03-02-internals-and-data.md):

- **Provider ABC** (`abc.ABC` with `@abstractmethod`) — define registry-related methods only for now:
  - `read_registry() -> str` — read the registry JSON string from storage. The provider knows its storage location from config.
  - `write_registry(data: str) -> None` — write the registry JSON string to storage.
  - Additional methods (offline, online) will be added in later tasks.
- **`LocalProvider`** implementation:
  - Reads/writes `registry.json` as a file on the local filesystem.
  - BB-04 (Registry Manager) handles JSON parsing/serialization and deterministic output (sorted keys, consistent formatting) for meaningful Git diffs (FR-REG-001). The provider does raw string I/O only.
- **Provider factory:** Given a config (from BB-10), instantiate the correct provider. For now, only `local` is implemented; `aws` raises a clear error.

Write tests covering: `LocalProvider` read/write roundtrip (string in, string out), factory instantiation.

**Dependencies introduced:** None (JSON and filesystem are stdlib).

**Demonstrable outcome:**

- `LocalProvider` reads and writes registry JSON strings at the configured storage root.
- Provider factory creates `LocalProvider` from a `provider: local` config.

**Traces:**

| Document                                                         | Look for                                                 | What you'll find                                               |
| ---------------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.8 Provider Abstraction — FR-PROV-001, FR-PROV-003     | Common interface, local provider requirement                   |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §3.4 KTD-2 (Provider Abstraction via Abstract Interface) | System-level decision record                                   |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.9 Provider Layer (BB-09)                              | Provider ABC, LocalProvider, KTD-14 (ABC not Protocol), KTD-15 |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §5 Internal Module Interfaces — Provider                 | Registry read/write method signatures                          |

---

### Task 8 — Registry Manager + `apply()` (BB-04 + BB-02 partial)

|                     |                                                                                                                            |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-8/registry-apply`                                                                                               |
| **Goal**            | `kitefs apply` discovers definitions, validates them, and generates `registry.json` — feature groups are now registerable. |
| **Building blocks** | BB-04 (Registry Manager), BB-02 (SDK — constructor + `apply()` only)                                                       |

**What to implement:**

**BB-04 (Registry Manager)** — as defined in [Internals §2.4](docs-03-02-internals-and-data.md):

- **Definition discovery:** Scan `definitions/` directory, dynamically import `.py` files via `importlib` (KTD-8), find `FeatureGroup` instances via `isinstance` checks on module-level attributes (FR-REG-003).
- **Definition validation** (all-or-nothing — collect all errors, KTD-9):
  - Duplicate feature group names → error.
  - `EventTimestamp` dtype must be `DATETIME` → error.
  - Feature types from the supported set → error.
  - Field names unique within group (entity key, event timestamp, features) → error.
  - Join key references: referenced group must exist, field name must match referenced entity key name, types must match → error.
- **Full registry rebuild** (KTD-3): Regenerate `registry.json` from scratch. Preserve `last_materialized_at` from the existing registry. Set `applied_at` ISO 8601 timestamp for each group.
- **Registry persistence:** Via provider (BB-09 from Task 7). BB-04 serializes definitions to a deterministic JSON string (`sort_keys=True, indent=2`) and calls the provider's `write_registry(data)` to persist it.
- **Lookup methods:** For use by later SDK operations — `get_group(name)`, `list_groups()`, `group_exists(name)` per [API Contracts §5.6](docs-03-03-api-contracts.md). Also `update_materialized_at(name, timestamp)` for Task 18 and `validate_query_params(...)` for Tasks 14, 16, 19.

**BB-02 (SDK — partial)** — as defined in [Internals §2.2](docs-03-02-internals-and-data.md) and [API Contracts §2.0–§2.1](docs-03-03-api-contracts.md):

- `FeatureStore.__init__`: Load config (BB-10), instantiate provider (BB-09), create registry manager (BB-04).
- `FeatureStore.apply()`: Delegate to BB-04 for definition discovery + registry regeneration.

**CLI `apply` command** — as defined in [API Contracts §3.2](docs-03-03-api-contracts.md):

- `kitefs apply` → resolve project root → instantiate `FeatureStore` → call `apply()` → render result.

Write tests covering: successful apply with single/multiple definitions, duplicate names rejected, invalid types rejected, field name collisions rejected, join key validation, all-or-nothing behavior (invalid definitions leave registry unchanged), `applied_at` timestamp set.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- `kitefs init` → write a definition in `definitions/` → `kitefs apply` → `registry.json` contains the registered feature group(s).
- Invalid definitions produce collected, actionable errors listing every issue.

**Traces:**

| Document                                                         | Look for                                           | What you'll find                                                       |
| ---------------------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------------------------- |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)            | §1.2 `kitefs apply`, §2.1 `apply()`                | Detailed CLI + SDK flow charts                                         |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.2 Feature Registry — FR-REG-001–004, FR-REG-007 | Requirement-level acceptance criteria                                  |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §4.3 Apply Definitions                             | Operational flow diagram                                               |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §3.4 KTD-3 (Registry as Full Rebuild)              | System-level decision record                                           |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.4 Registry Manager (BB-04)                      | Discovery, validation rules, KTD-8 (importlib), KTD-9 (all-or-nothing) |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.2 SDK (BB-02)                                   | Constructor wiring, apply() orchestration                              |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §3.1 Registry JSON schema                          | Registry data format reference                                         |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §2.0–§2.1 Constructor + `apply()`                  | SDK method signatures and return types                                 |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §3.2 `kitefs apply`                                | CLI contract                                                           |

---

### Task 9 — List & Describe Commands

|                     |                                                                                                         |
| ------------------- | ------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-9/list-describe`                                                                             |
| **Goal**            | `kitefs list` and `kitefs describe` show registered feature groups — feature discovery is now possible. |
| **Building blocks** | BB-02 (SDK — `list_feature_groups()`, `describe_feature_group()`), BB-01 (CLI — `list`, `describe`)     |

**What to implement:**

**SDK methods** — as defined in [API Contracts §2.6–§2.7](docs-03-03-api-contracts.md):

- `list_feature_groups(format, target)`:
  - Query registry via BB-04 for all groups.
  - Return `list[dict]` with summary fields: `name`, `owner`, `entity_key`, `storage_target`, `feature_count`.
  - Support `format="json"` (return JSON string) and `target` (write JSON to file).
  - Empty registry → return empty list (not an error).
- `describe_feature_group(name, format, target)`:
  - Look up single group by exact name via BB-04.
  - Return `dict` with full definition (all metadata, features, join keys, validation modes, `applied_at`, `last_materialized_at`).
  - Support `format="json"` and `target`.
  - Not found → `FeatureGroupNotFoundError`.

**CLI commands** — as defined in [API Contracts §3.4–§3.5](docs-03-03-api-contracts.md):

- `kitefs list [--format json] [--target <path>]` → human-readable table by default.
- `kitefs describe <name> [--format json] [--target <path>]` → human-readable key-value layout by default.

Write tests covering: list with groups, list empty, describe existing group, describe non-existent group, JSON format, file target output.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- After init + apply: `kitefs list` shows a table of registered groups. `kitefs describe listing_features` shows the full definition. JSON export works via `--format json` and `--target`.

**Traces:**

| Document                                                         | Look for                                                      | What you'll find                       |
| ---------------------------------------------------------------- | ------------------------------------------------------------- | -------------------------------------- |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)            | §1.5 `kitefs list`, §1.6 `kitefs describe`                    | Detailed flow charts                   |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.2 Feature Registry — FR-REG-005, FR-REG-006                | Discovery requirements                 |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.10 CLI — FR-CLI-005, FR-CLI-006, FR-CLI-012                | CLI output format requirements         |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §4.8 List Feature Groups, §4.9 Describe Feature Group         | Operational flow diagrams              |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §2.6 `list_feature_groups()`, §2.7 `describe_feature_group()` | SDK method signatures and return types |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §3.4 `kitefs list`, §3.5 `kitefs describe`                    | CLI contracts                          |

---

## Phase 3 — Ingest & Query

**Phase goal:** Data enters the offline store via `kitefs ingest` and can be queried back via `get_historical_features()` (single group, no joins yet). This is the first data path through the system.

**What this phase covers:**

- Parquet I/O with Hive-style partitioning in the local provider (Task 10)
- The validation engine — schema and data validation with three modes (Task 11)
- The offline store manager — partitioning and filtered reads (Task 12)
- End-to-end ingestion via SDK and CLI (Task 13)
- Historical retrieval for a single feature group (Task 14)

**Building blocks touched:** BB-09 (Provider — offline methods), BB-05 (Validation Engine), BB-06 (Offline Store Manager), BB-02 (SDK — `ingest()`, `get_historical_features()` partial)

---

### Task 10 — Local Provider: Offline Store I/O

|                     |                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-10/provider-offline-io`                                                      |
| **Goal**            | `LocalProvider` can read and write Parquet files in Hive-style partitioned directories. |
| **Building blocks** | BB-09 (Provider Layer — offline store methods)                                          |

**What to implement:**

Extend the provider ABC and `LocalProvider` with offline store methods per [API Contracts §5.5](docs-03-03-api-contracts.md):

- **`write_offline(group_name, partition_path, file_name, df: DataFrame) -> None`:**
  - Write a single Parquet file to a specific partition path (e.g., `year=2024/month=03`).
  - The provider handles raw I/O only — BB-06 (Offline Store Manager) derives partition paths and generates file names before calling this method.
  - Use PyArrow for Parquet writes. Atomic write (write-to-temp-then-rename on local).
- **`read_offline(group_name, partition_paths: list[str]) -> DataFrame`:**
  - Read Parquet files from specific partition paths (provided by BB-06 after pruning).
  - Returns a combined DataFrame from all files across the listed partitions.
  - Returns an empty DataFrame if no files exist.
  - Use PyArrow for Parquet reads.
- **`list_partitions(group_name) -> list[str]`:**
  - List available partition paths for a feature group (e.g., `["year=2024/month=01", "year=2024/month=02"]`).
  - Used by BB-06 for partition pruning decisions.

The layout is identical for both local and S3 (FR-ING-006) — the abstraction ensures this. Note: partition derivation, file naming (`{source}_{timestamp}_{id}.parquet`), and pruning logic are BB-06's responsibility (Task 12), not the provider's. The provider is a primitive I/O layer.

Write tests covering: write creates correct directory structure, read returns correct data from specified partitions, list_partitions returns available paths, append-only (second write doesn't overwrite first), empty partition read returns empty DataFrame.

**Dependencies introduced:**

| Package   | Scope   | Purpose                                     |
| --------- | ------- | ------------------------------------------- |
| `pyarrow` | runtime | Parquet read/write, Hive-style partitioning |
| `pandas`  | runtime | DataFrame interface (CON-003)               |

**Demonstrable outcome:**

- Tests write Parquet to `year=.../month=.../` partitions and read back from specified partition paths.
- Tests pass realistic file names (e.g., `ing_20240315_abc.parquet`) as arguments — the provider stores whatever name it receives; naming conventions are BB-06's responsibility (Task 12).

**Traces:**

| Document                                                   | Look for                                          | What you'll find                                                |
| ---------------------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.3 Data Ingestion — FR-ING-006, FR-ING-007      | Parquet layout, file naming requirements                        |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.4 Offline Store — FR-OFF-001                   | Storage format requirement                                      |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §2.9 Provider Layer (BB-09)                       | Provider ABC offline methods                                    |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §3.3 Offline Store Layout                         | Directory structure, Hive-style partitioning                    |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)  | §5 Internal Interfaces — Provider offline methods | Method signatures: write_offline, read_offline, list_partitions |

---

### Task 11 — Validation Engine (BB-05)

|                     |                                                                                                               |
| ------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-11/validation-engine`                                                                              |
| **Goal**            | A stateless data validator that enforces schema and business-level expectations with configurable strictness. |
| **Building blocks** | BB-05 (Validation Engine)                                                                                     |

**What to implement:**

Implement BB-05 as defined in [Internals §2.5](docs-03-02-internals-and-data.md):

- **Phase 1 — Schema validation** (always runs, always-ERROR semantics):
  - Column presence: all declared columns must exist in the DataFrame.
  - Null structural columns: entity key and event timestamp must not contain nulls.
  - If schema fails → `SchemaValidationError`. Data validation (Phase 2) is never reached.
- **Phase 2 — Data validation** (mode-dependent):
  - Type checks: each value conforms to the declared `FeatureType`.
  - Feature expectations: `not_null`, `gt`, `gte`, `lt`, `lte`, `one_of`.
  - Mode behaviors:
    - `ERROR` → reject entire operation, raise `DataValidationError` with full report.
    - `FILTER` → exclude failing records, return passing records + report.
    - `NONE` → skip Phase 2 entirely.
- **Validation report:** Passed count, failed count, per-failure details (entity key, field, expected constraint, actual value) (FR-VAL-007).
- The engine is **stateless** — receives schema definition + DataFrame as arguments, returns a result. No I/O, no module dependencies.

Write tests covering: every expectation type, all three modes, schema as hard gate (fails before data validation), report structure, edge cases (empty DataFrame, all rows filtered).

**Dependencies introduced:** None new (operates on Pandas DataFrames already available from Task 10).

**Demonstrable outcome:**

- All expectation types validated correctly.
- ERROR mode rejects, FILTER mode excludes, NONE mode skips.
- Reports include actionable per-failure details.

**Traces:**

| Document                                                         | Look for                                | What you'll find                                              |
| ---------------------------------------------------------------- | --------------------------------------- | ------------------------------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.7 Validation Engine — FR-VAL-001–009 | Requirement-level acceptance criteria                         |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §3.4 KTD-5                              | Decision: separate definition validation from data validation |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.5 Validation Engine (BB-05)          | Two-phase design, mode behaviors, report structure            |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §5.3 Validation Engine                  | Interface contract                                            |

---

### Task 12 — Offline Store Manager (BB-06)

|                     |                                                                                                                                     |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-12/offline-store-manager`                                                                                                |
| **Goal**            | The offline store manager handles partitioning logic and filtered reads — the orchestration layer between the SDK and the provider. |
| **Building blocks** | BB-06 (Offline Store Manager)                                                                                                       |

**What to implement:**

Implement BB-06 as defined in [Internals §2.6](docs-03-02-internals-and-data.md):

- **Partition column derivation:** Extract `year` and `month` from `event_timestamp` for Hive-style partitioning.
- **Write orchestration:** Add partition columns, delegate to provider's `write_offline()` with source prefix.
- **Read orchestration with where-filter:**
  - Translate the unified `where` format (see FR-OFF-007) into partition-level pruning (month-level) and row-level filtering.
  - MVP restriction: only `event_timestamp` field with `gt`/`gte`/`lt`/`lte` operators.
  - Delegate partition-pruned read to provider, then apply row-level `event_timestamp` filter.
- **Read for materialization:** Read all data for a group (no filtering) — used by `materialize()` later.

Write tests covering: partition columns derived correctly, filtered reads return correct subsets, partition pruning reduces I/O, full-group read returns everything.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- Data partitioned correctly by year/month on write.
- Filtered reads with time-range `where` return expected subsets.

**Traces:**

| Document                                                   | Look for                                     | What you'll find                   |
| ---------------------------------------------------------- | -------------------------------------------- | ---------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.3 Data Ingestion — FR-ING-004, FR-ING-006 | Append-only, Hive-style layout     |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.4 Offline Store — FR-OFF-007              | Unified where format               |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §2.6 Offline Store Manager (BB-06)           | Partitioning logic, KTD-10, KTD-11 |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §3.3 Offline Store Layout                    | Directory structure reference      |

---

### Task 13 — Ingest Operation (end-to-end)

|                     |                                                                                        |
| ------------------- | -------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-13/ingest`                                                                  |
| **Goal**            | `kitefs ingest` works end-to-end — the first data path through the system is complete. |
| **Building blocks** | BB-02 (SDK — `ingest()`), BB-01 (CLI — `ingest`)                                       |

**What to implement:**

**SDK `ingest()` method** — as defined in [API Contracts §2.2](docs-03-03-api-contracts.md):

- Look up feature group definition via BB-04 (Registry Manager).
- Resolve input to DataFrame:
  - `DataFrame` → use directly.
  - `str` ending in `.csv` → load via Pandas.
  - `str` ending in `.parquet` → load via PyArrow/Pandas.
  - Other → raise `IngestionError`.
- Drop extra columns not in the definition (FR-ING-002 — silently).
- Run schema validation via BB-05 (always runs).
- Run data validation via BB-05 (per ingestion validation mode).
- Write validated data via BB-06 (Offline Store Manager) with `ing` source prefix.
- Return result with rows written and partitions affected.

**CLI `ingest` command** — as defined in [API Contracts §3.3](docs-03-03-api-contracts.md):

- `kitefs ingest <feature_group_name> <file_path>` → delegate to `store.ingest()`.

Write tests covering: DataFrame ingestion, CSV ingestion, Parquet ingestion, extra column dropping, missing column rejection, null structural column rejection, all three validation modes, append-only behavior.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- `kitefs init` → write definition → `kitefs apply` → `kitefs ingest listing_features data.csv` → Parquet files in `feature_store/data/offline_store/listing_features/year=.../month=.../`.
- SDK DataFrame ingestion works in tests.
- Validation modes behave correctly (ERROR rejects, FILTER excludes, NONE skips).

**Traces:**

| Document                                                         | Look for                              | What you'll find                              |
| ---------------------------------------------------------------- | ------------------------------------- | --------------------------------------------- |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)            | §1.4 `kitefs ingest`, §2.2 `ingest()` | Detailed CLI + SDK flow charts                |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.3 Data Ingestion — FR-ING-001–007  | Requirement-level acceptance criteria         |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.10 CLI — FR-CLI-004                | CLI ingest command requirement                |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §4.4 Ingest Data                      | Operational flow diagram                      |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §2.2 `ingest()`                       | SDK method signature, parameters, return type |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §3.3 `kitefs ingest`                  | CLI contract                                  |

---

### Task 14 — Historical Retrieval (single group, no join)

|                     |                                                                                                                            |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-14/historical-retrieval-single`                                                                                 |
| **Goal**            | `get_historical_features()` retrieves data from a single feature group — training dataset generation for the no-join case. |
| **Building blocks** | BB-02 (SDK — `get_historical_features()`, non-join path)                                                                   |

**What to implement:**

Implement the non-join path of `get_historical_features()` as defined in [API Contracts §2.3](docs-03-03-api-contracts.md):

- **Parameter validation:** Group exists in registry, `select` references valid features (or `"*"`), `where` uses valid field/operator (MVP: `event_timestamp` only, `gt`/`gte`/`lt`/`lte` only). Invalid params → `RetrievalError`.
- **Read:** Delegate to BB-06 with partition pruning via `where`.
- **Select application:** Keep entity key + event timestamp (always) + selected features. `"*"` returns all fields.
- **Retrieval-gate validation:** Run BB-05 on selected features per the group's `offline_retrieval_validation` mode.
- **Return:** Pandas DataFrame.

No join logic in this task — that's Task 16.

Write tests covering: select as list, select as `"*"`, where filtering, retrieval validation modes, invalid select rejected, invalid where rejected, empty result (not an error).

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- `store.get_historical_features(from_="listing_features", select="*")` returns a DataFrame with all ingested data.
- `where={"event_timestamp": {"gte": ..., "lte": ...}}` filters correctly.
- Retrieval validation modes work.

**Traces:**

| Document                                                         | Look for                                                            | What you'll find                        |
| ---------------------------------------------------------------- | ------------------------------------------------------------------- | --------------------------------------- |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)            | §2.3 `get_historical_features()`                                    | Detailed SDK flow chart                 |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.4 Offline Store — FR-OFF-001, FR-OFF-002, FR-OFF-006, FR-OFF-007 | Retrieval and where-filter requirements |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §4.5 Get Historical Features                                        | Operational flow diagram                |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §2.3 `get_historical_features()`                                    | SDK method signature (non-join path)    |

---

## Phase 4 — Point-in-Time Joins

**Phase goal:** The core feature store differentiator — point-in-time correct training datasets that prevent data leakage. After this phase, the full `get_historical_features()` API is complete.

**What this phase covers:**

- The stateless join engine using `pd.merge_asof` (Task 15)
- Full historical retrieval with join support (Task 16)

**Building blocks touched:** BB-08 (Join Engine), BB-02 (SDK — `get_historical_features()` join path)

---

### Task 15 — Join Engine (BB-08)

|                     |                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-15/join-engine`                                                              |
| **Goal**            | A stateless point-in-time join engine that merges DataFrames with temporal correctness. |
| **Building blocks** | BB-08 (Join Engine)                                                                     |

**What to implement:**

Implement BB-08 as defined in [Internals §2.8](docs-03-02-internals-and-data.md):

- **Point-in-time join** using `pd.merge_asof`:
  - Sort both DataFrames by event timestamp.
  - Join on the declared join key (matching base group's join key field to joined group's entity key).
  - Direction: `backward` — for each base record, match only the most recent right-side record where `joined.event_timestamp ≤ base.event_timestamp` (KTD-13).
- **Null fill:** Unmatched base rows get null-filled joined columns. Base rows are never dropped (FR-OFF-005).
- **Column conflict resolution** (FR-OFF-010):
  - Conflicting joined columns are prefixed with `{joined_group_name}_`.
  - Base group columns are never renamed.
  - Joined group's `event_timestamp` always conflicts → always prefixed.
  - Join key column appears once (from base group — not duplicated).

The engine is **stateless** — receives DataFrames + join metadata, returns a merged DataFrame. No I/O, no module dependencies.

Write tests using reference use case data:

- PIT correctness: each listing matched with market data at or before its sale date.
- Unmatched rows have null-filled joined columns.
- Column naming matches FR-OFF-010.
- Data leakage prevention: future market data is never joined to past listings.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- Unit tests with reference use case data prove point-in-time correctness.
- Data leakage is demonstrably prevented.

**Traces:**

| Document                                                            | Look for                                                | What you'll find                                      |
| ------------------------------------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------- |
| [Reference Use Case (docs-00-01)](docs-00-01-reference-use-case.md) | Full document                                           | Test data: listings joined with town market data      |
| [Requirements (docs-02)](docs-02-project-requirements.md)           | §1.4 Offline Store — FR-OFF-003, FR-OFF-005, FR-OFF-010 | PIT correctness, null fill, column naming             |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)          | §2.8 Join Engine (BB-08)                                | Algorithm, KTD-13 (merge_asof), column conflict rules |

---

### Task 16 — Historical Retrieval with Join

|                     |                                                                                   |
| ------------------- | --------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-16/historical-retrieval-join`                                          |
| **Goal**            | The full `get_historical_features()` API — including point-in-time correct joins. |
| **Building blocks** | BB-02 (SDK — `get_historical_features()` join path)                               |

**What to implement:**

Extend `get_historical_features()` with the join path as defined in [API Contracts §2.3](docs-03-03-api-contracts.md) and [Architecture §4.5](docs-03-01-architecture-overview.md):

- **Join parameter validation:**
  - Each joined group must be registered.
  - Base group must have a join key referencing the joined group.
  - MVP single-join limit enforced: `join` accepts at most one group → `JoinError` if more (FR-OFF-009).
- **Read joined group:** Via BB-06 with partition pruning (base group's max `event_timestamp` as upper bound).
- **Select on joined group:** `select` as dict keyed by group name. `"*"` for a joined group returns all features + `event_timestamp`; entity key not included (it's the join key from base).
- **Validate joined data:** At retrieval gate per the joined group's `offline_retrieval_validation` mode.
- **Call BB-08** (Join Engine) with base DataFrame, joined DataFrame, join metadata, and joined group name.
- **Return:** Merged DataFrame.

Write tests covering the full reference use case workflow:

- Ingest both `listing_features` and `town_market_features`.
- Call `get_historical_features(from_="listing_features", select={...}, join=["town_market_features"])`.
- Verify PIT correctness across the joined result.
- Verify column naming, null fills, and single-join limit enforcement.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- Full reference use case: ingest both groups → historical retrieval with join → PIT-correct training dataset.
- Data leakage prevention is demonstrable.
- This completes the offline store's core value proposition.

**Traces:**

| Document                                                            | Look for                            | What you'll find                                 |
| ------------------------------------------------------------------- | ----------------------------------- | ------------------------------------------------ |
| [Reference Use Case (docs-00-01)](docs-00-01-reference-use-case.md) | Full document                       | End-to-end join scenario for test verification   |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)               | §2.3 `get_historical_features()`    | Detailed SDK flow chart (join branch)            |
| [Requirements (docs-02)](docs-02-project-requirements.md)           | §1.4 Offline Store — FR-OFF-002–010 | Full offline retrieval + join requirements       |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md)    | §4.5 Get Historical Features        | Operational flow diagram (join branch)           |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)           | §2.3 `get_historical_features()`    | SDK method signature (join path, select as dict) |

---

## Phase 5 — Online Serving

**Phase goal:** The complete offline-to-online pipeline — materialize latest values and serve them at low latency. After this phase, all Must Have requirements are implemented.

**What this phase covers:**

- SQLite-backed online store in the local provider (Task 17)
- Materialization: offline → online sync (Task 18)
- Online feature serving: single entity key lookup (Task 19)

**Building blocks touched:** BB-09 (Provider — online methods), BB-07 (Online Store Manager), BB-02 (SDK — `materialize()`, `get_online_features()`)

---

### Task 17 — Local Provider: Online Store I/O

|                     |                                                                    |
| ------------------- | ------------------------------------------------------------------ |
| **Branch**          | `feat/task-17/provider-online-io`                                  |
| **Goal**            | `LocalProvider` can read and write the SQLite-backed online store. |
| **Building blocks** | BB-09 (Provider Layer — online store methods)                      |

**What to implement:**

Extend the provider ABC and `LocalProvider` with online store methods:

- **`write_online(group_name, df: DataFrame) -> None`:**
  - One table per feature group (KTD-12).
  - Entity key as `PRIMARY KEY`.
  - Full overwrite: delete all existing rows, write new ones in a single atomic transaction (NFR-REL-002).
  - Type mapping per [Internals §3.2](docs-03-02-internals-and-data.md): STRING→TEXT, INTEGER→INTEGER, FLOAT→REAL, DATETIME→TEXT (ISO 8601).
  - Tables are created lazily on first write.
- **`read_online(group_name, entity_key_name, entity_key_value) -> dict | None`:**
  - Single-key lookup by entity key value.
  - Return `dict` of column→value if found, `None` if not found.
  - Raise `ProviderError` if the table does not exist (BB-07 translates this into a `MaterializationError` with a user-friendly message).

Write tests covering: write → read roundtrip, entity key lookup returns correct data, missing key returns `None`, full overwrite replaces previous data, table-not-exists raises `ProviderError`, type mapping correctness.

**Dependencies introduced:** None new (`sqlite3` is Python stdlib).

**Demonstrable outcome:**

- Tests show SQLite write → read roundtrip, correct type mapping, and full overwrite semantics.

**Traces:**

| Document                                                   | Look for                                    | What you'll find                    |
| ---------------------------------------------------------- | ------------------------------------------- | ----------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.5 Online Store — FR-ONL-001              | SQLite for local provider           |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.8 Provider Abstraction — FR-PROV-003     | Local provider requirement          |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §2.9 Provider Layer (BB-09)                 | Provider ABC online methods, KTD-12 |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §3.2 Type Mapping, §3.4 Online Store Schema | SQLite schema, type mapping rules   |

---

### Task 18 — Online Store Manager + Materialize (BB-07)

|                     |                                                                                          |
| ------------------- | ---------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-18/materialize`                                                               |
| **Goal**            | `kitefs materialize` syncs the latest feature values from offline to online store.       |
| **Building blocks** | BB-07 (Online Store Manager), BB-02 (SDK — `materialize()`), BB-01 (CLI — `materialize`) |

**What to implement:**

**BB-07 (Online Store Manager)** — as defined in [Internals §2.7](docs-03-02-internals-and-data.md):

- **Latest-per-entity extraction:** Group by entity key, select the row with maximum `event_timestamp`.
- **Write to online store:** Via provider's `write_online()` — full overwrite per group.

**SDK `materialize()` method** — as defined in [API Contracts §2.5](docs-03-03-api-contracts.md):

- If `feature_group_name` provided: materialize that group only. Validate it's `OFFLINE_AND_ONLINE` → `MaterializationError` if `OFFLINE` only (FR-MAT-002).
- If `None`: materialize all `OFFLINE_AND_ONLINE` groups. A failure in one group does not prevent others (FR-MAT-001).
- Read offline data via BB-06, extract latest-per-entity via BB-07, write online via BB-07.
- If offline store is empty for a group → skip with warning.
- Update `last_materialized_at` in registry for each successfully materialized group.
- Return result with groups processed and entity counts.

**CLI `materialize` command** — as defined in [API Contracts §3.6](docs-03-03-api-contracts.md):

- `kitefs materialize [feature_group_name]` → delegate to `store.materialize()`.

Write tests covering: single group materialization, all-group materialization, OFFLINE-only rejection, empty offline store skipped, idempotency (running twice = same state), `last_materialized_at` updated, entity count reported.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- `kitefs materialize town_market_features` → SQLite `online.db` has latest values per entity key.
- Running again is idempotent — same state.
- Entity counts reported on success.

**Traces:**

| Document                                                         | Look for                              | What you'll find                                  |
| ---------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------- |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)            | §1.3 `kitefs materialize`             | Detailed flow chart                               |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.6 Materialization — FR-MAT-001–005 | Requirement-level acceptance criteria             |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.10 CLI — FR-CLI-007                | CLI materialize command requirement               |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §4.7 Materialize                      | Operational flow diagram                          |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.7 Online Store Manager (BB-07)     | Latest-per-entity extraction, write orchestration |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §2.5 `materialize()`                  | SDK method signature and return type              |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §3.6 `kitefs materialize`             | CLI contract                                      |

---

### Task 19 — Online Feature Serving

|                     |                                                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-19/online-serving`                                                                                       |
| **Goal**            | `get_online_features()` retrieves the latest feature values for a single entity key — the serving path is complete. |
| **Building blocks** | BB-02 (SDK — `get_online_features()`)                                                                               |

**What to implement:**

Implement `get_online_features()` as defined in [API Contracts §2.4](docs-03-03-api-contracts.md):

- **Parameter validation:**
  - Feature group must be `OFFLINE_AND_ONLINE` → `RetrievalError` if `OFFLINE` only.
  - `where` must use the entity key field with `eq` operator only (MVP restriction).
  - `select` references valid features (or `"*"`).
- **Lookup:** Delegate to BB-07 → provider's `read_online()`.
- **Table-not-exists check:** If `materialize()` has never been run → `MaterializationError` with message: "No online data for '{name}'. Run `kitefs materialize` first."
- **Select application:** Keep structural columns (entity key, event timestamp) + selected features.
- **Return:** `dict | None` — dict of feature values if found, `None` if entity key not found.

No validation engine on the serving path — data was validated at ingestion time.

Write tests covering: successful lookup, missing entity key returns `None`, OFFLINE-only group rejected, unmaterialized group error, select as list, select as `"*"`.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- After materialize: `store.get_online_features(from_="town_market_features", select="*", where={"town_id": {"eq": 1}})` returns a dict.
- Missing key → `None`.
- This completes all Must Have requirements for the local provider.

**Traces:**

| Document                                                         | Look for                                   | What you'll find                                    |
| ---------------------------------------------------------------- | ------------------------------------------ | --------------------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.5 Online Store — FR-ONL-001, FR-ONL-002 | Serving requirements, where format                  |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §4.6 Get Online Features                   | Operational flow diagram                            |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §2.4 `get_online_features()`               | SDK method signature, return type, MVP restrictions |

---

## Phase 6 — AWS Provider & Should-Have Features

**Phase goal:** Extend to a production-grade AWS backend and add developer experience features. These are **Should Have** — build if time permits. Each task is independently valuable; the phase does not need to be completed in full.

**What this phase covers:**

- AWS provider: S3 + DynamoDB backend (Task 20)
- Registry sync/pull between local and remote (Task 21)
- Mock data generation for development (Task 22)
- Smart sampling from remote stores (Task 23)

**Building blocks touched:** BB-09 (Provider — `AWSProvider`), BB-02 (SDK — `sync_registry()`, `pull_registry()`, `generate_mock_data()`, `pull_remote_sample()`)

---

### Task 20 — AWS Provider

|                     |                                                                                        |
| ------------------- | -------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-20/aws-provider`                                                            |
| **Goal**            | The full workflow works with S3 + DynamoDB — the same API, a production-grade backend. |
| **Building blocks** | BB-09 (Provider Layer — `AWSProvider`)                                                 |

**What to implement:**

Implement `AWSProvider` in BB-09 as defined in [Internals §2.9](docs-03-02-internals-and-data.md):

- **Offline store (S3):** Same Parquet/Hive-style layout as local. Read/write via `boto3` S3 client.
- **Online store (DynamoDB):** One table per feature group. Entity key as partition key. Full overwrite via `batch_write_item`. Single-key lookup via `get_item`.
- **Registry (S3):** Read/write `registry.json` to/from the configured S3 bucket + prefix.
- **Credentials:** Standard AWS credential chain (env vars, `~/.aws/credentials`, IAM role) — no credential management in KiteFS (NFR-SEC-001).
- Register `boto3` as optional dependency: `pip install kitefs[aws]` in `pyproject.toml`.

Write integration tests (e.g., using `localstack` or `moto`) covering: the full workflow (apply → ingest → materialize → online serve) with AWS provider config.

**Dependencies introduced:**

| Package | Scope                            | Purpose                |
| ------- | -------------------------------- | ---------------------- |
| `boto3` | optional runtime (`[aws]` extra) | S3 and DynamoDB access |

**Demonstrable outcome:**

- Full workflow works with `provider: aws` in `kitefs.yaml`.
- `pip install kitefs[aws]` adds `boto3`.

**Traces:**

| Document                                                   | Look for                                                          | What you'll find                         |
| ---------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.8 Provider Abstraction — FR-PROV-002, FR-PROV-004, FR-PROV-005 | AWS provider requirements                |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §2.4 Security — NFR-SEC-001                                       | Credential chain, no KiteFS-managed auth |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §2.9 Provider Layer (BB-09)                                       | AWSProvider section, S3/DynamoDB details |

---

### Task 21 — Registry Sync & Pull

|                     |                                                                                                           |
| ------------------- | --------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-21/registry-sync-pull`                                                                         |
| **Goal**            | `kitefs registry-sync` and `kitefs registry-pull` transfer the registry between local and remote storage. |
| **Building blocks** | BB-02 (SDK — `sync_registry()`, `pull_registry()`), BB-01 (CLI — `registry-sync`, `registry-pull`)        |
| **Depends on**      | Task 20 (AWS Provider)                                                                                    |

**What to implement:**

SDK methods and CLI commands as defined in [API Contracts §2.8, §3.7](docs-03-03-api-contracts.md):

- `sync_registry()`: Upload local `registry.json` to configured remote S3 location. Full overwrite.
- `pull_registry()`: Download remote `registry.json` and overwrite local copy.
- Both require remote provider configuration in `kitefs.yaml`.
- Raise `ConfigurationError` if no remote provider configured, `ProviderError` if transfer fails.

**Dependencies introduced:** None new (uses `boto3` from Task 20).

**Demonstrable outcome:**

- Registry uploaded to S3 and downloaded back. Local overwrite on pull verified.

**Traces:**

| Document                                                  | Look for                                                 | What you'll find        |
| --------------------------------------------------------- | -------------------------------------------------------- | ----------------------- |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)     | §1.7 `kitefs registry-sync`, §1.8 `kitefs registry-pull` | Detailed flow charts    |
| [Requirements (docs-02)](docs-02-project-requirements.md) | §1.2 Feature Registry — FR-REG-008, FR-REG-009           | Sync/pull requirements  |
| [Requirements (docs-02)](docs-02-project-requirements.md) | §1.10 CLI — FR-CLI-008                                   | CLI command requirement |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md) | §2.8 `sync_registry()`, `pull_registry()`                | SDK method signatures   |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md) | §3.7 `kitefs registry-sync`, `kitefs registry-pull`      | CLI contracts           |

---

### Task 22 — Mock Data Generation

|                     |                                                                                            |
| ------------------- | ------------------------------------------------------------------------------------------ |
| **Branch**          | `feat/task-22/mock-data`                                                                   |
| **Goal**            | `kitefs mock` generates synthetic test data for rapid development — zero real data needed. |
| **Building blocks** | BB-02 (SDK — `generate_mock_data()`), BB-01 (CLI — `mock`)                                 |

**What to implement:**

As defined in [Requirements §1.11](docs-02-project-requirements.md):

- Type-aware random data generator:
  - `STRING` → random strings.
  - `INTEGER` → random integers (respecting `gt`/`gte`/`lt`/`lte` expectations if defined).
  - `FLOAT` → random floats (respecting expectations).
  - `DATETIME` → random timestamps within a configurable time range.
- Generates realistic entity key values.
- Respects all defined feature expectations (not_null, value ranges, one_of).
- Ingests into local offline store with `mock` source prefix (FR-MOCK-003).
- Local provider only (FR-MOCK-001).

**Dependencies introduced:** None new (stdlib `random`/`datetime` sufficient).

**Demonstrable outcome:**

- `kitefs mock listing_features` → Parquet files in offline store conforming to schema and expectations.

**Traces:**

| Document                                                  | Look for                                     | What you'll find                      |
| --------------------------------------------------------- | -------------------------------------------- | ------------------------------------- |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)     | §1.9 `kitefs mock`                           | Detailed flow chart                   |
| [Requirements (docs-02)](docs-02-project-requirements.md) | §1.11 Mock Data Generation — FR-MOCK-001–003 | Requirement-level acceptance criteria |
| [Requirements (docs-02)](docs-02-project-requirements.md) | §1.10 CLI — FR-CLI-009                       | CLI mock command requirement          |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md) | §3.8 `kitefs mock`                           | CLI contract                          |

---

### Task 23 — Smart Sampling

|                     |                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-23/smart-sampling`                                                         |
| **Goal**            | `kitefs sample` pulls a representative subset from remote data for local development. |
| **Building blocks** | BB-02 (SDK — `pull_remote_sample()`), BB-01 (CLI — `sample`)                          |
| **Depends on**      | Task 20 (AWS Provider)                                                                |

**What to implement:**

As defined in [Requirements §1.12](docs-02-project-requirements.md):

- Connect to remote provider (AWS), read from remote offline store.
- Support filtering by:
  - Absolute row count.
  - Percentage.
  - `event_timestamp` time range.
- Write sampled data to local offline store with `sample` source prefix (FR-SAM-003).
- Local provider only (requires remote connection details in config).
- Sampled data is immediately queryable via standard SDK methods (FR-SAM-001).

**Dependencies introduced:** None new (uses `boto3` from Task 20).

**Demonstrable outcome:**

- Data from remote S3 offline store sampled into local offline store.

**Traces:**

| Document                                                  | Look for                              | What you'll find                      |
| --------------------------------------------------------- | ------------------------------------- | ------------------------------------- |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)     | §1.10 `kitefs sample`                 | Detailed flow chart                   |
| [Requirements (docs-02)](docs-02-project-requirements.md) | §1.12 Smart Sampling — FR-SAM-001–003 | Requirement-level acceptance criteria |
| [Requirements (docs-02)](docs-02-project-requirements.md) | §1.10 CLI — FR-CLI-010                | CLI sample command requirement        |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md) | §3.9 `kitefs sample`                  | CLI contract                          |

---

## Appendix A — Task Dependency Graph

```
Phase 1 — Project Foundation
  Task 1  → Task 2  → Task 3  → Task 4  → Task 5  → Task 6
  (scaffold) (errors) (types) (config) (CLI init) (publish)

Phase 2 — Define & Register
  Task 7  → Task 8  → Task 9
  (provider) (apply) (list/describe)

Phase 3 — Ingest & Query
  Task 10 → Task 11 → Task 12 → Task 13 → Task 14
  (parquet) (valid.) (offline) (ingest) (retrieval)

Phase 4 — Point-in-Time Joins
  Task 15 → Task 16
  (join)   (retrieval+join)

Phase 5 — Online Serving
  Task 17 → Task 18 → Task 19
  (sqlite) (materialize) (serve)

Phase 6 — AWS & Extras
  Task 20 → Task 21
  (AWS)    (sync/pull)
  Task 20 → Task 23
  (AWS)    (sampling)
  Task 22 (independent)
  (mock)
```

## Appendix B — Dependency Introduction Order

| Task  | Runtime Dependencies Introduced  | Dev Dependencies Introduced |
| ----- | -------------------------------- | --------------------------- |
| 1     | —                                | `ruff`, `pytest`            |
| 2–3   | —                                | —                           |
| 4     | `pyyaml`                         | —                           |
| 5     | `click`                          | —                           |
| 6–9   | —                                | —                           |
| 10    | `pyarrow`, `pandas`              | —                           |
| 11–19 | —                                | —                           |
| 20    | `boto3` (optional `[aws]` extra) | —                           |
| 21–23 | —                                | —                           |

## Appendix C — Requirement Traceability

> _Maps each functional requirement to the task(s) that implement it._

| Requirement Category         | FR IDs                                                       | Task(s)         |
| ---------------------------- | ------------------------------------------------------------ | --------------- |
| Feature Group Definition     | FR-DEF-001 through FR-DEF-007                                | 3               |
| Feature Registry             | FR-REG-001 through FR-REG-004, FR-REG-007                    | 8               |
| Feature Registry (discovery) | FR-REG-005, FR-REG-006                                       | 9               |
| Feature Registry (sync/pull) | FR-REG-008, FR-REG-009                                       | 21              |
| Data Ingestion               | FR-ING-001 through FR-ING-007                                | 10, 12, 13      |
| Offline Store & Historical   | FR-OFF-001, FR-OFF-002, FR-OFF-006, FR-OFF-007               | 10, 12, 14      |
| Offline Store (joins)        | FR-OFF-003 through FR-OFF-005, FR-OFF-008 through FR-OFF-010 | 15, 16          |
| Online Store & Serving       | FR-ONL-001, FR-ONL-002                                       | 17, 19          |
| Materialization              | FR-MAT-001 through FR-MAT-005                                | 18              |
| Validation Engine            | FR-VAL-001 through FR-VAL-009                                | 11              |
| Provider Abstraction         | FR-PROV-001, FR-PROV-003, FR-PROV-005                        | 7, 10, 17       |
| Provider Abstraction (AWS)   | FR-PROV-002, FR-PROV-004                                     | 20              |
| Configuration                | FR-CFG-001 through FR-CFG-006                                | 4               |
| CLI                          | FR-CLI-001, FR-CLI-002                                       | 5               |
| CLI                          | FR-CLI-003                                                   | 8               |
| CLI                          | FR-CLI-004                                                   | 13              |
| CLI                          | FR-CLI-005, FR-CLI-006, FR-CLI-012                           | 9               |
| CLI                          | FR-CLI-007                                                   | 18              |
| CLI                          | FR-CLI-008                                                   | 21              |
| CLI                          | FR-CLI-009                                                   | 22              |
| CLI                          | FR-CLI-010                                                   | 23              |
| CLI (cross-cutting)          | FR-CLI-011                                                   | 5, 8, 9, 13, 18 |
| Mock Data Generation         | FR-MOCK-001 through FR-MOCK-003                              | 22              |
| Smart Sampling               | FR-SAM-001 through FR-SAM-003                                | 23              |
