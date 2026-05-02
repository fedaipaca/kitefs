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
>   No over-engineering. MVP here means a working alpha version that
>   demonstrates KiteFS end-to-end in a simple, minimalist, yet looks like
>   realistic use-case project. (e.g., a simple demo built on the reference use case).
>   The goal is to prove the library works, not to polish every edge. If a
>   feature isn't needed to run the demo, it can wait.
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

### Task 1 — Project Scaffold & Tooling - (DONE)

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

### Task 2 — Exception Hierarchy - (DONE)

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

### Task 3 — Definition Module (BB-03) - (DONE)

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

### Task 4 — Configuration Manager (BB-10) - (DONE)

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

### Task 5 — CLI Entry Point + `kitefs init` - (DONE)

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

### Task 6 — Package Build & Publish - (DONE)

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
- Document the usage instructions for installing from TestPyPI and running `kitefs init` in the README.

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
- Definition discovery (Task 8a), definition validation rules (Task 8b), registry manager + `apply()` (Task 8c), SDK + CLI `apply` (Task 8d)
- Feature group inspection commands (Task 9)

**Building blocks touched:** BB-09 (Provider Layer, partial), BB-04 (Registry Manager), BB-02 (SDK, partial)

---

### Task 7 — Provider Interface + Local Provider (Registry I/O) - (DONE)

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

### Task 8a — Definition Discovery - (DONE)

|                     |                                                                                                                                  |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-8a/definition-discovery`                                                                                              |
| **Goal**            | A pure discovery function that scans `definitions/`, imports `.py` files via `importlib` (KTD-8), and returns `FeatureGroup` instances — the first step of the apply pipeline. |
| **Building blocks** | BB-04 (Registry Manager — discovery only)                                                                                        |

**What to implement:**

Implement `_discover_definitions(definitions_path: Path) -> list[FeatureGroup]` as a private module-level function in a new `src/kitefs/registry.py` module:

- Walk `.py` files in `definitions/` (non-recursive, skip `__init__.py`, ignore non-`.py` files).
- Dynamically import each file via `importlib.util.spec_from_file_location` + `loader.exec_module` (KTD-8).
- Inspect all module-level attributes with `isinstance(attr, FeatureGroup)` to collect instances (FR-REG-003). No decorators, naming conventions, or registration calls required.
- Import errors (`SyntaxError`, `ImportError`, etc.) → `DefinitionError` with file path and original error included in the message.
- No `FeatureGroup` instances found in any file → `DefinitionError`: "No feature group definitions found in `{definitions_path}/`. Create a `.py` file with a `FeatureGroup` instance."
- No provider or config dependencies — uses only `definitions.py`, `exceptions.py`, and stdlib `importlib`/`pathlib` for filesystem discovery.

Write tests covering: single group discovered, multiple groups across multiple files, `__init__.py` skipped, non-`FeatureGroup` module-level attributes ignored, empty directory error, `SyntaxError` in a file produces `DefinitionError` with file path, `ImportError` in a file, non-`.py` files ignored.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- Unit tests prove discovery works for valid definition files and produces clear, actionable errors for broken or empty `definitions/` directories.

**Traces:**

| Document                                                   | Look for                                  | What you'll find                                               |
| ---------------------------------------------------------- | ----------------------------------------- | -------------------------------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.2 Feature Registry — FR-REG-003        | Discovery via `isinstance`, no decorators or naming convention |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §2.4 Registry Manager (BB-04)             | KTD-8 (importlib discovery mechanism)                         |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)  | §5.6 Registry Manager                     | Discovery as part of the BB-04 interface                       |

---

### Task 8b — Definition Validation Rules - (DONE)

|                     |                                                                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-8b/definition-validation-rules`                                                                                            |
| **Goal**            | A pure validation function that checks `list[FeatureGroup]` against all structural rules, collecting all errors before reporting (KTD-9). |
| **Building blocks** | BB-04 (Registry Manager — validation only)                                                                                            |

**What to implement:**

Implement `_validate_definitions(groups: list[FeatureGroup]) -> list[str]` as a private module-level function in `src/kitefs/registry.py`:

- Returns a list of error message strings. Empty list means all definitions are valid.
- Collects **all** errors before returning — never fails on the first error alone (KTD-9).
- **Individual group validation** (runs first, per group):
  - `EventTimestamp.dtype` must be `FeatureType.DATETIME` → error.
  - Feature `dtype` must be a member of the `FeatureType` enum → error.
  - Field names must be unique within the group across `entity_key.name`, `event_timestamp.name`, and all `feature.name` values → error.
- **Cross-group validation** (runs second, across the full list):
  - Duplicate feature group names → error.
  - Join key `referenced_group` must name an existing group → error.
  - Join key `field_name` must match the `entity_key.name` of the referenced group → error with rename suggestion.
  - Join key type compatibility: look up the field in the base group whose `name` matches `join_key.field_name` (could be the `entity_key` or a `Feature`), then verify its `dtype` matches the `entity_key.dtype` of the referenced group → error listing both types and both groups.
- No I/O, provider, or config dependencies — pure logic on definition objects.

Write tests covering: one test per validation rule, multiple errors from multiple groups collected in one call, valid definitions return empty list, reference use case definitions (`listing_features` + `town_market_features` from [Reference Use Case](docs-00-01-reference-use-case.md)) pass validation.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- All structural validation rules are enforced with actionable error messages.
- A single call with multiple broken definitions returns all errors at once, not just the first.

**Traces:**

