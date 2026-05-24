# Implementation Plan

## Purpose

This file defines implementation sequencing for the KiteFS feature store library. It owns task planning and delivery boundaries only.

## Owns

- Phases.
- Tasks.
- Branch names.
- Task status: done or not started.
- Task scope and boundaries.
- Dependencies between tasks.
- What each task delivers.

## Does Not Own

- Project context. See [00-project-context.md](00-project-context.md).
- Reference use case. See [01-reference-use-case.md](01-reference-use-case.md).
- Requirements definitions. See [02-product-requirements.md](02-product-requirements.md).
- Behavior specifications. See [03-system-behavior.md](03-system-behavior.md).
- Architectural design. See [04-architecture.md](04-architecture.md).
- Data and storage contracts. See [05-data-and-storage-contracts.md](05-data-and-storage-contracts.md).
- API signatures. See [06-api-and-cli-contracts.md](06-api-and-cli-contracts.md).

## Conventions

- **Task ID:** `T-NNN` — monotonically increasing, zero-padded.
- **Phase ID:** `P-N` — sequential.
- **Branch naming:** `feat/T-NNN-short-slug`.
- **Status:** `not started` or `done`.
- **Development flow:** Vertical. Each phase delivers a demoable outcome where possible.
- **Task scope:** Single-purpose. Small, self-contained changes.

---

## P-1 — Project Skeleton and Foundations

**Goal:** A buildable, testable Python package with dev tooling, the shared error model, and shared enums in place.

### T-001 — Local Package Skeleton

**Status:** not started
**Branch:** `feat/T-001-package-skeleton`
**Refined status:** yes

**Goal:** A clean-venv `uv pip install -e .` produces an importable `kitefs` package with one empty sub-package per BB-XX, a working `kitefs --help` console script (placeholder Click group, no subcommands), and `just` recipes that pass on the empty skeleton — all with base dependencies only, no AWS extras.

**Scope:**

_In scope:_

