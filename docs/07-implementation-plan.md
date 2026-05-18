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

**Goal:** A buildable, testable Python package with tooling, error model, and shared enums.

### T-001 — Package Skeleton

**Status:** not started
**Branch:** `feat/T-001-package-skeleton`
**Goal:** Create a pip-installable package with dev tooling ready.
**Description:** Set up `src/kitefs/` layout, `pyproject.toml` (uv), `justfile`, ruff config, pytest config, and `kitefs` console-script entry point. Confirm `pip install -e .` succeeds and `kitefs --help` prints a placeholder.
**Requirements and References:** [CON-001](02-product-requirements.md#con-001--python-312), [CON-002](02-product-requirements.md#con-002--pip-installable-library), [NFR-MAINT-001](02-product-requirements.md#nfr-maint-001--modular-architecture)

### T-002 — Error Model

**Status:** not started
**Branch:** `feat/T-002-error-model`
**Goal:** Establish the shared exception hierarchy (BB-11).
**Description:** Create `src/kitefs/errors.py` with the base `KiteFSError` and all public exception classes. Each exception supports actionable error messages. No behavior logic — just the type tree and message formatting helpers.
**Requirements and References:** [AP-7](04-architecture.md#architectural-design-principles)

### T-003 — Shared Enums

**Status:** not started
**Branch:** `feat/T-003-shared-enums`
**Goal:** Define `FeatureType`, `StorageTarget`, and `ValidationMode` enums.
**Description:** Create the three enums used across definitions, configuration, and validation. Export them from the top-level package.
**Requirements and References:** [FR-DEF-002](02-product-requirements.md#fr-def-002--field-type-definitions), [FR-DEF-003](02-product-requirements.md#fr-def-003--storage-target), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes)

---

## P-2 — Feature Definition Types

**Goal:** Users can author feature groups in Python with construction-time validation (BB-03).

### T-004 — Atomic Field Classes

**Status:** not started
**Branch:** `feat/T-004-field-classes`
**Goal:** Implement `EntityKey`, `EventTimestamp`, `Feature`, `JoinKey`, and `Metadata`.
**Description:** Each class validates its own constraints at construction time (e.g. entity key dtype must be STRING or INTEGER). Raises `DefinitionError` on violations.
**Requirements and References:** [FR-DEF-001](02-product-requirements.md#fr-def-001--feature-group-definition-as-code), [FR-DEF-002](02-product-requirements.md#fr-def-002--field-type-definitions)

### T-005 — Expect Builder

**Status:** not started
**Branch:** `feat/T-005-expect-builder`
**Goal:** Implement the `Expect` fluent builder for feature expectations.
**Description:** Support `not_null`, `gt`, `gte`, `lt`, `lte`, `is_in`. Validate argument types at call time. Raises `DefinitionError` on invalid arguments.
**Requirements and References:** [FR-DEF-004](02-product-requirements.md#fr-def-004--feature-expectations)

### T-006 — FeatureGroup Composite

**Status:** not started
**Branch:** `feat/T-006-feature-group`
**Goal:** Implement `FeatureGroup` with within-group structural checks.
**Description:** Validates: non-empty features list, at most one join key, unique field names across structural and feature fields, field names match CON-009 regex, event timestamp is DATETIME. Raises `DefinitionError` on violations.
**Requirements and References:** [FR-DEF-001](02-product-requirements.md#fr-def-001--feature-group-definition-as-code), [CON-004](02-product-requirements.md#con-004--single-entity-key), [CON-009](02-product-requirements.md#con-009--identifier-naming-rules)

---

## P-3 — Configuration Manager

**Goal:** `kitefs.yaml` is loaded, validated, and exposes runtime target resolution (BB-10).

### T-007 — Configuration Schema and Loader

**Status:** not started
**Branch:** `feat/T-007-config-loader`
**Goal:** Load and validate `kitefs.yaml` for the local runtime target.
**Description:** Define the configuration schema (version, project name, runtime target). Parse YAML, validate required fields, reject missing or malformed configs with actionable errors.
**Requirements and References:** [FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration)

### T-008 — Environment Variable Interpolation

**Status:** not started
**Branch:** `feat/T-008-env-interpolation`
**Goal:** Support `${VAR:-default}` interpolation in configurable fields.
**Description:** Replace interpolation expressions with environment variable values or declared defaults. Reject interpolation in fixed fields. Surface the source variable name in validation errors.
**Requirements and References:** [FR-CFG-003](02-product-requirements.md#fr-cfg-003--environment-variable-interpolation)

### T-009 — Remote Section Parsing

**Status:** not started
**Branch:** `feat/T-009-remote-config`
**Goal:** Parse and lazily validate the remote configuration section.
**Description:** Accept a remote section in kitefs.yaml with offline store, online store, and registry settings. On config load, validate the section's top-level structure (required keys present, value types correct) and reject unsupported backend type identifiers. Do not validate whether individual store settings are complete or reachable — that is deferred to operation time (T-045).
**Requirements and References:** [FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration), [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation)

### T-010 — Runtime Target Override

**Status:** not started
**Branch:** `feat/T-010-target-override`
**Goal:** Allow runtime target switching via environment variable.
**Description:** Check for a `KITEFS_RUNTIME_TARGET` environment variable. When set, it overrides the `runtime.target` field from config without modifying the file.
**Requirements and References:** [FR-CFG-002](02-product-requirements.md#fr-cfg-002--runtime-target-switching)

---

## P-4 — Provider Boundary and Local Provider

**Goal:** Storage abstraction exists with a working local implementation (BB-09).

### T-011 — Provider ABCs

**Status:** not started
**Branch:** `feat/T-011-provider-abcs`
**Goal:** Define `Provider`, `RegistryStore`, `OfflineStore`, `OnlineStore` abstract base classes.
**Description:** Create `src/kitefs/providers/base.py` with the three store interfaces and the provider factory ABC. Core modules will depend on these interfaces only.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [NFR-MAINT-001](02-product-requirements.md#nfr-maint-001--modular-architecture)

### T-012 — Local RegistryStore

**Status:** not started
**Branch:** `feat/T-012-local-registry-store`
**Goal:** Implement local registry storage as a JSON file.
**Description:** Read and write the registry artifact at `./feature_store/registry.json`. Whole-document read and overwrite semantics.
**Requirements and References:** [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact), [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary)

### T-013 — Local OfflineStore

**Status:** not started
**Branch:** `feat/T-013-local-offline-store`
**Goal:** Implement local offline storage with Parquet files and partition layout.
**Description:** Write Parquet files under the managed directory with year/month partitioning. Reads support partition-scoped access. Writes are atomic (write-to-temp then rename).
**Requirements and References:** [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes)

### T-014 — Local OnlineStore

**Status:** not started
**Branch:** `feat/T-014-local-online-store`
**Goal:** Implement local online storage with SQLite (one table per group).
**Description:** Create and manage SQLite tables for materialized online data. Support latest-per-entity upserts and key-based point lookups.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend)

### T-015 — Provider Factory Wiring

**Status:** not started
**Branch:** `feat/T-015-provider-factory`
**Goal:** Wire the provider factory to return a local or AWS provider based on config.
**Description:** Build the `LocalProvider` bundle that returns the three local store implementations. Factory selects provider based on runtime target from configuration. AWS provider returns a not-implemented stub until P-11.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [FR-CFG-002](02-product-requirements.md#fr-cfg-002--runtime-target-switching)

---

## P-5 — Registry Manager and First SDK Slice

**Goal:** `FeatureStore.apply`, `list`, and `describe` work end-to-end on local (BB-04, BB-02).

**Demo outcome:** Users declare groups in Python, call `apply`, then list and describe them programmatically.

### T-016 — Definition Discovery

**Status:** not started
**Branch:** `feat/T-016-definition-discovery`
**Goal:** Automatically discover feature group objects from the definitions directory.
**Description:** Scan `./feature_store/definitions/` for Python modules. Collect all `FeatureGroup` instances regardless of variable name. Fail with actionable message when no definitions found.
**Requirements and References:** [FR-REG-002](02-product-requirements.md#fr-reg-002--definition-discovery)

### T-017 — Cross-Definition Validation

**Status:** not started
**Branch:** `feat/T-017-cross-validation`
**Goal:** Validate discovered definitions as a complete set before any registry write.
**Description:** Check for duplicate group names, invalid join references, join dtype mismatches, reserved field names (`year`, `month`). Collect all errors and report together in a single `DefinitionValidationError`.
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-018 — Registry Artifact Builder

**Status:** not started
**Branch:** `feat/T-018-registry-builder`
**Goal:** Build the registry artifact from validated definitions.
**Description:** Produce a JSON-serializable registry structure. Preserve `last_materialized_at` for groups that survive regeneration. Include `applied_at` timestamp.
**Requirements and References:** [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact), [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-019 — FeatureStore Construction

**Status:** not started
**Branch:** `feat/T-019-feature-store-init`
**Goal:** Implement `FeatureStore.__init__` with config load and provider build.
**Description:** Constructor discovers project root, loads config, builds the provider. Raises `ConfigurationError` on failure.
**Requirements and References:** [FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration), [NFR-MAINT-001](02-product-requirements.md#nfr-maint-001--modular-architecture)

### T-020 — FeatureStore.apply (Local)

**Status:** not started
**Branch:** `feat/T-020-sdk-apply`
**Goal:** Wire `FeatureStore.apply` for local-only registry generation.
**Description:** Orchestrate discovery → cross-validation → artifact build → local registry write. Return `ApplyResult`. Publish mode deferred to P-11.
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-021 — List and Describe Feature Groups

**Status:** not started
**Branch:** `feat/T-021-list-describe`
**Goal:** Implement `list_feature_groups` and `describe_feature_group` on the SDK.
**Description:** Read from the active registry. Return summaries or full descriptions. Empty registry returns empty list. Unknown group raises `FeatureGroupNotFoundError`.
**Requirements and References:** [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe)

---

## P-6 — Local CLI Surface

**Goal:** End-to-end local producer workflow runs from terminal (BB-01).

**Demo outcome:** Fresh machine quickstart — install → `kitefs init` → write a group → `kitefs apply` → `kitefs list`.

### T-022 — CLI Entry Point and Error Boundary

**Status:** not started
**Branch:** `feat/T-022-cli-entry`
**Goal:** Set up the CLI framework with Click and the outermost error boundary.
**Description:** Create the Click group, wire the console-script. Catch `KiteFSError` subclasses and render plain-text messages on stderr. No raw tracebacks for expected errors. `--help` on every command.
**Requirements and References:** [FR-CLI-001](02-product-requirements.md#fr-cli-001--installed-cli-entry-point), [AP-7](04-architecture.md#architectural-design-principles)

### T-023 — kitefs init (Producer)

**Status:** not started
**Branch:** `feat/T-023-cli-init`
**Goal:** Scaffold a producer project from the CLI.
**Description:** Create `./feature_store/definitions/` directory, a starter `kitefs.yaml`, and a `.gitignore` entry for the registry file. Abort if config already exists.
**Requirements and References:** [FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization), [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact)

### T-024 — kitefs apply

**Status:** not started
**Branch:** `feat/T-024-cli-apply`
**Goal:** Expose `apply` as a CLI subcommand.
**Description:** Call `FeatureStore.apply`. Support `--publish` flag (deferred to P-11 for actual remote write) and `--no-confirm`. Render `ApplyResult` as human-readable output.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations), [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-025 — kitefs list and kitefs describe

**Status:** not started
**Branch:** `feat/T-025-cli-list-describe`
**Goal:** Expose list and describe as CLI subcommands with output format options.
**Description:** Default human-readable table output. Support `--format text|json` for output format selection. Support `--output <path>` to write to a file.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations), [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe)

---

## P-7 — Validation Engine

**Goal:** A stateless validation engine ready to plug into operation gates (BB-05).

### T-026 — Structural Checks

**Status:** not started
**Branch:** `feat/T-026-structural-checks`
**Goal:** Validate row-level structural fields (presence, type, UTC).
**Description:** Check that entity key, event timestamp, and join key values are present, type-compatible, and UTC for datetimes. These checks are always enforced regardless of validation mode.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--feature-data-validation), [CON-006](02-product-requirements.md#con-006--utc-only-datetimes)

### T-027 — Feature Expectation Checks

**Status:** not started
**Branch:** `feat/T-027-expectation-checks`
**Goal:** Validate feature field values against declared expectations.
**Description:** Apply type checks and declared `Expect` operators (`gt`, `gte`, `lt`, `lte`, `is_in`, `not_null`) per feature field. Return per-row, per-field failure details.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--feature-data-validation), [FR-DEF-004](02-product-requirements.md#fr-def-004--feature-expectations)

### T-028 — Mode-Aware Orchestration and Report

**Status:** not started
**Branch:** `feat/T-028-validation-modes`
**Goal:** Orchestrate validation with mode semantics (ERROR, FILTER, NONE) and produce reports.
**Description:** `ERROR` rejects the entire operation on any feature-check failure. `FILTER` excludes failing rows and continues. `NONE` skips feature checks. All modes enforce structural checks. Produce a validation report with summary counts and per-failure details.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--feature-data-validation), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes)

---

## P-8 — Offline Ingestion

**Goal:** Users can ingest a DataFrame or file into the offline store with validation (write path vertical slice).

**Demo outcome:** Declare → apply → ingest data → Parquet files visible on disk in expected partition layout.

### T-029 — Offline Store Manager Write Path

**Status:** not started
**Branch:** `feat/T-029-offline-write`
**Goal:** Implement append-only write coordination in the offline store manager (BB-06).
**Description:** Accept validated data, write through the `OfflineStore` interface with the ingestion source prefix and partition layout. Never modify or delete prior files.
**Requirements and References:** [FR-ING-002](02-product-requirements.md#fr-ing-002--append-only-writes), [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes)

### T-030 — FeatureStore.ingest

**Status:** not started
**Branch:** `feat/T-030-sdk-ingest`
**Goal:** Wire SDK `ingest` method with shape checks and validation gate.
**Description:** Verify group exists, check input contains required columns, drop undeclared columns, apply ingestion validation mode, then write. Return `IngestResult` with row counts and optional validation report.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion), [FR-VAL-001](02-product-requirements.md#fr-val-001--feature-data-validation), [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation)

### T-031 — File Input Support (CSV/Parquet)

**Status:** not started
**Branch:** `feat/T-031-file-input`
**Goal:** Allow `ingest` to accept file paths in addition to DataFrames.
**Description:** Detect format by extension (`.csv`, `.parquet`). Load into a DataFrame, then follow normal ingest flow. Reject unsupported extensions.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion)

### T-032 — kitefs ingest CLI

**Status:** not started
**Branch:** `feat/T-032-cli-ingest`
**Goal:** Expose ingestion as a CLI subcommand.
**Description:** Accept group name and file path arguments. Call SDK `ingest`. Render result and any validation report to stdout/stderr.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations)

---

## P-9 — Historical Retrieval and Point-in-Time Joins

**Goal:** Training datasets retrievable with point-in-time correctness (read path vertical slice).

**Demo outcome:** Users build a leak-free training set joining two feature groups.

### T-033 — Offline Store Manager Read Path

**Status:** not started
**Branch:** `feat/T-033-offline-read`
**Goal:** Implement offline reads with event-timestamp filtering and partition pruning.
**Description:** Read Parquet data through `OfflineStore` interface. Apply partition-level pruning for year/month. Support timestamp comparison operators (`gt`, `gte`, `lt`, `lte`) on the event timestamp column.
**Requirements and References:** [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval)

### T-034 — get_historical_features (Single Group)

**Status:** not started
**Branch:** `feat/T-034-historical-single`
**Goal:** Implement single-group historical retrieval with select and where.
**Description:** Validate request shape (group exists, selected fields valid, filters valid). Read offline data with filters. Return DataFrame with structural columns plus selected feature fields.
**Requirements and References:** [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval)

### T-035 — Join Engine

**Status:** not started
**Branch:** `feat/T-035-join-engine`
**Goal:** Implement point-in-time correct joins (BB-08).
**Description:** Stateless, no I/O. For each base row, find the most recent joined row with event timestamp ≤ base timestamp. Deterministic tie-break. No future leakage. Unmatched base rows keep null joined columns.
**Requirements and References:** [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins), [AP-6](04-architecture.md#architectural-design-principles)

### T-036 — get_historical_features (Joined)

**Status:** not started
**Branch:** `feat/T-036-historical-joined`
**Goal:** Support one joined group in historical retrieval.
**Description:** Validate join shape (at most one join, join relationship exists, select dict shape). Read both groups, apply join engine, prefix joined columns with group name.
**Requirements and References:** [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins)

### T-037 — Offline Retrieval Validation Gate

**Status:** not started
**Branch:** `feat/T-037-retrieval-validation`
**Goal:** Apply validation to retrieved offline data per the group's retrieval mode.
**Description:** After reading data, apply validation engine with the group's `offline_retrieval_validation` mode. For joined retrieval, validate base and joined groups independently per their respective modes.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--feature-data-validation), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes)

---

## P-10 — Materialization and Online Serving

**Goal:** Latest feature values served from the online store (serving path vertical slice).

**Demo outcome:** Full local pipeline — apply → ingest → materialize → online retrieval.

### T-038 — Online Store Manager

**Status:** not started
**Branch:** `feat/T-038-online-manager`
**Goal:** Implement online store manager for writes and reads (BB-07).
**Description:** Coordinate latest-per-entity materialization writes and key-based reads through the `OnlineStore` interface. Handle per-group failure isolation.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-039 — FeatureStore.materialize (Named Group)

**Status:** not started
**Branch:** `feat/T-039-materialize-named`
**Goal:** Materialize a single named online-eligible group.
**Description:** Read latest-per-entity from offline store, write to online store. Reject offline-only groups. Skip groups with no offline data. Idempotent.
**Requirements and References:** [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups)

### T-040 — FeatureStore.materialize (All Groups)

**Status:** not started
**Branch:** `feat/T-040-materialize-all`
**Goal:** Materialize all online-eligible groups with per-group outcome reporting.
**Description:** Run materialization for each online-eligible group. Report succeeded, skipped, and failed outcomes. Update `last_materialized_at` per group on success. A per-group failure does not stop the run.
**Requirements and References:** [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-041 — kitefs materialize CLI

**Status:** not started
**Branch:** `feat/T-041-cli-materialize`
**Goal:** Expose materialization as a CLI subcommand.
**Description:** Accept optional group name. Call SDK `materialize`. Render per-group outcomes to stdout.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations)

### T-042 — FeatureStore.get_online_features

**Status:** not started
**Branch:** `feat/T-042-online-retrieval`
**Goal:** Implement single-entity online retrieval.
**Description:** Validate request shape (group is online-eligible, select valid, where targets entity key with `eq` operator). Return dict on hit, empty dict on miss. No validation gate on online retrieval.
**Requirements and References:** [FR-ONL-002](02-product-requirements.md#fr-onl-002--single-entity-online--retrieval)

---

## P-11 — Remote Registry and Publish

**Goal:** Remote registry operations work. Users can publish and discover features from AWS.

**Demo outcome:** `apply --publish` writes to S3 → remote `list` and `describe` read from S3 → `init-config` project can list remote groups.

### T-043 — AWS Credential Chain and Error Mapping

**Status:** not started
**Branch:** `feat/T-043-aws-credentials`
**Goal:** Rely on standard AWS credential chain and map permission errors.
**Description:** Use the standard boto3 credential resolution. Map missing or insufficient credentials to actionable errors that identify the affected store. Never leak secret values.
**Requirements and References:** [FR-PROV-002](02-product-requirements.md#fr-prov-002--aws-credential-chain)

### T-044 — AWS RegistryStore

**Status:** not started
**Branch:** `feat/T-044-aws-registry`
**Goal:** Implement AWS registry storage as a JSON object in S3.
**Description:** Read and overwrite the registry JSON at the configured S3 key. Same interface as local.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact)

### T-045 — Per-Operation Remote Configuration Validation

**Status:** not started
**Branch:** `feat/T-045-remote-op-validation`
**Goal:** Validate remote store availability before each operation that needs it.
**Description:** Before an operation touches a remote store, check that the required remote sub-section (offline, online, or registry) is present, fully configured, and internally valid. Fail with an actionable error that identifies the missing or invalid capability and the operation that triggered the check. This is the lazy validation counterpart to T-009's structural parse.
**Requirements and References:** [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation)

### T-046 — apply --publish End-to-End

**Status:** not started
**Branch:** `feat/T-046-apply-publish`
**Goal:** Enable `apply --publish` to write local and remote registries.
**Description:** Write local registry, then write remote registry. CLI prompts for `yes` confirmation unless `--no-confirm` is passed. Handle partial failure (local succeeds, remote fails).
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation), [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations)

### T-047 — kitefs init-config (Consumer)

**Status:** not started
**Branch:** `feat/T-047-cli-init-config`
**Goal:** Scaffold a consumer-only project from the CLI.
**Description:** Create only `kitefs.yaml` with a remote-target template. Abort if config already exists. No definitions directory created.
**Requirements and References:** [FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization)

### T-048 — Remote List and Describe Verification

**Status:** not started
**Branch:** `feat/T-048-remote-list-describe`
**Goal:** Verify list and describe work against the remote registry.
**Description:** Confirm that `list` and `describe` read from S3 registry when runtime target is remote. Confirm `init-config` project can list and describe from the published registry.
**Requirements and References:** [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe), [FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization)

---

## P-12 — Remote Offline Store

**Goal:** Remote ingestion and historical retrieval produce equivalent results to local.

**Demo outcome:** Ingest to S3 → `get_historical_features` with PIT join returns the same results as the local provider.

### T-049 — AWS OfflineStore

**Status:** not started
**Branch:** `feat/T-049-aws-offline`
**Goal:** Implement AWS offline storage with S3 Parquet via PyArrow and boto3.
**Description:** Same partition layout and naming as local. Atomic writes via S3 put semantics. Reads support partition-scoped access and timestamp filtering.
**Requirements and References:** [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes)

### T-050 — Remote Ingest Verification

**Status:** not started
**Branch:** `feat/T-050-remote-ingest`
**Goal:** Verify ingestion works against S3 offline store.
**Description:** Confirm `ingest` writes Parquet files to S3 with the same partition layout and naming as local. Confirm append-only semantics hold.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion), [FR-ING-002](02-product-requirements.md#fr-ing-002--append-only-writes)

### T-051 — Remote Historical Retrieval Verification

**Status:** not started
**Branch:** `feat/T-051-remote-historical`
**Goal:** Verify historical retrieval and PIT joins work against S3.
**Description:** Confirm `get_historical_features` with single-group and joined retrieval produces equivalent results on local and remote for the same logical data.
**Requirements and References:** [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval), [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins)

---

## P-13 — Remote Online Store and Consumer Serving

**Goal:** Remote materialization and online serving work. A consumer project serves features from DynamoDB.

**Demo outcome:** Remote materialize → `get_online_features` from DynamoDB → consumer `init-config` project retrieves online features.

### T-052 — AWS OnlineStore

**Status:** not started
**Branch:** `feat/T-052-aws-online`
**Goal:** Implement AWS online storage with DynamoDB per-group tables.
**Description:** Create and manage DynamoDB tables. Support latest-per-entity upserts and key-based reads. Handle provider-managed table namespacing.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-053 — Remote Materialize Verification

**Status:** not started
**Branch:** `feat/T-053-remote-materialize`
**Goal:** Verify materialization works against DynamoDB.
**Description:** Confirm `materialize` writes latest-per-entity rows to DynamoDB. Confirm per-group failure isolation and `last_materialized_at` update.
**Requirements and References:** [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups)

### T-054 — Remote Online Retrieval and Consumer Acceptance

**Status:** not started
**Branch:** `feat/T-054-remote-online-consumer`
**Goal:** Verify online retrieval from DynamoDB and consumer project acceptance.
**Description:** Confirm `get_online_features` returns equivalent results on local and remote. Confirm a consumer `init-config` project can perform online retrieval without further setup.
**Requirements and References:** [FR-ONL-002](02-product-requirements.md#fr-onl-002--single-entity-online--retrieval), [FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization)

---

## P-15 — Post-MVP Backlog

**Goal:** Track future capabilities outside MVP scope. These tasks start after MVP acceptance.

### T-055 — Registry Pull

**Status:** not started
**Branch:** `feat/T-055-registry-pull`
**Goal:** Pull remote registry into local working environment.
**Description:** `FeatureStore.pull` and `kitefs pull` CLI. Overwrite local registry with remote contents.
**Requirements and References:** [FR-REG-005](02-product-requirements.md#fr-reg-005--remote-registry-pull)

### T-056 — Batch Online Retrieval

**Status:** not started
**Branch:** `feat/T-056-batch-online`
**Goal:** Accept multiple entity keys in one online retrieval call.
**Description:** Extend `get_online_features` to support an `in` operator for batch key lookup. Preserve input order. Represent misses distinctly.
**Requirements and References:** [FR-ONL-003](02-product-requirements.md#fr-onl-003--batch-online-retrieval)

### T-057 — Mock Data Generation

**Status:** not started
**Branch:** `feat/T-057-mock-data`
**Goal:** Generate synthetic feature data from registered definitions.
**Description:** Produce rows that satisfy declared types and expectations. Write to local offline store. Configurable timestamp range and row count.
**Requirements and References:** [FR-MOCK-001](02-product-requirements.md#fr-mock-001--mock-data-generation)

### T-058 — Smart Sampling

**Status:** not started
**Branch:** `feat/T-058-smart-sampling`
**Goal:** Pull a subset of remote offline data into local.
**Description:** Support row count, percentage, or timestamp range selection. Preserve feature group structure. Sampled data queryable through standard retrieval.
**Requirements and References:** [FR-SAM-001](02-product-requirements.md#fr-sam-001--smart-sampling)

### T-059 — Incremental Materialization

**Status:** not started
**Branch:** `feat/T-059-incremental-materialize`
**Goal:** Materialize only rows within an event-timestamp range.
**Description:** Accept timestamp range. Only rows in range are considered. Online store still holds at most one latest row per entity key after the run.
**Requirements and References:** [FR-MAT-002](02-product-requirements.md#fr-mat-002--incremental-materialization)

---

## Requirements Coverage Matrix

Every requirement in [02-product-requirements.md](02-product-requirements.md) is covered by at least one task.

| Requirement | Task(s) |
| --- | --- |
| FR-DEF-001 | T-004, T-006 |
| FR-DEF-002 | T-003, T-004, T-006 |
| FR-DEF-003 | T-003 |
| FR-DEF-004 | T-005, T-027 |
| FR-DEF-005 | T-003, T-028 |
| FR-REG-001 | T-012, T-018, T-023, T-044 |
| FR-REG-002 | T-016 |
| FR-REG-003 | T-017, T-018, T-020, T-024, T-046 |
| FR-REG-004 | T-021, T-025, T-048 |
| FR-REG-005 | T-055 |
| FR-ING-001 | T-030, T-031 |
| FR-ING-002 | T-029 |
| FR-OFF-001 | T-013, T-029, T-049 |
| FR-OFF-002 | T-033, T-034, T-051 |
| FR-OFF-003 | T-035, T-036, T-051 |
| FR-MAT-001 | T-039, T-040, T-041, T-053 |
| FR-MAT-002 | T-059 |
| FR-ONL-001 | T-014, T-038, T-052 |
| FR-ONL-002 | T-042, T-054 |
| FR-ONL-003 | T-056 |
| FR-VAL-001 | T-026, T-027, T-028, T-030, T-037 |
| FR-PROV-001 | T-011, T-012, T-013, T-014, T-015, T-044, T-049, T-052 |
| FR-PROV-002 | T-043 |
| FR-CFG-001 | T-007, T-009, T-019 |
| FR-CFG-002 | T-010, T-015 |
| FR-CFG-003 | T-008 |
| FR-CFG-004 | T-009, T-030, T-045 |
| FR-CLI-001 | T-022 |
| FR-CLI-002 | T-024, T-025, T-032, T-041, T-046 |
| FR-CLI-003 | T-023, T-047 |
| FR-MOCK-001 | T-057 |
| FR-SAM-001 | T-058 |
| NFR-REL-001 | T-013, T-029, T-049 |
| NFR-REL-002 | T-038, T-040, T-052 |
| NFR-UX-001 | T-030, T-034, T-042 |
| NFR-MAINT-001 | T-001, T-011, T-019 |
| CON-001 | T-001 |
| CON-002 | T-001 |
| CON-003 | T-030, T-034 |
| CON-004 | T-006 |
| CON-005 | T-001 |
| CON-006 | T-026 |
| CON-007 | T-011, T-015 |
| CON-008 | P-15 (deferred) |
| CON-009 | T-006, T-017 |