| Document                                                         | Look for                                  | What you'll find                                              |
| ---------------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.2 Feature Registry — FR-REG-004        | Unique feature group names requirement                        |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.2 Feature Registry — FR-REG-007        | Join key relationship metadata                                |
| [Reference Use Case (docs-00-01)](docs-00-01-reference-use-case.md) | Full document                          | Example definitions for validation pass test                  |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §3.4 KTD-5                                | Separation of definition validation from data validation      |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.4 Registry Manager (BB-04)             | Validation rules, KTD-9 (all-or-nothing collected errors)     |

---

### Task 8c — Registry Manager + `apply()` (BB-04) - (DONE)

|                     |                                                                                                                                     |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-8c/registry-manager-apply`                                                                                               |
| **Goal**            | `RegistryManager` orchestrates discovery → validation → serialization → persistence, and exposes lookup methods for later SDK operations. |
| **Building blocks** | BB-04 (Registry Manager — full)                                                                                                     |
| **Depends on**      | Task 8a (discovery), Task 8b (validation)                                                                                           |

**What to implement:**

**`ApplyResult`** — frozen dataclass in `src/kitefs/registry.py`:

- `registered_groups: tuple[str, ...]` — names of all registered feature groups.
- `group_count: int` — number of groups registered.

**`RegistryManager`** class in `src/kitefs/registry.py`:

- **Constructor** `__init__(self, provider: StorageProvider, definitions_path: Path) -> None`: stores provider and definitions path; loads existing registry from provider for `last_materialized_at` preservation and to serve lookup queries.
- **`apply(self) -> ApplyResult`** — full orchestration (KTD-3):
  1. Call `_discover_definitions(self._definitions_path)`.
  2. Call `_validate_definitions(groups)`.
  3. If any errors → raise `DefinitionError` with all errors joined; registry remains unchanged (KTD-9).
  4. Serialize each group to the registry JSON schema via `_serialize_group()`.
  5. Preserve `last_materialized_at` from the existing registry for each group that already exists.
  6. Set `applied_at` to the current UTC timestamp (ISO 8601) for each group.
  7. Build the full registry dict: `{ "version": "1.0", "feature_groups": { ... } }`.
  8. Write `json.dumps(registry, sort_keys=True, indent=2)` via `provider.write_registry()` (FR-REG-001).
  9. Update internal state; return `ApplyResult`.
- **`_serialize_group(group: FeatureGroup) -> dict`** — private helper: converts a `FeatureGroup` to the registry JSON schema dict (enum values as `.value` strings, features with `expect` constraints as list of dicts, join keys, metadata, validation modes, storage target).
- **Lookup methods** — for use by later SDK operations per [API Contracts §5.6](docs-03-03-api-contracts.md):
  - `get_group(self, name: str) -> FeatureGroup` — reconstruct and return `FeatureGroup` from loaded registry; raise `FeatureGroupNotFoundError` if not found.
  - `list_groups(self) -> list[dict]` — return summary dicts (`name`, `owner`, `entity_key`, `storage_target`, `feature_count`) for all groups.
  - `group_exists(self, name: str) -> bool`.
- **Stubs with full signatures** (implementation in later tasks):
  - `update_materialized_at(self, group_name: str, timestamp: datetime) -> None` — for Task 18.
  - `validate_query_params(self, from_: str, select: list[str] | str | dict[str, list[str] | str], where: dict[str, dict[str, Any]] | None, join: list[str] | None, method: str) -> None` — for Tasks 14, 16, 19.

Write tests covering: successful apply single/multiple groups, `applied_at` is valid ISO 8601, `last_materialized_at` preserved across re-apply and `null` for newly added groups, all-or-nothing behavior (invalid definitions → `DefinitionError` raised, existing registry unchanged), deterministic JSON output (`sort_keys=True, indent=2`), `version: "1.0"` present, `get_group()` returns correct group, `get_group()` with unknown name raises `FeatureGroupNotFoundError`, `list_groups()` and `group_exists()` correct, deleted definition files vanish on re-apply (KTD-3), reference use case produces valid registry JSON.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- `RegistryManager` produces a correct, deterministic `registry.json` from valid definitions; preserves runtime fields across re-applies; raises collected errors without touching the registry when definitions are invalid.

**Traces:**

| Document                                                         | Look for                                           | What you'll find                                               |
| ---------------------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------------- |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)            | §2.1 `apply()`                                     | Full SDK apply flow chart                                      |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.2 Feature Registry — FR-REG-001, FR-REG-002     | Deterministic JSON, full rebuild, preserve `last_materialized_at` |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §3.4 KTD-3 (Registry as Full Rebuild)              | System-level decision record                                   |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.4 Registry Manager (BB-04)                      | Full BB-04 specification                                       |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §3.1 Registry JSON schema                          | Registry data format reference                                 |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §5.6 Registry Manager                              | Lookup method signatures and contracts                         |

---

### Task 8d — SDK `FeatureStore` + CLI `apply` (BB-02 partial + BB-01 partial) - (DONE)

|                     |                                                                                                                                   |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-8d/sdk-featurestore-cli-apply`                                                                                         |
| **Goal**            | `FeatureStore` SDK class with constructor + `apply()`, and the `kitefs apply` CLI command — feature groups are now registerable from the command line. |
| **Building blocks** | BB-02 (SDK — constructor + `apply()` only), BB-01 (CLI — `apply` command)                                                         |
| **Depends on**      | Task 8c (RegistryManager)                                                                                                         |

**What to implement:**

**BB-02 (SDK — partial)** — as defined in [Internals §2.2](docs-03-02-internals-and-data.md) and [API Contracts §2.0–§2.1](docs-03-03-api-contracts.md):