- `pyproject.toml`: keep existing base dependencies (`click`, `pandas`, `pyarrow`, `pyyaml`) and dev group (`pyright`, `pytest`, `pytest-bdd`, `ruff`); confirm `requires-python = ">=3.12"` and `uv_build` backend; add `[project.scripts] kitefs = "kitefs.cli:main"`.
- `src/kitefs/__init__.py`: replace placeholder `hello()` with module body containing `__version__ = "0.1.0"` only. No re-exports yet.
- `src/kitefs/cli/__init__.py`: define `main` as a Click group with no subcommands so `kitefs --help` prints Click's auto-generated usage. No error boundary, no subcommand wiring.
- `src/kitefs/py.typed`: empty marker file present.
- Confirm every BB sub-package directory exists per [Building Block to Source Path Mapping](04-architecture.md#building-block-to-source-path-mapping) with an empty `__init__.py`: `cli/`, `sdk/`, `definitions/`, `registry/`, `validation/`, `offline_store/`, `online_store/`, `join_engine/`, `providers/` (with `local/` and `aws/` subfolders; `base.py` deferred to T-014), `config/`, `errors/`, plus the empty `enums.py` file. No symbols defined.
- Verify `just lint`, `just format-check`, `just type-check`, `just test`, `just build`, and `just clean-build` pass on the empty skeleton.

_Out of scope:_

- AWS optional extras and the `[aws]` extra group (deferred to T-041).
- Real CLI subcommands and the CLI error boundary (T-003 onward).
- Exception classes and shared enum members (T-002).
- Provider ABCs and `providers/base.py` body (T-014).
- Public re-exports of definition types, `FeatureStore`, return-type dataclasses (T-022).
- Test scaffolding beyond `tests/` directories that already exist.

**Acceptance Criteria:**

1. In a clean Python 3.12+ venv, `uv pip install -e .` from the repo root completes successfully and exposes `kitefs` as an installed distribution.
2. `kitefs --help` prints Click's auto-generated usage block to stdout and exits with code `0`.
3. `python -c "import kitefs; print(kitefs.__version__)"` succeeds and prints `0.1.0`. No `boto3` import is triggered (no `boto3` import anywhere under `src/kitefs/` outside `providers/aws/`, which is empty here).
4. Every BB sub-package listed in the source-path-mapping table exists under `src/kitefs/` with an `__init__.py` (empty body acceptable). `enums.py` and `py.typed` exist at the package root.
5. `just clean-build` (which chains `clear → check → test → build`) exits `0` on the unmodified skeleton.
6. The base install does not declare or pull in any AWS-specific runtime dependency; `pyproject.toml` contains no `[aws]` extras group.

**Doc References:**

- [CON-001 — Python 3.12+](02-product-requirements.md#con-001--python-312) — declared in package metadata.
- [CON-002 — Pip-Installable Library](02-product-requirements.md#con-002--pip-installable-library) — single pip-installable package, no companion service.
- [CON-005 — No Server or Daemon](02-product-requirements.md#con-005--no-server-or-daemon) — only SDK calls or CLI invocations exist.
- [NFR-MAINT-001 — Modular Architecture](02-product-requirements.md#nfr-maint-001--modular-architecture) — separate concerns mapped to sub-packages.
- [Packaging Model](04-architecture.md#packaging-model) — `src/kitefs/` layout, `kitefs` console script, AWS extra deferred.
- [Building Block to Source Path Mapping](04-architecture.md#building-block-to-source-path-mapping) — exact directory mapping per BB.
- [FR-CLI-001 — Installed CLI Entry Point](02-product-requirements.md#fr-cli-001--installed-cli-entry-point) — partial coverage; full FR-CLI-001 conformance lands in T-003.

**Flags, Open Questions, Assumptions, Recommendations:**

- **Flag — Partial FR-CLI-001 coverage:** the placeholder CLI satisfies "command available after install" and "`--help` works" but does NOT yet enforce the full FR-CLI-001 contract (no-subcommand → non-zero exit with help, plain-text error rendering). T-003 owns the full contract. _Recommendation:_ accept Click's default invoke-without-subcommand behavior (which already exits non-zero with usage); do not add custom no-subcommand handling here.
- **Assumption:** `pyproject.toml` and `justfile` are already partially set up in the repo and only need the `[project.scripts]` addition plus the `kitefs.cli:main` target. Validated against the current files.
- **Assumption:** `src/kitefs/__init__.py` carries only `__version__` for now; full re-exports are scheduled by T-002 (errors/enums) and T-022 (definition types and `FeatureStore`).
- **Open Question — `__version__` source:** hard-coded `"0.1.0"` vs. dynamic `importlib.metadata.version("kitefs")`. _Recommendation:_ hard-code for the skeleton — dynamic resolution adds complexity not required here and is easy to flip later.

**Test Strategy:**

- _Unit tests:_ `tests/unit/test_package_metadata.py` — assert `kitefs.__version__` is a string equal to the value in `pyproject.toml`; assert importing `kitefs` does not raise.
- _Integration tests:_ `tests/integration/test_cli_entry.py` — using `click.testing.CliRunner`, invoke `kitefs --help` and assert exit code `0` and non-empty `result.output`. No subprocess test required; `pip install -e .` and the `kitefs` console script are verified manually as part of `just clean-build`.

### T-002 — Error Model and Shared Enums

**Status:** not started
**Branch:** `feat/T-002-errors-and-enums`
**Refined status:** yes

**Goal:** The full `KiteFSError` exception hierarchy from [docs/06 § Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy) and the three shared enums (`FeatureType`, `StorageTarget`, `ValidationMode`) are defined as importable symbols from the top-level `kitefs` package, with no behavior logic beyond declaration and a small message-formatting helper.

**Scope:**

_In scope:_

- `src/kitefs/errors/__init__.py`: define `KiteFSError` as the base class and every concrete exception class listed in [docs/06 § Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy):
  - `ConfigurationError`, `DefinitionError`, `DefinitionDiscoveryError`, `DefinitionValidationError`
  - `RegistryError` → `RegistryReadError`, `RegistryWriteError`
  - `FeatureGroupNotFoundError`, `FeatureGroupNotMaterializableError`
  - `ValidationError` (with a `report` attribute typed via forward reference; see Open Questions)
  - `IngestionShapeError`
  - `RetrievalParameterError`, `JoinError`
  - `OfflineStoreError` → `OfflineStoreReadError`, `OfflineStoreWriteError`
  - `OnlineStoreError` → `OnlineStoreReadError`, `OnlineStoreWriteError`
  - `ProviderError`
- One small helper for actionable error messages (e.g. `format_actionable(*, setting=None, group=None, field=None, problem, next_step) -> str` returning a single-line plain string). Used optionally by raisers; not enforced via subclass logic.
- `src/kitefs/enums.py`: define `FeatureType` (`STRING`, `INTEGER`, `FLOAT`, `DATETIME`), `StorageTarget` (`OFFLINE`, `OFFLINE_AND_ONLINE`), and `ValidationMode` (`ERROR`, `FILTER`, `NONE`) as `enum.Enum` subclasses with string values matching the names.
- `src/kitefs/__init__.py`: re-export every public exception class, `KiteFSError`, and the three enums so `from kitefs import KiteFSError, ConfigurationError, FeatureType, ...` works. Definition types and `FeatureStore` re-exports remain deferred to T-022.

_Out of scope:_

- `ValidationReport` / `ValidationFailure` dataclasses — owned by T-011 (validation engine). T-002 references `ValidationReport` only via a `TYPE_CHECKING` forward reference annotation on `ValidationError.report`.
- CLI error boundary that catches and renders these (T-003).
- Any raise-site code that uses these exceptions (lands in tasks that introduce each behavior).
- Provider-specific cause chaining (`__cause__`) wiring — implemented as raisers are added.

**Acceptance Criteria:**

1. `KiteFSError` exists in `kitefs.errors` and is a subclass of `Exception`.
2. Every exception class enumerated in [docs/06 § Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy) exists with the documented inheritance: `RegistryReadError` and `RegistryWriteError` inherit from `RegistryError`; `OfflineStoreReadError` / `OfflineStoreWriteError` inherit from `OfflineStoreError`; `OnlineStoreReadError` / `OnlineStoreWriteError` inherit from `OnlineStoreError`; all bases inherit from `KiteFSError`.
3. Every exception class is reachable via `from kitefs import <ClassName>` and via `from kitefs.errors import <ClassName>`.
4. `ValidationError` defines a `report` attribute (typed annotation referencing `ValidationReport` via forward reference under `TYPE_CHECKING`); constructing `ValidationError("msg", report=<sentinel>)` stores the sentinel on the instance and returns it via `error.report`.
5. `FeatureType`, `StorageTarget`, and `ValidationMode` are `enum.Enum` subclasses defined in `kitefs.enums` with the exact members listed in [docs/06 § Public Package Surface › Enums](06-api-and-cli-contracts.md#enums); each is reachable via `from kitefs import <EnumName>`.
6. The actionable-message helper is a pure function with no I/O and is importable from `kitefs.errors`. Calling it with all kwargs returns a single-line `str`.
7. Importing `kitefs.errors` triggers no provider-specific imports (no `boto3`, `sqlite3`, `pyarrow`, `pandas`).

**Doc References:**

- [Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy) — authoritative class list and inheritance diagram.
- [Selection Rules](06-api-and-cli-contracts.md#selection-rules) — taxonomy intent (configuration vs. operation, shape vs. validation, store-error provider-cause rule).
- [`ValidationError` Attribute](06-api-and-cli-contracts.md#validationerror-attribute) — `report: ValidationReport` contract.
- [AP-7 — Explicit Failure with Actionable Errors](04-architecture.md#architectural-design-principles) — single shared error taxonomy across SDK and CLI.
- [Error Model](04-architecture.md#error-model) — actionable-error standard.
- [02 § Conventions](02-product-requirements.md#conventions) — definition of "actionable error".
- [FR-DEF-002 — Field Type Definitions](02-product-requirements.md#fr-def-002--field-type-definitions) — supported `FeatureType` values.
- [FR-DEF-003 — Storage Target](02-product-requirements.md#fr-def-003--storage-target) — `StorageTarget` values.
- [FR-DEF-005 — Per-Operation Validation Modes](02-product-requirements.md#fr-def-005--per-operation-validation-modes) — `ValidationMode` values.
- [docs/06 § Public Package Surface › Enums](06-api-and-cli-contracts.md#enums) — exact member names.

**Flags, Open Questions, Assumptions, Recommendations:**

- **Flag — `ValidationError.report` typing cycle:** `ValidationReport` is documented in [docs/06 § Return Types](06-api-and-cli-contracts.md#return-types) and conceptually lives in `kitefs.sdk.results` (T-011). Defining the concrete dataclass in T-002 would pull SDK return-type concerns into the foundation layer; not defining it leaves `ValidationError.report` typed loosely. _Recommendation:_ annotate via `if TYPE_CHECKING: from kitefs.sdk.results import ValidationReport` and use a string forward reference (`report: "ValidationReport"`); accept `report` as a constructor argument with no runtime isinstance check. T-011 owns the dataclass itself.
- **Open Question — Enum value style:** `enum.Enum` with string values matching member names (e.g. `FeatureType.STRING.value == "STRING"`) is the simplest serialization fit for the registry JSON contract. _Recommendation:_ use `enum.Enum` (not `IntEnum` or `StrEnum`) with explicit string values; verify against [05 § Feature Group Entry Schema](05-data-and-storage-contracts.md) when T-021 lands and adjust if mismatched.
- **Open Question — Helper signature:** docs do not prescribe a specific helper API. _Recommendation:_ keep the helper internal to `kitefs.errors` for now (`format_actionable(*, setting=None, group=None, field=None, problem, next_step) -> str`); raise-site callers import it by name. Refactor freely as the first real raiser arrives in T-003 / T-012.
- **Assumption:** No exception class needs custom `__init__` beyond `Exception`'s default; `ValidationError` adds `report`, every other class is `pass`-bodied. Validated against the docs — no other attributes are documented.

**Test Strategy:**

- _Unit tests:_ `tests/unit/errors/test_hierarchy.py` — parametrized over every concrete exception class, assert `issubclass(cls, KiteFSError)` and the documented intermediate base (e.g. `OfflineStoreReadError → OfflineStoreError → KiteFSError`); assert each is reachable via `from kitefs import <name>` and `from kitefs.errors import <name>`.
- _Unit tests:_ `tests/unit/errors/test_validation_error.py` — construct `ValidationError("msg", report=object())`, assert `error.report is sentinel`, `str(error) == "msg"`.
- _Unit tests:_ `tests/unit/errors/test_actionable_message.py` — given representative kwargs, assert the helper returns a single-line non-empty string containing each provided value.
- _Unit tests:_ `tests/unit/test_enums.py` — assert each enum's member set equals the documented set; assert `FeatureType` reachable from top-level package.
- _Integration tests:_ none required; the contracts are import- and inheritance-shaped only, fully verifiable at the unit layer.

---

## P-2 — CLI Entry and Project Scaffolding

**Goal:** Users can scaffold a producer or consumer project from the terminal before the SDK runtime exists. Downstream tasks build on these scaffold outputs.

**Demo outcome:** Fresh machine → `pip install kitefs` → `kitefs init` produces a complete producer project layout on disk; `kitefs init-config` produces a consumer-only configuration.

### T-003 — CLI Entry Point and Error Boundary

**Status:** not started
**Branch:** `feat/T-003-cli-entry`
**Goal:** Set up the CLI framework and the outermost error boundary.
**Description:** Create the CLI command group and wire the console-script. Every subcommand has a `--help` flag and rejects invalid input before doing any work. Catch `KiteFSError` subclasses and render plain-text actionable messages on stderr with a non-zero exit code. No raw tracebacks for expected user errors. Unexpected errors fall through with their traceback.
**Requirements and References:** [FR-CLI-001](02-product-requirements.md#fr-cli-001--installed-cli-entry-point), [AP-7](04-architecture.md#architectural-design-principles), [CLI Error Boundary](03-system-behavior.md#cli-error-boundary)

### T-004 — kitefs init (Producer Scaffold)

**Status:** not started
**Branch:** `feat/T-004-cli-init`
**Goal:** Scaffold a complete producer project from the CLI.
**Description:** When `./kitefs.yaml` does not exist, create the full producer scaffold: `kitefs.yaml` with `runtime.target: local`, `./feature_store/definitions/` containing one example feature group definition, the managed offline and online data directories at their fixed conventional paths, an empty local registry file, and `.gitignore` entries for the managed data directories and the local registry file. Abort with a non-zero exit code if a configuration already exists. Print a confirmation summary. CLI-only — does not load the SDK runtime.
**Watchpoints:** Scaffold creation must be atomic — a mid-way failure leaves no partial output visible (pre-flight all target paths before any write, or write-to-temp-then-rename). See `docs/03-system-behavior.md` `kitefs init`.
**Requirements and References:** [FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization), [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact), [`kitefs init`](03-system-behavior.md)

### T-005 — kitefs init-config (Consumer Scaffold)

**Status:** not started
**Branch:** `feat/T-005-cli-init-config`
**Goal:** Scaffold a consumer-only project from the CLI.
**Description:** Create only `kitefs.yaml` with `runtime.target: remote` and a remote section that includes the remote registry and online store but omits the offline store. Abort if a configuration already exists. Do not create a definitions directory, data directories, an example, or `.gitignore` entries. CLI-only — does not load the SDK runtime.
**Requirements and References:** [FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization), [`kitefs init-config`](03-system-behavior.md)

---

## P-3 — Feature Definition Types

**Goal:** Users can author feature groups in Python with construction-time validation (BB-03).

### T-006 — Atomic Field Classes

**Status:** not started
**Branch:** `feat/T-006-field-classes`
**Goal:** Implement `EntityKey`, `EventTimestamp`, `Feature`, `JoinKey`, and `Metadata`.
**Description:** Each class validates its own constraints at construction time (e.g. entity key dtype must be `STRING` or `INTEGER`, event timestamp must be `DATETIME`, metadata `description` and `owner` required when metadata is present). Raises `DefinitionError` on violations. Re-export from the top-level package.
**Watchpoints:** Per-class construction-time constraints are fully enumerated in `docs/06-api-and-cli-contracts.md`. Refinement must enumerate each as an explicit acceptance criterion rather than leaving them implicit in prose.
**Requirements and References:** [FR-DEF-001](02-product-requirements.md#fr-def-001--feature-group-definition-as-code), [FR-DEF-002](02-product-requirements.md#fr-def-002--field-type-definitions)

### T-007 — Expect Builder

**Status:** not started
**Branch:** `feat/T-007-expect-builder`
**Goal:** Implement the `Expect` fluent builder for feature expectations.
**Description:** Support `not_null`, `gt`, `gte`, `lt`, `lte`, `is_in`. Validate argument types at call time. Raises `DefinitionError` on invalid arguments. Reject expectations on structural fields at the point where they would be attached.
**Requirements and References:** [FR-DEF-004](02-product-requirements.md#fr-def-004--feature-expectations)

### T-008 — FeatureGroup Composite

**Status:** not started
**Branch:** `feat/T-008-feature-group`
**Goal:** Implement `FeatureGroup` with within-group structural checks.
**Description:** Validates: required fields present, non-empty features list, exactly one entity key, exactly one event timestamp, at most one join key, unique field names across structural and feature fields, identifier names match the CON-009 regex, event timestamp is `DATETIME`. Holds per-operation validation modes with declared defaults. Raises `DefinitionError` on violations.
**Watchpoints:** CON-009 identifier-name regex is enforced *here at construction time*. Cross-set checks (duplicate group names, reserved names `year`/`month`, join references, dtype matching) belong to T-020 — do not duplicate them here.
**Requirements and References:** [FR-DEF-001](02-product-requirements.md#fr-def-001--feature-group-definition-as-code), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes), [CON-004](02-product-requirements.md#con-004--single-entity-key), [CON-009](02-product-requirements.md#con-009--identifier-naming-rules)

---

## P-4 — Validation Engine

**Goal:** A stateless validation engine ready to plug into operation gates (BB-05). The engine depends only on definition types and enums, so it lands before any storage or runtime work.

### T-009 — Structural Checks

**Status:** not started
**Branch:** `feat/T-009-structural-checks`
**Goal:** Validate row-level structural fields (presence, type compatibility, UTC).
**Description:** Check that entity key, event timestamp, and join key values are present, type-compatible with the declaration, and — for datetimes — UTC per CON-006. These checks are always enforced regardless of validation mode.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [CON-006](02-product-requirements.md#con-006--utc-only-datetimes)

### T-010 — Feature Expectation Checks

**Status:** not started
**Branch:** `feat/T-010-expectation-checks`
**Goal:** Validate feature field values against declared types and expectations.
**Description:** Apply type checks and declared `Expect` operators (`gt`, `gte`, `lt`, `lte`, `is_in`, `not_null`) per feature field. Return per-row, per-field failure details.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-DEF-004](02-product-requirements.md#fr-def-004--feature-expectations)

### T-011 — Mode-Aware Orchestration and Report

**Status:** not started
**Branch:** `feat/T-011-validation-modes`
**Goal:** Orchestrate validation with mode semantics (`ERROR`, `FILTER`, `NONE`) and produce reports.
**Description:** Structural-check failures reject the operation in every mode. `ERROR` rejects the entire operation on any feature-check failure. `FILTER` excludes failing rows and continues (empty result is allowed and reported). `NONE` skips feature checks. Produce a validation report with summary counts and per-failure details sufficient to identify which rows and fields failed and why.
**Watchpoints:** Structural checks (T-009) run in *every* mode including `NONE` — `NONE` skips feature checks only, not structural checks. `FILTER` with all rows failing must produce an empty result with a report, not raise an error.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes)

---

## P-5 — Configuration Manager

**Goal:** `kitefs.yaml` is loaded and validated end-to-end per the prescribed sequence, with runtime target resolution (BB-10).

### T-012 — Configuration Loader

**Status:** not started
**Branch:** `feat/T-012-config-loader`
**Goal:** Implement the full `kitefs.yaml` load-and-validate pipeline in one coherent task.
**Description:** Read `./kitefs.yaml` from the project root and run the prescribed configuration loading sequence: parse the file; validate required project-level fields (version, project name, runtime target); validate fixed literal fields (remote store backend types) as literal values; apply environment variable interpolation (`${VAR:-default}`) to configurable fields only; reject interpolation expressions in fixed fields; validate the fully resolved configuration. Validate the structural shape of the optional `remote` section (required keys present, value types correct, unsupported backend identifiers rejected, remote runtime target requires a remote section) without checking whether individual store settings are complete or reachable — that check is deferred to operation time (T-031). Distinguish missing configuration (suggests initialization) from invalid configuration (identifies the offending setting and the source variable when interpolation is involved).
**Watchpoints:** Large task — refinement should produce acceptance criteria across all five distinct concerns: (1) parse, (2) required-field validation, (3) fixed-literal vs. interpolatable field distinction, (4) `${VAR:-default}` interpolation semantics, (5) structural remote-section shape. Operation-time remote completeness checks are deferred to T-044, not here.
**Requirements and References:** [FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration), [FR-CFG-003](02-product-requirements.md#fr-cfg-003--environment-variable-interpolation), [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation), [Configuration Loading Sequence](03-system-behavior.md#configuration-loading-sequence)

### T-013 — Runtime Target Override

**Status:** not started
**Branch:** `feat/T-013-target-override`
**Goal:** Allow runtime target switching via environment variable.
**Description:** Check for a `KITEFS_RUNTIME_TARGET` environment variable. When set, it overrides the `runtime.target` field from config without modifying the file.
**Requirements and References:** [FR-CFG-002](02-product-requirements.md#fr-cfg-002--runtime-target-switching)

---

## P-6 — Provider Boundary and Local Provider

**Goal:** Storage abstraction exists with a working local implementation (BB-09).

### T-014 — Provider ABCs

**Status:** not started
**Branch:** `feat/T-014-provider-abcs`
**Goal:** Define `Provider`, `RegistryStore`, `OfflineStore`, `OnlineStore` abstract base classes.
**Description:** Create `src/kitefs/providers/base.py` with the three store interfaces and the `Provider` factory ABC. Core modules will depend on these interfaces only. No provider-specific imports here.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [NFR-MAINT-001](02-product-requirements.md#nfr-maint-001--modular-architecture), [Provider Abstraction Boundary](04-architecture.md#provider-abstraction-boundary)

### T-015 — Local RegistryStore

**Status:** not started
**Branch:** `feat/T-015-local-registry-store`
**Goal:** Implement the `RegistryStore` interface for the local provider, backed by a single JSON file.
**Description:** Provide whole-document read and overwrite of the registry artifact at the fixed local path `./feature_store/registry.json`. Serialization is deterministic so the file can be inspected and diffed per the storage contract. This is the only place that touches the local registry file on disk; higher-level registry logic in BB-04 calls this interface and never reads or writes the file directly.
**Watchpoints:** "Deterministic serialization" is a four-part spec in `docs/05-data-and-storage-contracts.md` — `sort_keys=True`, features sorted by name, join_keys sorted by name, trailing newline. `json.dumps` default order is not sufficient.
**Requirements and References:** [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact), [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [Registry JSON](05-data-and-storage-contracts.md#registry-json)

### T-016 — Local OfflineStore

**Status:** not started
**Branch:** `feat/T-016-local-offline-store`
**Goal:** Implement local offline storage with Parquet files and the prescribed partition layout.
**Description:** Write Parquet files under the managed directory with year/month partitioning and the documented file-naming convention (including the ingestion source prefix and short-id collision resolution). Reads support partition-scoped access. Writes are atomic (write-to-temp then rename) so that a failed write leaves no partial file visible.
**Watchpoints:** Reads must use `pyarrow.dataset` with `partitioning='hive'` and scanner filter pushdown — not manual filesystem walk or filename parsing. Partition path (year=/month=) is the only authoritative time signal; file-name timestamp is not used for filtering.
**Requirements and References:** [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes), [Offline Store Layout](05-data-and-storage-contracts.md)

### T-017 — Local OnlineStore

**Status:** not started
**Branch:** `feat/T-017-local-online-store`
**Goal:** Implement local online storage with SQLite (one table per online-capable group).
**Description:** Create and manage SQLite tables for materialized online data per the documented schema. Support latest-per-entity upserts and key-based point lookups. Preserve prior committed state on write failure (no partial visibility).
**Watchpoints:** Write pattern is full-table replacement within one transaction (`BEGIN; DELETE FROM …; executemany INSERT …; COMMIT`) — not upsert. Set `journal_mode=WAL` and `busy_timeout=5000` on every connection open, not only at creation time.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-018 — Provider Factory Wiring

**Status:** not started
**Branch:** `feat/T-018-provider-factory`
**Goal:** Wire the provider factory to return the local provider based on configuration.
**Description:** Build the `LocalProvider` bundle that returns the three local store implementations. Factory selects provider based on the resolved runtime target. AWS provider returns a not-implemented stub until P-12. Core modules receive only the interface types — never provider-specific clients.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [FR-CFG-002](02-product-requirements.md#fr-cfg-002--runtime-target-switching), [CON-007](02-product-requirements.md#con-007--local-and-aws-providers-only)

---

## P-7 — Registry Manager and First SDK Slice

**Goal:** `FeatureStore.apply`, `list_feature_groups`, and `describe_feature_group` work end-to-end on local (BB-04, BB-02).

**Demo outcome:** Users declare groups in Python, call `apply`, then list and describe them programmatically.

### T-019 — Definition Discovery

**Status:** not started
**Branch:** `feat/T-019-definition-discovery`
**Goal:** Automatically discover feature group objects from the definitions directory.
**Description:** Scan `./feature_store/definitions/` for Python modules. Collect all module-level `FeatureGroup` instances regardless of variable name. Files outside `definitions/` are not scanned. Report an actionable message when no definitions are found.
**Requirements and References:** [FR-REG-002](02-product-requirements.md#fr-reg-002--definition-discovery)

### T-020 — Cross-Definition Validation

**Status:** not started
**Branch:** `feat/T-020-cross-validation`
**Goal:** Validate discovered definitions as a complete set before any registry write.
**Description:** Check for duplicate group names, invalid join references, join dtype mismatches between referencing and referenced join keys, and reserved field names (e.g. `year`, `month`). Collect all errors and report together in a single error before any registry write begins.
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation), [CON-009](02-product-requirements.md#con-009--identifier-naming-rules)

### T-021 — Registry Artifact Builder

**Status:** not started
**Branch:** `feat/T-021-registry-builder`
**Goal:** Build the registry artifact from validated definitions.
**Description:** Produce a JSON-serializable registry structure per the storage contract. Preserve runtime-managed fields (notably `last_materialized_at`) for groups that survive regeneration. Update `applied_at` per registered group to the current UTC time on success.
**Watchpoints:** Output must be byte-deterministic per the Registry JSON contract (see T-015 watchpoint). Groups absent from the new definition set drop their registry entry entirely — no tombstoning.
**Requirements and References:** [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact), [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-022 — FeatureStore Construction and Public Surface

**Status:** not started
**Branch:** `feat/T-022-feature-store-init`
**Goal:** Implement `FeatureStore.__init__` and finalize the top-level package re-exports.
**Description:** Constructor treats the current working directory as the project root, follows the configuration loading sequence, and builds the provider. Raises `ConfigurationError` on missing or invalid configuration. Wire the public package surface (`from kitefs import FeatureStore, FeatureGroup, EntityKey, ...`) per the contracts doc.
**Requirements and References:** [FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration), [NFR-MAINT-001](02-product-requirements.md#nfr-maint-001--modular-architecture), [Public Package Surface](06-api-and-cli-contracts.md#public-package-surface)

### T-023 — FeatureStore.apply (Local)

**Status:** not started
**Branch:** `feat/T-023-sdk-apply`
**Goal:** Wire `FeatureStore.apply` for local-only registry generation.
**Description:** Orchestrate discovery → cross-validation → artifact build → local registry write. Return `ApplyResult`. A failure before registry writes begin leaves the registry unchanged. Publish mode is deferred to P-12.
**Watchpoints:** The atomicity invariant — any failure during discovery, cross-validation, or artifact build must leave the on-disk registry unchanged. Acceptance criteria must include a test scenario for each failure point.
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-024 — List and Describe Feature Groups

**Status:** not started
**Branch:** `feat/T-024-list-describe`
**Goal:** Implement `list_feature_groups` and `describe_feature_group` on the SDK.
**Description:** Read from the active registry. Return summaries or full descriptions including runtime-managed fields when present. Empty registry returns an empty list (not an error). Unknown group raises `FeatureGroupNotFoundError`. A missing or unreachable selected registry fails with an actionable error.
**Requirements and References:** [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe)

---

## P-8 — Local CLI Surface

**Goal:** End-to-end local producer workflow runs from the terminal (BB-01).

**Demo outcome:** Fresh machine quickstart — install → `kitefs init` → write a group → `kitefs apply` → `kitefs list`.

### T-025 — kitefs apply

**Status:** not started
**Branch:** `feat/T-025-cli-apply`
**Goal:** Expose `apply` as a CLI subcommand.
**Description:** Call `FeatureStore.apply`. Wire the `--publish` and `--no-confirm` flags (actual remote write is deferred to P-12). Render `ApplyResult` as human-readable output.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations), [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-026 — kitefs list and kitefs describe

**Status:** not started
**Branch:** `feat/T-026-cli-list-describe`
**Goal:** Expose list and describe as CLI subcommands with output format options.
**Description:** Default human-readable table output. Support `--format text|json` for output format selection. Support `--output <path>` to write to a file.
**Watchpoints:** `--format json` must emit the on-disk registry entry shape, not the `FeatureGroupDescription` dataclass repr — requires explicit translation. Error message for missing registry differs by runtime target (local: suggest `init` + `apply`; remote: suggest producer `apply --publish`).
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations), [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe)

---

## P-9 — Offline Ingestion

**Goal:** Users can ingest a DataFrame or file into the offline store with validation (write-path vertical slice).

**Demo outcome:** Declare → apply → ingest data → Parquet files visible on disk in the expected partition layout.

### T-027 — Offline Store Manager Write Path

**Status:** not started
**Branch:** `feat/T-027-offline-write`
**Goal:** Implement append-only write coordination in the offline store manager (BB-06).
**Description:** Accept validated data, write through the `OfflineStore` interface with the ingestion source prefix and partition layout. Never modify or delete prior files. Multi-partition batch writes guarantee per-file atomicity.
**Requirements and References:** [FR-ING-002](02-product-requirements.md#fr-ing-002--append-only-writes), [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes)

### T-028 — FeatureStore.ingest

**Status:** not started
**Branch:** `feat/T-028-sdk-ingest`
**Goal:** Wire SDK `ingest` for DataFrame input with shape checks and the ingestion validation gate.
**Description:** Verify the target group exists, check the input contains the entity key, event timestamp, join key, and declared feature fields, drop undeclared columns, apply the group's ingestion validation mode via the validation engine, then write through the offline store manager. Return `IngestResult` with row counts and the validation report (when produced).
**Watchpoints:** Five phases run in strict order with distinct error types: group lookup (`FeatureGroupNotFoundError`) → shape check (`IngestionShapeError`) → row-level structural checks (always-on, independent of mode) → feature checks (mode-driven, `ValidationError` with `error.report` in ERROR mode) → write. `IngestResult.written_files` carries absolute paths for local writes.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion), [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation), [CON-003](02-product-requirements.md#con-003--pandas-as-primary-dataframe)

### T-029 — File Input Support (CSV/Parquet)

**Status:** not started
**Branch:** `feat/T-029-file-input`
**Goal:** Allow `FeatureStore.ingest` to accept a local `.csv` or `.parquet` file path in addition to a DataFrame.
**Description:** Detect format by file extension and load into a DataFrame inside the SDK, then follow the normal ingest flow. Reject unsupported extensions. File loading is the SDK's responsibility — the CLI passes the path directly without parsing.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion), [NFR-UX-001](02-product-requirements.md#nfr-ux-001--standard-python-interfaces)

### T-030 — kitefs ingest CLI

**Status:** not started
**Branch:** `feat/T-030-cli-ingest`
**Goal:** Expose ingestion as a CLI subcommand.
**Description:** Accept group name and file path arguments. Pass the path directly to the SDK `ingest`. Render result and any validation report to stdout/stderr.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations)

---

## P-10 — Historical Retrieval and Point-in-Time Joins

**Goal:** Training datasets retrievable with point-in-time correctness (read-path vertical slice).

**Demo outcome:** Users build a leak-free training set joining two feature groups.

### T-031 — Offline Store Manager Read Path

**Status:** not started
**Branch:** `feat/T-031-offline-read`
**Goal:** Implement offline reads with event-timestamp filtering and partition pruning.
**Description:** Read Parquet data through the `OfflineStore` interface. Apply partition-level pruning for year/month. Support timestamp comparison operators (`gt`, `gte`, `lt`, `lte`) on the event timestamp column.
**Watchpoints:** Use `pyarrow.dataset` with `partitioning='hive'` and scanner filter pushdown — do not enumerate files manually or parse filenames for filtering.
**Requirements and References:** [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval)

### T-032 — get_historical_features (Single Group)

**Status:** not started
**Branch:** `feat/T-032-historical-single`
**Goal:** Implement single-group historical retrieval with `select` and `where`.
**Description:** Validate request shape (group exists, `select` provided and fields valid, filters target the event timestamp column with supported operators) before any read. Read offline data with filters. Return a DataFrame containing the group's structural columns plus the selected feature fields.
**Requirements and References:** [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval), [NFR-UX-001](02-product-requirements.md#nfr-ux-001--standard-python-interfaces)

### T-033 — Join Engine

**Status:** not started
**Branch:** `feat/T-033-join-engine`
**Goal:** Implement point-in-time correct joins (BB-08).
**Description:** Stateless, no I/O. For each base row, find the most recent joined row with event timestamp ≤ base timestamp. Equality is eligible; rows with later timestamps are never selected. Ties resolve deterministically. Re-running against unchanged data returns the same rows in the same order. Unmatched base rows remain with null joined columns.
**Watchpoints:** Tie-break semantics (equal join-key + equal event timestamp) must use a pinned secondary sort key — refinement must define it explicitly so re-runs against unchanged data are provably identical, not just probably identical.
**Requirements and References:** [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins), [AP-6](04-architecture.md#architectural-design-principles)

### T-034 — get_historical_features (Joined)

**Status:** not started
**Branch:** `feat/T-034-historical-joined`
**Goal:** Support one joined feature group in historical retrieval.
**Description:** Validate join shape (at most one joined group, registered join relationship exists, `select` dict shape valid) before any read. Read base and joined groups, apply the join engine, prefix joined columns with the joined group name; base columns remain unprefixed.
**Watchpoints:** `select` shape changes for the join path: `list[str] | "*"` for single-group, `dict[str, list[str] | "*"]` keyed by group name with join. Structural fields (entity key, event timestamp, join key) are always returned regardless of `select` — callers cannot exclude them.
**Requirements and References:** [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins)

### T-035 — Offline Retrieval Validation Gate

**Status:** not started
**Branch:** `feat/T-035-retrieval-validation`
**Goal:** Apply validation to retrieved offline data per each group's retrieval mode.
**Description:** After reading data, apply the validation engine with the group's `offline_retrieval_validation` mode. For joined retrieval, validate the base group and the joined group independently per their respective modes.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes)

---

## P-11 — Materialization and Online Serving

**Goal:** Latest feature values served from the online store (serving-path vertical slice).

**Demo outcome:** Full local pipeline — apply → ingest → materialize → online retrieval.

### T-036 — Online Store Manager

**Status:** not started
**Branch:** `feat/T-036-online-manager`
**Goal:** Implement the online store manager for writes and reads (BB-07).
**Description:** Coordinate latest-per-entity materialization writes and key-based reads through the `OnlineStore` interface. Preserve prior committed online state on write failure. Surface the underlying error message for per-group failures.
**Watchpoints:** "Latest-per-entity" describes the *result*, not the write pattern. The SQLite implementation (T-017) uses full-table replacement — not upsert. On write failure the table state is whatever was last committed; no partial writes are visible.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-037 — FeatureStore.materialize (Named Group)

**Status:** not started
**Branch:** `feat/T-037-materialize-named`
**Goal:** Materialize a single named online-eligible group.
**Description:** Validate the named group exists and is online-eligible; reject offline-only and unknown groups with actionable errors. Read latest-per-entity from offline, write to online. A group with no offline data is reported as skipped. Idempotent. Report a per-group outcome and update `last_materialized_at` in the local working registry on success.
**Watchpoints:** `last_materialized_at` is written to the *local* working registry on success regardless of runtime target — it propagates to the remote registry only via a subsequent `apply --publish`. Write failures go into `MaterializeResult.failed`, not raised as exceptions.
**Requirements and References:** [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups)

### T-038 — FeatureStore.materialize (All Groups)

**Status:** not started
**Branch:** `feat/T-038-materialize-all`
**Goal:** Materialize all online-eligible groups with per-group failure isolation.
**Description:** Silently exclude offline-only groups. Run materialization for each remaining group. Report per-group outcomes (succeeded, skipped, failed) through the same result shape as the named-group case. A per-group failure does not stop the run or roll back other groups.
**Watchpoints:** Offline-only groups are silently excluded from the run *and* from the result — they do not appear in succeeded, skipped, or failed buckets. A per-group failure does not roll back already-completed groups.
**Requirements and References:** [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-039 — kitefs materialize CLI

**Status:** not started
**Branch:** `feat/T-039-cli-materialize`
**Goal:** Expose materialization as a CLI subcommand.
**Description:** Accept an optional group name. Call SDK `materialize`. Render per-group outcomes to stdout.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations)

### T-040 — FeatureStore.get_online_features

**Status:** not started
**Branch:** `feat/T-040-online-retrieval`
**Goal:** Implement single-entity online retrieval.
**Description:** Validate request shape (group exists and is online-eligible, `select` provided, `where` targets the entity key with a single `eq` operator, value is type-compatible). Return a dict on hit (structural fields plus selected features), empty dict on miss. No validation gate on online retrieval.
**Requirements and References:** [FR-ONL-002](02-product-requirements.md#fr-onl-002--single-entity-online-retrieval), [NFR-UX-001](02-product-requirements.md#nfr-ux-001--standard-python-interfaces)

---

## P-12 — Remote Registry and Publish

**Goal:** AWS packaging is introduced. Remote registry operations work. Users can publish and discover features from AWS.

**Demo outcome:** `apply --publish` writes to S3 → remote `list` and `describe` read from S3 → an `init-config` project can list and describe remote groups.

### T-041 — AWS Packaging Extra and Provider Stub

**Status:** not started
**Branch:** `feat/T-041-aws-packaging`
**Goal:** Introduce the `[aws]` optional install extra and the `providers/aws/` sub-package.
**Description:** Add the `[aws]` optional dependency group to `pyproject.toml` covering boto3 and any other AWS-only dependencies. Create the `providers/aws/` sub-package as the only place AWS clients may be imported. Replace the not-implemented AWS provider stub from T-018 with a real factory entry that resolves AWS implementations. Confirm `pip install kitefs` (without extras) still imports the base package cleanly without any AWS dependency available.
**Watchpoints:** Add a packaging-level integration test that `import kitefs` succeeds in a clean environment without the `[aws]` extra — verifies no top-level boto3 import path was accidentally introduced.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [CON-007](02-product-requirements.md#con-007--local-and-aws-providers-only), [Packaging Model](04-architecture.md#packaging-model)

### T-042 — AWS Credential Chain and Error Mapping

**Status:** not started
**Branch:** `feat/T-042-aws-credentials`
**Goal:** Rely on the standard AWS credential chain and map permission errors.
**Description:** Use the standard boto3 credential resolution (env vars, AWS config, IAM role). Map missing or insufficient credentials/permissions to actionable errors that identify the affected store. Never leak secret values.
**Requirements and References:** [FR-PROV-002](02-product-requirements.md#fr-prov-002--aws-credential-chain)

### T-043 — AWS RegistryStore

**Status:** not started
**Branch:** `feat/T-043-aws-registry`
**Goal:** Implement AWS registry storage as a JSON object in S3.
**Description:** Read and overwrite the registry JSON at the configured S3 key (`s3://{bucket}/{s3_prefix}/registry.json`). Same interface as local.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact)

### T-044 — Per-Operation Remote Configuration Validation

**Status:** not started
**Branch:** `feat/T-044-remote-op-validation`
**Goal:** Validate remote store availability before each operation that needs it.
**Description:** Before an operation touches a remote store, check that the required remote sub-section (registry, offline, or online) is present, fully configured, and internally valid. Fail with an actionable error that identifies the missing or invalid capability and the operation that triggered the check. This is the lazy validation counterpart to T-012's structural parse.
**Requirements and References:** [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation)

### T-045 — apply --publish End-to-End

**Status:** not started
**Branch:** `feat/T-045-apply-publish`
**Goal:** Enable `apply --publish` to write local then remote registries with confirmation.
**Description:** Unless `--no-confirm` is passed, the CLI prompts for the exact confirmation word **before** the `./kitefs.yaml` check; any response other than the exact word aborts. On confirm: write the local registry, then write the remote registry. Handle partial failure (local succeeds, remote fails) so the local working registry may contain regenerated content while the remote remains stale, and the operation reports failure.
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation), [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations), [Project Root Discovery](03-system-behavior.md#project-root-discovery)

### T-046 — Remote List and Describe Verification

**Status:** not started
**Branch:** `feat/T-046-remote-list-describe`
**Goal:** Verify list and describe work against the remote registry from both project types.
**Description:** Confirm that `list` and `describe` read from the S3 registry when the runtime target is remote. Confirm a project created by `init-config` can list and describe from the published registry without further setup.
**Requirements and References:** [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe), [FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization)

---

## P-13 — Remote Offline Store

**Goal:** Remote ingestion and historical retrieval produce equivalent results to local.

**Demo outcome:** Ingest to S3 → `get_historical_features` with PIT join returns the same results as the local provider.

### T-047 — AWS OfflineStore

**Status:** not started
**Branch:** `feat/T-047-aws-offline`
**Goal:** Implement AWS offline storage with S3 Parquet via PyArrow and boto3.
**Description:** Same partition layout and file-naming convention as local. Atomic writes via S3 put semantics. Reads support partition-scoped access and event-timestamp filtering. Importable only from `providers/aws/` so the base package install does not require boto3.
**Requirements and References:** [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes)

### T-048 — Remote Offline End-to-End Verification

**Status:** not started
**Branch:** `feat/T-048-remote-offline-e2e`
**Goal:** Verify ingestion and historical retrieval (single and joined) work against S3 and match local.
**Description:** Confirm `ingest` writes Parquet files to S3 in the same partition layout and naming as local, and that append-only semantics hold. Confirm `get_historical_features` with single-group and joined retrieval produces equivalent results on local and remote for the same logical data.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion), [FR-ING-002](02-product-requirements.md#fr-ing-002--append-only-writes), [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval), [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins)

---

## P-14 — Remote Online Store and Consumer Serving

**Goal:** Remote materialization and online serving work. A consumer project serves features from DynamoDB.

**Demo outcome:** Remote materialize → `get_online_features` from DynamoDB → consumer `init-config` project retrieves online features.

### T-049 — AWS OnlineStore

**Status:** not started
**Branch:** `feat/T-049-aws-online`
**Goal:** Implement AWS online storage with DynamoDB per-group tables.
**Description:** Create and manage per-group DynamoDB tables with the documented naming (`{dynamodb_table_prefix}{group_name}`). Support latest-per-entity upserts and key-based reads. Surface underlying errors for per-group failure isolation. Importable only from `providers/aws/`.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-050 — Remote Online End-to-End and Consumer Acceptance

**Status:** not started
**Branch:** `feat/T-050-remote-online-consumer`
**Goal:** Verify materialization, online retrieval, and consumer-only project flows work end-to-end against DynamoDB.
**Description:** Confirm `materialize` writes latest-per-entity rows to DynamoDB, isolates per-group failures, and updates `last_materialized_at` only on success. Confirm `get_online_features` returns equivalent results on local and remote. Confirm a project created by `init-config` can perform online retrieval against the configured remote online store without further setup.
**Requirements and References:** [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups), [FR-ONL-002](02-product-requirements.md#fr-onl-002--single-entity-online-retrieval), [FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization)

---

## P-15 — MVP Acceptance Demo (Reference Use Case)

**Goal:** Demonstrate KiteFS end-to-end through the reference use case on both local and remote runtime targets, proving the MVP works as a working alpha.

> **Placeholder.** Task breakdown for this phase will be handled separately. See [Reference Use Case](01-reference-use-case.md) for the scenario this phase will exercise.

---

## P-16 — Post-MVP Backlog

**Goal:** Track future capabilities outside MVP scope. Includes `pull`, batch online retrieval, mock data generation, smart sampling, and incremental materialization.

> **Placeholder.** Task breakdown for this phase will be handled separately. Requirements expected to land here: [FR-REG-005](02-product-requirements.md#fr-reg-005--remote-registry-pull), [FR-ONL-003](02-product-requirements.md#fr-onl-003--batch-online-retrieval), [FR-MOCK-001](02-product-requirements.md#fr-mock-001--mock-data-generation), [FR-SAM-001](02-product-requirements.md#fr-sam-001--smart-sampling), [FR-MAT-002](02-product-requirements.md#fr-mat-002--incremental-materialization).

---

## Requirements Coverage Matrix

Every MVP requirement in [02-product-requirements.md](02-product-requirements.md) is covered by at least one task in P-1 through P-14. Post-MVP requirements (FR-REG-005, FR-ONL-003, FR-MOCK-001, FR-SAM-001, FR-MAT-002) are tracked in P-16.

| Requirement   | Task(s)                                                       |
| ------------- | ------------------------------------------------------------- |
| FR-DEF-001    | T-006, T-008                                                  |
| FR-DEF-002    | T-002, T-006, T-008                                           |
| FR-DEF-003    | T-002                                                         |
| FR-DEF-004    | T-007, T-010                                                  |
| FR-DEF-005    | T-002, T-008, T-011                                           |
| FR-REG-001    | T-004, T-015, T-021, T-043                                    |
| FR-REG-002    | T-019                                                         |
| FR-REG-003    | T-020, T-021, T-023, T-025, T-045                             |
| FR-REG-004    | T-024, T-026, T-046                                           |
| FR-REG-005    | P-16 (deferred)                                               |
| FR-ING-001    | T-028, T-029, T-048                                           |
| FR-ING-002    | T-027, T-048                                                  |
| FR-OFF-001    | T-016, T-027, T-047                                           |
| FR-OFF-002    | T-031, T-032, T-048                                           |
| FR-OFF-003    | T-033, T-034, T-048                                           |
| FR-MAT-001    | T-037, T-038, T-050                                           |
| FR-MAT-002    | P-16 (deferred)                                               |
| FR-ONL-001    | T-017, T-036, T-049                                           |
| FR-ONL-002    | T-040, T-050                                                  |
| FR-ONL-003    | P-16 (deferred)                                               |
| FR-VAL-001    | T-009, T-010, T-011, T-028, T-035                             |
| FR-PROV-001   | T-014, T-015, T-016, T-017, T-018, T-041, T-043, T-047, T-049 |
| FR-PROV-002   | T-042                                                         |
| FR-CFG-001    | T-012, T-022                                                  |
| FR-CFG-002    | T-013, T-018                                                  |
| FR-CFG-003    | T-012                                                         |
| FR-CFG-004    | T-012, T-028, T-044                                           |
| FR-CLI-001    | T-003                                                         |
| FR-CLI-002    | T-025, T-026, T-030, T-039, T-045                             |
| FR-CLI-003    | T-004, T-005, T-046, T-050                                    |
| FR-MOCK-001   | P-16 (deferred)                                               |
| FR-SAM-001    | P-16 (deferred)                                               |
| NFR-REL-001   | T-016, T-027, T-047                                           |
| NFR-REL-002   | T-017, T-036, T-038, T-049                                    |
| NFR-UX-001    | T-028, T-029, T-032, T-040                                    |
| NFR-MAINT-001 | T-001, T-014, T-022                                           |
| CON-001       | T-001                                                         |
| CON-002       | T-001                                                         |
| CON-003       | T-028, T-032                                                  |
| CON-004       | T-008                                                         |
| CON-005       | T-001                                                         |
| CON-006       | T-009                                                         |
| CON-007       | T-018, T-041                                                  |
| CON-008       | P-16 (deferred)                                               |
| CON-009       | T-008, T-020                                                  |