- **`FeatureStore.__init__(self, project_root: str | Path | None = None) -> None`**:
  - If `project_root` is provided, use it directly; otherwise walk up from `cwd` to find `kitefs.yaml` (KTD-4 — project root resolution lives in the SDK, not the CLI).
  - If no `kitefs.yaml` found → `ConfigurationError`: "No KiteFS project found. Run `kitefs init` to create one."
  - Load config via BB-10 (`load_config(project_root)`).
  - Instantiate provider via BB-09 (`create_provider(config)`).
  - Create `RegistryManager(provider, config.definitions_path)` (BB-04).
  - Note: Other core module instances (BB-05 through BB-08) are added to the constructor as their respective tasks are implemented (Tasks 11, 12, 15, 18).
- **`FeatureStore.apply(self) -> ApplyResult`**: delegates to `self._registry_manager.apply()`.
- Add `FeatureStore` and `ApplyResult` to `src/kitefs/__init__.py` re-exports.

**BB-01 (CLI — `apply`)** — as defined in [API Contracts §3.2](docs-03-03-api-contracts.md):

- `kitefs apply` command (no arguments or options).
- Instantiate `FeatureStore`, call `fs.apply()`, print success summary + exit 0.
- On `DefinitionError` or `ProviderError` → render error message to stderr + exit 1.

Write tests covering:

- SDK: constructor with valid project, constructor with no `kitefs.yaml` in path raises `ConfigurationError`, `apply()` success returns correct `ApplyResult`, `apply()` with invalid definitions raises `DefinitionError`, end-to-end (init → write definition file → `FeatureStore.apply()` → read `registry.json` → verify contents).
- CLI: `kitefs apply` success (exit 0, summary message), outside KiteFS project (exit 1, error message), invalid definitions (exit 1, errors to stderr), no definition files (exit 1, error message), `kitefs apply --help` shows no options.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- `kitefs init` → write a definition in `definitions/` → `kitefs apply` → `registry.json` contains the registered feature group(s).
- Invalid definitions produce collected, actionable errors listing every issue.

**Traces:**

| Document                                                         | Look for                                 | What you'll find                                   |
| ---------------------------------------------------------------- | ---------------------------------------- | -------------------------------------------------- |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)            | §1.2 `kitefs apply`, §2.1 `apply()`      | Detailed CLI + SDK flow charts                     |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.10 CLI — FR-CLI-003                   | CLI `apply` command requirement                    |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §4.3 Apply Definitions                   | Operational flow diagram                           |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §3.4 KTD-4 (Thin CLI, Fat SDK)           | Project root resolution belongs in the SDK         |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.2 SDK (BB-02)                         | Constructor wiring, `apply()` orchestration        |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §2.0–§2.1 Constructor + `apply()`        | SDK method signatures and return types             |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §3.2 `kitefs apply`                      | CLI contract                                       |

---

### Task 9 — List & Describe Commands - (DONE)

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

- Provider ABC offline method signatures (Task 10a), atomic Parquet writes (Task 10b), Parquet reads + partition listing (Task 10c)
- The validation engine — schema and data validation with three modes (Task 11)
- The offline store manager — partitioning and filtered reads (Task 12)
- SDK ingest method (Task 13a), CLI ingest command (Task 13b)
- Historical retrieval for a single feature group (Task 14)

**Building blocks touched:** BB-09 (Provider — offline methods), BB-05 (Validation Engine), BB-06 (Offline Store Manager), BB-02 (SDK — `ingest()`, `get_historical_features()` partial)

---

### Task 10a — Provider ABC: Offline Store Method Signatures - (DONE)

|                     |                                                                                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Branch**          | `feat/task-10a/provider-offline-abc`                                                                                                                   |
| **Goal**            | The `StorageProvider` ABC declares the three offline store methods — `write_offline`, `read_offline`, `list_partitions` — enforcing the contract for all providers. |
| **Building blocks** | BB-09 (Provider Layer — offline store interface only)                                                                                                  |

**What to implement:**

Extend `StorageProvider` in `src/kitefs/providers/base.py` with three new `@abstractmethod` signatures per [API Contracts §5.5](docs-03-03-api-contracts.md):

- **`write_offline(self, group_name: str, partition_path: str, file_name: str, df: DataFrame) -> None`** — Write a single Parquet file to a specific partition path.
- **`read_offline(self, group_name: str, partition_paths: list[str]) -> DataFrame`** — Read and combine Parquet files from specified partition paths.
- **`list_partitions(self, group_name: str) -> list[str]`** — List available partition paths for a feature group.

The `DataFrame` type annotation requires importing from `pandas`. Both `pandas` and `pyarrow` are introduced as runtime dependencies in this subtask.

Write tests covering: subclass missing any of the three new methods raises `TypeError` on instantiation (extend existing ABC enforcement tests), a complete subclass implementing all methods (including the existing registry methods) can be instantiated.

**Dependencies introduced:**

| Package   | Scope   | Purpose                                              |
| --------- | ------- | ---------------------------------------------------- |
| `pyarrow` | runtime | Parquet read/write (used by LocalProvider in 10b/10c) |
| `pandas`  | runtime | DataFrame interface for method signatures (CON-003)  |

**Demonstrable outcome:**

- `StorageProvider` ABC enforces the three new offline methods alongside the existing registry methods.
- All ABC enforcement tests pass.

**Traces:**

| Document                                                   | Look for                         | What you'll find                                    |
| ---------------------------------------------------------- | -------------------------------- | --------------------------------------------------- |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §2.9 Provider Layer (BB-09)      | Provider ABC offline methods, behavioral rules      |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)  | §5.5 Provider Layer              | Method signatures: write_offline, read_offline, list_partitions |

---

### Task 10b — LocalProvider: `write_offline` (Atomic Parquet Writes) - (DONE)

|                     |                                                                                                                                   |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-10b/provider-offline-write`                                                                                            |
| **Goal**            | `LocalProvider.write_offline()` atomically writes Parquet files into Hive-style partition directories — the offline store write path. |
| **Building blocks** | BB-09 (Provider Layer — `write_offline` implementation)                                                                           |
| **Depends on**      | Task 10a (ABC signatures)                                                                                                         |

**What to implement:**

Implement `write_offline` in `LocalProvider`:

- Compute the full path: `{storage_root}/data/offline_store/{group_name}/{partition_path}/{file_name}`.
- Create the partition directory lazily (`os.makedirs(exist_ok=True)`).
- Use PyArrow to convert the DataFrame to a Parquet table and write it.
- **Atomic write:** write-to-temp-then-rename on local (same pattern as `write_registry`). This prevents partial files from appearing if the write is interrupted.
- The provider stores whatever `partition_path` and `file_name` it receives — it does not derive or validate them. Partition derivation, file naming (`{source}_{timestamp}_{id}.parquet`), and pruning logic are BB-06's responsibility (Task 12).
- Wrap `OSError` and PyArrow exceptions in `ProviderError` with context (operation, path, original exception).

Stub `read_offline` and `list_partitions` with `raise NotImplementedError` to satisfy the ABC until Task 10c implements them.

Write tests covering: write creates correct directory structure (`{storage_root}/data/offline_store/{group_name}/year=YYYY/month=MM/{file_name}`), written Parquet file is readable by PyArrow and contains expected data, append-only (second write with a different file name to the same partition does not overwrite the first — both files coexist), parent directories created lazily, realistic file names passed as arguments (e.g., `ing_20240315T120000_a1b2c3d4.parquet`), `ProviderError` raised on I/O failure.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- Tests prove Parquet files land in the correct Hive-style directory structure and are append-only.
- Atomic write pattern prevents partial files.

**Traces:**

| Document                                                   | Look for                                     | What you'll find                                           |
| ---------------------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.3 Data Ingestion — FR-ING-006, FR-ING-007 | Parquet layout, file naming requirements                   |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.4 Offline Store — FR-OFF-001              | Storage format requirement                                 |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §3.2 Offline Store (Parquet Files)           | Directory structure, type mapping, Hive-style partitioning |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)  | §5.5 Provider Layer — `write_offline`        | Method contract, atomicity guarantee                       |

---

### Task 10c — LocalProvider: `read_offline` + `list_partitions` (Parquet Reads) - (DONE)

|                     |                                                                                                                                                       |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-10c/provider-offline-read`                                                                                                                 |
| **Goal**            | `LocalProvider` can read Parquet files from specified partitions and list available partitions — the offline store read path is complete.              |
| **Building blocks** | BB-09 (Provider Layer — `read_offline` and `list_partitions` implementation)                                                                          |
| **Depends on**      | Task 10b (`write_offline` for producing test data)                                                                                                    |

**What to implement:**

Implement `read_offline` in `LocalProvider`:

- For each partition path in `partition_paths`, read all `.parquet` files under `{storage_root}/data/offline_store/{group_name}/{partition_path}/` using PyArrow.
- Combine all read tables into a single DataFrame.
- Return an **empty DataFrame** if no files exist in any of the specified partitions (not an error).
- Skip non-existent partition paths gracefully (a path with no directory contributes zero rows).
- Wrap PyArrow/OS exceptions in `ProviderError`.

Implement `list_partitions` in `LocalProvider`:

- Enumerate subdirectories under `{storage_root}/data/offline_store/{group_name}/` that follow the `year=YYYY/month=MM` pattern.
- Return a sorted `list[str]` of relative partition paths (e.g., `["year=2024/month=01", "year=2024/month=02"]`).
- Return an empty list if the group directory does not exist or has no partitions.

The layout is identical for both local and S3 (FR-ING-006) — the abstraction ensures this. Note: partition derivation, file naming (`{source}_{timestamp}_{id}.parquet`), and pruning logic are BB-06's responsibility (Task 12), not the provider's. The provider is a primitive I/O layer.

Write tests covering: read returns correct data from specified partition paths, read from multiple partitions combines data correctly, empty partition read returns empty DataFrame, non-existent partition path returns empty DataFrame (not an error), `list_partitions` returns available paths after writes, `list_partitions` returns empty list for non-existent group, `list_partitions` results are sorted, end-to-end roundtrip (write via `write_offline` → `list_partitions` → `read_offline` → verify data).

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- Full write → list → read roundtrip works.
- Empty reads are graceful (empty DataFrame, not an error).
- This completes the offline store I/O — `LocalProvider` has full `write_offline`, `read_offline`, and `list_partitions`.

**Traces:**

| Document                                                   | Look for                                                  | What you'll find                                                |
| ---------------------------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.3 Data Ingestion — FR-ING-006                          | Hive-style layout requirement                                   |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.4 Offline Store — FR-OFF-001                           | Storage format requirement                                      |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §2.9 Provider Layer (BB-09)                               | Provider ABC offline methods                                    |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §3.2 Offline Store (Parquet Files)                        | Directory structure, Hive-style partitioning                    |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)  | §5.5 Provider Layer — `read_offline`, `list_partitions`   | Method contracts, empty-result behavior                         |

---

### Task 11 — Validation Engine (BB-05) - (DONE)

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

**Dependencies introduced:** None new (operates on Pandas DataFrames already available from Task 10a).

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

### Task 12 — Offline Store Manager (BB-06) - (DONE)

|                     |                                                                                                                                     |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-12/offline-store-manager`                                                                                                |
| **Goal**            | The offline store manager handles partitioning logic and filtered reads — the orchestration layer between the SDK and the provider. |
| **Building blocks** | BB-06 (Offline Store Manager)                                                                                                       |

**What to implement:**

Implement BB-06 as defined in [Internals §2.6](docs-03-02-internals-and-data.md):

- **Partition column derivation:** Extract `year` and `month` from the column identified by `event_timestamp_col` for Hive-style partitioning.
- **Write orchestration:** `write(group_name, df, event_timestamp_col, source_prefix)` — add partition columns derived from `event_timestamp_col`, delegate to provider's `write_offline()` with source prefix.
- **Read orchestration with time-filter:** `read(group_name, event_timestamp_col, time_filter, upper_bound)`
  - Apply `time_filter` operators (`gt`/`gte`/`lt`/`lte`) against `event_timestamp_col` for partition-level pruning (month-level) and row-level filtering.
  - BB-02 extracts `time_filter = where.get("event_timestamp") if where else None` before calling BB-06. BB-06 receives only the flat operator→value dict — it does not understand the user-facing `where` format or perform alias resolution.
  - Delegate partition-pruned read to provider, then apply row-level filter on `event_timestamp_col`.
- **Read for materialization:** Read all data for a group (no filtering) — used by `materialize()` later.

**Note:** BB-06 does not depend on the definition module (BB-03) or registry (BB-04). The caller (BB-02) passes `definition.event_timestamp.name` as `event_timestamp_col`. This follows the same pattern as BB-08's `left_timestamp`/`right_timestamp` parameters (see [API Contracts §5.4](docs-03-03-api-contracts.md)).

Write tests covering: partition columns derived correctly, filtered reads return correct subsets, partition pruning reduces I/O, full-group read returns everything.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- Data partitioned correctly by year/month on write.
- Filtered reads with time-range `time_filter` return expected subsets.

**Traces:**

| Document                                                   | Look for                                     | What you'll find                   |
| ---------------------------------------------------------- | -------------------------------------------- | ---------------------------------- |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.3 Data Ingestion — FR-ING-004, FR-ING-006 | Append-only, Hive-style layout     |
| [Requirements (docs-02)](docs-02-project-requirements.md)  | §1.4 Offline Store — FR-OFF-007              | Unified where format               |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §2.6 Offline Store Manager (BB-06)           | Partitioning logic, KTD-10, KTD-11 |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md) | §3.3 Offline Store Layout                    | Directory structure reference      |

---

### Task 13a — SDK `FeatureStore.ingest()` (BB-02 partial) - (DONE)

|                     |                                                                                                                                     |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-13a/sdk-ingest`                                                                                                          |
| **Goal**            | `FeatureStore.ingest()` accepts a DataFrame or file path, validates, and writes to the offline store — the first SDK data write path. |
| **Building blocks** | BB-02 (SDK — `ingest()` only)                                                                                                       |
| **Depends on**      | Task 11 (Validation Engine), Task 12 (Offline Store Manager)                                                                        |

**What to implement:**

**`IngestResult`** — frozen dataclass (public return type, per [API Contracts §2.2](docs-03-03-api-contracts.md)):

- `rows_written: int` — number of rows written after validation filtering.
- `partitions_affected: tuple[str, ...]` — partition paths that received data.
- Add to `src/kitefs/__init__.py` re-exports.

**`FeatureStore.ingest()` method** — as defined in [API Contracts §2.2](docs-03-03-api-contracts.md):

- Wire `OfflineStoreManager` into `FeatureStore.__init__` as `self._offline_store_manager = OfflineStoreManager(provider)` — first time BB-06 is connected to the SDK (following the pattern from Task 8d where `RegistryManager` was wired).
- Look up feature group definition via BB-04 (`self._registry_manager.get_group(feature_group_name)`). Not found → `FeatureGroupNotFoundError`.
- Resolve input to DataFrame:
  - `DataFrame` → use directly.
  - `str` ending in `.csv` → load via `pd.read_csv`.
  - `str` ending in `.parquet` → load via `pd.read_parquet`.
  - Other → raise `IngestionError` listing supported input formats.
- Run schema validation via BB-05 (`validate_schema`) — always runs regardless of mode. Drops extra columns not in the definition (FR-ING-002). Raises `SchemaValidationError` on missing columns or null structural columns.
- Run data validation via BB-05 (`validate_data`) per `definition.ingestion_validation` mode.
- If FILTER mode and all rows filtered out → return `IngestResult(rows_written=0, partitions_affected=())`.
- Write validated data via BB-06 (`self._offline_store_manager.write()`) with `source_prefix="ing"`. Pass `definition.event_timestamp.name` as `event_timestamp_col`.
- Map `WriteResult` (BB-06 internal) to `IngestResult` (public return type) and return.

Write tests covering: DataFrame ingestion success, CSV file ingestion, Parquet file ingestion, unsupported input type raises `IngestionError`, unsupported file extension raises `IngestionError`, feature group not found raises `FeatureGroupNotFoundError`, missing columns raise `SchemaValidationError`, null entity key raises `SchemaValidationError`, null event timestamp raises `SchemaValidationError`, extra columns silently dropped, ERROR mode with invalid data raises `DataValidationError` (no data written), FILTER mode excludes failing rows, FILTER mode with all rows filtered returns `IngestResult(rows_written=0, ...)`, NONE mode skips data validation (schema still runs), append-only behavior (two ingests to same group both persist), reference use case `listing_features` ingestion produces correct partition paths.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- `FeatureStore.ingest("listing_features", df)` writes validated Parquet files to the offline store.
- All three validation modes behave correctly (ERROR rejects, FILTER excludes, NONE skips Phase 2).
- `IngestResult` is importable from `kitefs`.

**Traces:**

| Document                                                         | Look for                              | What you'll find                                             |
| ---------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------ |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)            | §2.2 `ingest()`                       | Detailed SDK flow chart                                      |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.3 Data Ingestion — FR-ING-001–007  | Requirement-level acceptance criteria                        |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §4.4 Ingest Data                      | Operational flow diagram                                     |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.2 SDK (BB-02)                      | Constructor wiring, `ingest()` orchestration                 |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.5 Validation Engine (BB-05)        | Two-phase validation, extra column dropping                  |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.6 Offline Store Manager (BB-06)    | Write orchestration contract                                 |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §2.2 `ingest()`                       | SDK method signature, parameters, `IngestResult` return type |

---

### Task 13b — CLI `kitefs ingest` (BB-01 partial) - (DONE)

|                     |                                                                                                                               |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-13b/cli-ingest`                                                                                                    |
| **Goal**            | `kitefs ingest <feature_group_name> <file_path>` is a runnable command — the first data ingestion path from the command line. |
| **Building blocks** | BB-01 (CLI — `ingest` command)                                                                                                |
| **Depends on**      | Task 13a (SDK `ingest()`)                                                                                                     |

**What to implement:**

**CLI `ingest` command** — as defined in [API Contracts §3.3](docs-03-03-api-contracts.md):

- `kitefs ingest <feature_group_name> <file_path>` — two positional arguments.
- Instantiate `FeatureStore()`, call `fs.ingest(feature_group_name, file_path)`.
- On success (exit 0): print ingestion summary — rows written and partitions affected.
- On error (exit 1): catch `KiteFSError`, render message to stderr, exit 1. No tracebacks.
- Follows Thin CLI, Fat SDK pattern (KTD-4) — no business logic in the command.
- Note: DataFrame ingestion is SDK-only, not available via CLI (FR-ING-001).

Write tests covering: `kitefs ingest <name> <csv>` success (exit 0, summary printed), outside KiteFS project (exit 1, error to stderr), unknown feature group (exit 1, error message), nonexistent file path (exit 1, error message), schema validation failure (exit 1, errors to stderr), `kitefs ingest --help` shows arguments and usage.

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- `kitefs init` → write definition → `kitefs apply` → `kitefs ingest listing_features data.csv` → Parquet files in `feature_store/data/offline_store/listing_features/year=.../month=.../`.
- Errors produce clear, actionable messages to stderr with exit code 1.

**Traces:**

| Document                                                         | Look for                 | What you'll find                            |
| ---------------------------------------------------------------- | ------------------------ | ------------------------------------------- |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)            | §1.4 `kitefs ingest`     | Detailed CLI flow chart                     |
| [Requirements (docs-02)](docs-02-project-requirements.md)        | §1.10 CLI — FR-CLI-004   | CLI ingest command requirement              |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.1 CLI (BB-01)         | Thin CLI behavioral rules, error scenarios  |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §3.3 `kitefs ingest`     | CLI contract: arguments, exit codes, output |

---

### Task pre-14 — Retrieval Alignment (doc fixes + validation seam)

|                     |                                                                                                                                              |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-pre-14/retrieval-alignment`                                                                                                       |
| **Goal**            | Align docs, code, and design decisions so Task 14 can be implemented without ambiguity or contract conflicts.                                |
| **Building blocks** | BB-05 (Validation Engine — minor), BB-04 (Registry Manager — doc-only), BB-02 (SDK — doc-only)                                               |
| **Depends on**      | Task 13b                                                                                                                                     |

**What to implement:**

This task resolves 8 identified discrepancies between the design docs, existing code, and the Task 14 spec. It produces doc fixes, one targeted code change, and explicit design decisions that Task 14 will rely on. Organized into three categories:

**Category A — Doc fixes (update existing documents):**

1. **Fix Task 14 exception wording (this document, Task 14 §Parameter validation).** The current bullet lumps "group exists in registry" into "Invalid params → `RetrievalError`". The API contract ([API Contracts §2.3 Raises](docs-03-03-api-contracts.md)) says unknown `from_` raises `FeatureGroupNotFoundError`, not `RetrievalError`. The existing `RegistryManager.get_group()` already follows this contract. Fix: rewrite the parameter validation bullet to separate the two error surfaces — `FeatureGroupNotFoundError` for unknown groups, `RetrievalError` for invalid `select`/`where`.

2. **Fix SDK error scenarios table ([Internals §2.2 Error Scenarios](docs-03-02-internals-and-data.md)).** The row "Feature group not found for any operation" says `RegistryError propagated`. It should say `FeatureGroupNotFoundError propagated` to match the API contract and the existing `get_group()` implementation.

3. **Fix architecture sequence diagram return value ([Architecture §4.5 Get Historical Features](docs-03-01-architecture-overview.md)).** The line `BB04-->>BB02: Validated params + definitions` implies `validate_query_params()` returns definitions. The formal contract signature is `-> None` (validation-only, raises on failure). Fix: change to `BB04-->>BB02: Validation passed`. BB-02 calls `get_group()` separately to obtain definitions.

4. **Fix architecture select-narrowing note ([Architecture §4.5 Get Historical Features](docs-03-01-architecture-overview.md)).** The sequence diagram note says "keep entity_key, event_timestamp, join keys + selected features". The join-key retention applies only to the join path (Task 16). For the no-join path, the output is: entity key + event timestamp + selected features — join keys are not force-included unless explicitly selected or covered by `"*"`. Fix: make the diagram note conditional by path, or split it into two notes. The prose in the same section already handles this correctly.

**Category B — Code change (validation engine):**

5. **Add `validate_data_selected()` to `src/kitefs/validation.py`.** The current `validate_data()` iterates all features from the full `FeatureGroup` definition and directly indexes each column in the DataFrame. When the caller passes a select-narrowed DataFrame (as Task 14 requires), any unselected feature column causes a `KeyError`. The contract says validation runs on selected features only ([API Contracts §2.3 Behavioral notes](docs-03-03-api-contracts.md), [Flow Charts §2.3](docs-00-02-flow-charts.md), [Architecture §4.5](docs-03-01-architecture-overview.md)).

   Implement a new public function:
   ```python
   def validate_data_selected(
       definition: FeatureGroup,
       df: DataFrame,
       mode: ValidationMode,
       selected_features: list[str],
   ) -> tuple[ValidationReport, DataFrame]:
   ```
   This function constructs a derived `FeatureGroup` with only the features whose names are in `selected_features`, then delegates to the existing `validate_data()`. The ingestion-path code remains untouched. Add `validate_data_selected` to the module's public surface and to `src/kitefs/__init__.py` re-exports.

**Category C — Design decisions (codified in Task 14 amendments):**

These decisions do not require code changes in this task. They are recorded here and applied as amendments to Task 14's description in this document, so Task 14 can implement them without ambiguity.

6. **Empty-result DataFrame shape.** When BB-06 returns an empty DataFrame (zero columns, zero rows), BB-02 must synthesize an empty DataFrame with the correct output columns (entity key + event timestamp + selected features) before returning. This satisfies the structural-columns rule ([API Contracts §6.1](docs-03-03-api-contracts.md)). The empty result is not an error ([API Contracts §2.3 Behavioral notes](docs-03-03-api-contracts.md)). No change to BB-06 — the output-shape concern lives in BB-02.

7. **event_timestamp logical alias test requirement.** Task 14's test list must include: (a) a positive test using a group whose physical timestamp column is `ts` (not `event_timestamp`) with `where={"event_timestamp": {"gte": ...}}` to prove alias resolution works; (b) a negative test proving `where={"ts": ...}` is rejected with `RetrievalError`. The helpers already provide `EventTimestamp(name="ts", ...)` fixtures.

8. **Non-empty `join` rejection in Task 14.** Task 14 must explicitly reject any non-empty `join` parameter with `JoinError`: "Join support will be available in a future release. Remove the `join` parameter for single-group retrieval." This is the correct transitional behavior per [API Contracts §2.3 Raises](docs-03-03-api-contracts.md) which maps join issues to `JoinError`. Add a test for this.

9. **`where` value-type strictness.** `validate_query_params()` (implemented in Task 14) must require `where` values for `event_timestamp` to be `datetime` instances (or `pd.Timestamp`). Strings, ints, and other types are rejected with `RetrievalError`. The internals doc says "value types must match the field's declared type" ([Internals §2.4](docs-03-02-internals-and-data.md)). `event_timestamp` is `DATETIME`, so only datetime-like values are accepted. BB-06's existing `pd.Timestamp(dt)` coercion serves as a safety net, not an invitation for arbitrary types.

10. **No-join select does not force-include join keys.** For the no-join path, a list `select` includes only entity key + event timestamp + the explicitly named features. Join key fields are not auto-included unless they appear in the `select` list or `select="*"`. This follows [Requirements FR-OFF-002](docs-02-project-requirements.md) and the architecture prose ([Architecture §4.5](docs-03-01-architecture-overview.md)).

Write tests covering:

- `validate_data_selected()` with a subset of features: an invalid unselected feature does not block retrieval of valid selected features.
- `validate_data_selected()` with all features selected behaves identically to `validate_data()`.
- `validate_data_selected()` in all three modes (ERROR, FILTER, NONE).
- `validate_data_selected()` with empty `selected_features` list (only structural columns in DataFrame).

**Dependencies introduced:** None new.

**Demonstrable outcome:**

- Doc inconsistencies across [Architecture](docs-03-01-architecture-overview.md), [Internals](docs-03-02-internals-and-data.md), and [Implementation Guide](docs-04-implementation-guide.md) are resolved.
- `validate_data_selected()` is importable from `kitefs` and passes all tests.
- Task 14's description is amended with explicit design decisions (empty-result shape, alias test requirement, join rejection, value-type strictness, join-key exclusion).
- `just clean-build` passes.

**Traces:**

| Document                                                         | Look for                                            | What you'll find                                           |
| ---------------------------------------------------------------- | --------------------------------------------------- | ---------------------------------------------------------- |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §2.3 `get_historical_features()` — Raises           | Exception mapping: which error for which failure           |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §2.3 Behavioral notes                               | "only selected features are validated", empty-result rule  |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §5.6 Registry Manager — `validate_query_params()`   | Validation-only signature (`-> None`)                      |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §6.1 Structural Columns Rule                        | Entity key + event timestamp always in results             |
| [API Contracts (docs-03-03)](docs-03-03-api-contracts.md)        | §6.6 Event Timestamp Column Name Resolution         | Logical alias rule for `where`                             |
| [Architecture (docs-03-01)](docs-03-01-architecture-overview.md) | §4.5 Get Historical Features                        | Sequence diagram to fix (return value, select note)        |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.2 SDK — Error Scenarios                          | `RegistryError` → `FeatureGroupNotFoundError` fix          |
| [Internals (docs-03-02)](docs-03-02-internals-and-data.md)       | §2.4 Registry Manager — Interface Contract          | "value types must match the field's declared type"         |
| [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)            | §2.3 `get_historical_features()`                    | "selected features only" validation                        |

---

### Task 14 — Historical Retrieval (single group, no join)

|                     |                                                                                                                            |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Branch**          | `feat/task-14/historical-retrieval-single`                                                                                 |
| **Goal**            | `get_historical_features()` retrieves data from a single feature group — training dataset generation for the no-join case. |
| **Building blocks** | BB-02 (SDK — `get_historical_features()`, non-join path)                                                                   |

**What to implement:**

Implement the non-join path of `get_historical_features()` as defined in [API Contracts §2.3](docs-03-03-api-contracts.md):

- **Parameter validation:** Group exists in registry, `select` references valid features (or `"*"`), `where` uses valid field/operator (MVP: `event_timestamp` logical alias only — resolved to `definition.event_timestamp.name` — with `gt`/`gte`/`lt`/`lte` operators). Invalid params → `RetrievalError`.
- **Read:** Delegate to BB-06 with partition pruning. Pass `definition.event_timestamp.name` as `event_timestamp_col` to BB-06's `read()`. Extract `time_filter = where.get("event_timestamp") if where else None` and pass it as `time_filter` to BB-06 — BB-06 receives the flat operator→value dict, not the full user-facing `where`.
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
  - Joined group's event timestamp column is always prefixed with `{joined_group_name}_` — structural role-based rule, not name-based conflict detection (see API Contracts §6.6).
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

- **Latest-per-entity extraction:** `materialize(group_name, df, event_timestamp_col, entity_key_col)` — group by `entity_key_col`, select the row with maximum `event_timestamp_col`. The caller (BB-02) passes `definition.event_timestamp.name` and `definition.entity_key.name` as these parameters.
- **Write to online store:** Via provider's `write_online()` — full overwrite per group.

**SDK `materialize()` method** — as defined in [API Contracts §2.5](docs-03-03-api-contracts.md):

- If `feature_group_name` provided: materialize that group only. Validate it's `OFFLINE_AND_ONLINE` → `MaterializationError` if `OFFLINE` only (FR-MAT-002).
- If `None`: materialize all `OFFLINE_AND_ONLINE` groups. A failure in one group does not prevent others (FR-MAT-001).
- Read offline data via BB-06 (passing `definition.event_timestamp.name` as `event_timestamp_col`), extract latest-per-entity via BB-07 (passing both `event_timestamp_col` and `entity_key_col`), write online via BB-07.
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
  Task 7  → Task 8a ──┐
  (provider) (discovery) ├──→ Task 8c → Task 8d → Task 9
             Task 8b ──┘   (registry) (SDK+CLI) (list/describe)
             (validation)

Phase 3 — Ingest & Query
  Task 10a → Task 10b → Task 10c → Task 11 → Task 12 → Task 13 → Task pre-14 → Task 14
  (ABC)     (write)    (read)     (valid.)  (offline)  (ingest)  (alignment)   (retrieval)

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
| 10a   | `pyarrow`, `pandas`              | —                           |
| 10b–10c | —                              | —                           |
| 11–13 | —                                | —                           |
| pre-14 | —                               | —                           |
| 14–19 | —                                | —                           |
| 20    | `boto3` (optional `[aws]` extra) | —                           |
| 21–23 | —                                | —                           |

## Appendix C — Requirement Traceability

> _Maps each functional requirement to the task(s) that implement it._

| Requirement Category         | FR IDs                                                       | Task(s)         |
| ---------------------------- | ------------------------------------------------------------ | --------------- |
| Feature Group Definition     | FR-DEF-001 through FR-DEF-007                                | 3               |
| Feature Registry (discovery) | FR-REG-003                                                   | 8a              |
| Feature Registry (validation)| FR-REG-004, FR-REG-007                                       | 8b              |
| Feature Registry (apply)     | FR-REG-001, FR-REG-002                                       | 8c              |
| Feature Registry (inspect)   | FR-REG-005, FR-REG-006                                       | 9               |
| Feature Registry (sync/pull) | FR-REG-008, FR-REG-009                                       | 21              |
| Data Ingestion               | FR-ING-001 through FR-ING-007                                | 10a–10c, 12, 13 |
| Offline Store & Historical   | FR-OFF-001, FR-OFF-002, FR-OFF-006, FR-OFF-007               | 10a–10c, 12, 14 |
| Offline Store (joins)        | FR-OFF-003 through FR-OFF-005, FR-OFF-008 through FR-OFF-010 | 15, 16          |
| Online Store & Serving       | FR-ONL-001, FR-ONL-002                                       | 17, 19          |
| Materialization              | FR-MAT-001 through FR-MAT-005                                | 18              |
| Validation Engine            | FR-VAL-001 through FR-VAL-009                                | 11              |
| Provider Abstraction         | FR-PROV-001, FR-PROV-003, FR-PROV-005                        | 7, 10a–10c, 17  |
| Provider Abstraction (AWS)   | FR-PROV-002, FR-PROV-004                                     | 20              |
| Configuration                | FR-CFG-001 through FR-CFG-006                                | 4               |
| CLI                          | FR-CLI-001, FR-CLI-002                                       | 5               |
| CLI                          | FR-CLI-003                                                   | 8d              |
| CLI                          | FR-CLI-004                                                   | 13              |
| CLI                          | FR-CLI-005, FR-CLI-006, FR-CLI-012                           | 9               |
| CLI                          | FR-CLI-007                                                   | 18              |
| CLI                          | FR-CLI-008                                                   | 21              |
| CLI                          | FR-CLI-009                                                   | 22              |
| CLI                          | FR-CLI-010                                                   | 23              |
| CLI (cross-cutting)          | FR-CLI-011                                                   | 5, 8d, 9, 13, 18 |
| Mock Data Generation         | FR-MOCK-001 through FR-MOCK-003                              | 22              |
| Smart Sampling               | FR-SAM-001 through FR-SAM-003                                | 23              |
