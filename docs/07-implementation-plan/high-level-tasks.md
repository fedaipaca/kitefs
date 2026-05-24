# Implementation Plan

## Purpose

This file defines implementation sequencing for the KiteFS feature store library. It owns task planning and delivery boundaries only.

## Owns

- Phases.
- Tasks.
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
- **Status:** `not started` or `done`.
- **Development flow:** Vertical. Each phase delivers a demoable outcome where possible.
- **Task scope:** Single-purpose. Small, self-contained changes.

---

## P-3 — Feature Definition Types

**Goal:** Users can author feature groups in Python with construction-time validation (BB-03).

### T-006 — Atomic Field Classes

**Status:** not started
**Goal:** Implement `EntityKey`, `EventTimestamp`, `Feature`, `JoinKey`, and `Metadata`.
**Description:** Each class validates its own constraints at construction time (e.g. entity key dtype must be `STRING` or `INTEGER`, event timestamp must be `DATETIME`, metadata `description` and `owner` required when metadata is present). Raises `DefinitionError` on violations. Re-export from the top-level package.
**Watchpoints:** Per-class construction-time constraints are fully enumerated in `docs/06-api-and-cli-contracts.md`. Refinement must enumerate each as an explicit acceptance criterion rather than leaving them implicit in prose.
**Requirements and References:** [FR-DEF-001](02-product-requirements.md#fr-def-001--feature-group-definition-as-code), [FR-DEF-002](02-product-requirements.md#fr-def-002--field-type-definitions)

### T-007 — Expect Builder

**Status:** not started
**Goal:** Implement the `Expect` fluent builder for feature expectations.
**Description:** Support `not_null`, `gt`, `gte`, `lt`, `lte`, `is_in`. Validate argument types at call time. Raises `DefinitionError` on invalid arguments. Reject expectations on structural fields at the point where they would be attached.
**Requirements and References:** [FR-DEF-004](02-product-requirements.md#fr-def-004--feature-expectations)

### T-008 — FeatureGroup Composite

**Status:** not started
**Goal:** Implement `FeatureGroup` with within-group structural checks.
**Description:** Validates: required fields present, non-empty features list, exactly one entity key, exactly one event timestamp, at most one join key, unique field names across structural and feature fields, identifier names match the CON-009 regex, event timestamp is `DATETIME`. Holds per-operation validation modes with declared defaults. Raises `DefinitionError` on violations.
**Watchpoints:** CON-009 identifier-name regex is enforced _here at construction time_. Cross-set checks (duplicate group names, reserved names `year`/`month`, join references, dtype matching) belong to T-020 — do not duplicate them here.
**Requirements and References:** [FR-DEF-001](02-product-requirements.md#fr-def-001--feature-group-definition-as-code), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes), [CON-004](02-product-requirements.md#con-004--single-entity-key), [CON-009](02-product-requirements.md#con-009--identifier-naming-rules)

---

## P-4 — Validation Engine

**Goal:** A stateless validation engine ready to plug into operation gates (BB-05). The engine depends only on definition types and enums, so it lands before any storage or runtime work.

### T-009 — Structural Checks

**Status:** not started
**Goal:** Validate row-level structural fields (presence, type compatibility, UTC).
**Description:** Check that entity key, event timestamp, and join key values are present, type-compatible with the declaration, and — for datetimes — UTC per CON-006. These checks are always enforced regardless of validation mode.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [CON-006](02-product-requirements.md#con-006--utc-only-datetimes)

### T-010 — Feature Expectation Checks

**Status:** not started
**Goal:** Validate feature field values against declared types and expectations.
**Description:** Apply type checks and declared `Expect` operators (`gt`, `gte`, `lt`, `lte`, `is_in`, `not_null`) per feature field. Return per-row, per-field failure details.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-DEF-004](02-product-requirements.md#fr-def-004--feature-expectations)

### T-011 — Mode-Aware Orchestration and Report

**Status:** not started
**Goal:** Orchestrate validation with mode semantics (`ERROR`, `FILTER`, `NONE`) and produce reports.
**Description:** Structural-check failures reject the operation in every mode. `ERROR` rejects the entire operation on any feature-check failure. `FILTER` excludes failing rows and continues (empty result is allowed and reported). `NONE` skips feature checks. Produce a validation report with summary counts and per-failure details sufficient to identify which rows and fields failed and why.
**Watchpoints:** Structural checks (T-009) run in _every_ mode including `NONE` — `NONE` skips feature checks only, not structural checks. `FILTER` with all rows failing must produce an empty result with a report, not raise an error.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes)

---

## P-5 — Configuration Manager

**Goal:** `kitefs.yaml` is loaded and validated end-to-end per the prescribed sequence, with runtime target resolution (BB-10).

### T-012 — Configuration Loader

**Status:** not started
**Goal:** Implement the full `kitefs.yaml` load-and-validate pipeline in one coherent task.
**Description:** Read `./kitefs.yaml` from the project root and run the prescribed configuration loading sequence: parse the file; validate required project-level fields (version, project name, runtime target); validate fixed literal fields (remote store backend types) as literal values; apply environment variable interpolation (`${VAR:-default}`) to configurable fields only; reject interpolation expressions in fixed fields; validate the fully resolved configuration. Validate the structural shape of the optional `remote` section (required keys present, value types correct, unsupported backend identifiers rejected, remote runtime target requires a remote section) without checking whether individual store settings are complete or reachable — that check is deferred to operation time (T-031). Distinguish missing configuration (suggests initialization) from invalid configuration (identifies the offending setting and the source variable when interpolation is involved).
**Watchpoints:** Large task — refinement should produce acceptance criteria across all five distinct concerns: (1) parse, (2) required-field validation, (3) fixed-literal vs. interpolatable field distinction, (4) `${VAR:-default}` interpolation semantics, (5) structural remote-section shape. Operation-time remote completeness checks are deferred to T-044, not here.
**Requirements and References:** [FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration), [FR-CFG-003](02-product-requirements.md#fr-cfg-003--environment-variable-interpolation), [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation), [Configuration Loading Sequence](03-system-behavior.md#configuration-loading-sequence)

### T-013 — Runtime Target Override

**Status:** not started
**Goal:** Allow runtime target switching via environment variable.
**Description:** Check for a `KITEFS_RUNTIME_TARGET` environment variable. When set, it overrides the `runtime.target` field from config without modifying the file.
**Requirements and References:** [FR-CFG-002](02-product-requirements.md#fr-cfg-002--runtime-target-switching)

---

## P-6 — Provider Boundary and Local Provider

**Goal:** Storage abstraction exists with a working local implementation (BB-09).

### T-014 — Provider ABCs

**Status:** not started
**Goal:** Define `Provider`, `RegistryStore`, `OfflineStore`, `OnlineStore` abstract base classes.
**Description:** Create `src/kitefs/providers/base.py` with the three store interfaces and the `Provider` factory ABC. Core modules will depend on these interfaces only. No provider-specific imports here.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [NFR-MAINT-001](02-product-requirements.md#nfr-maint-001--modular-architecture), [Provider Abstraction Boundary](04-architecture.md#provider-abstraction-boundary)

### T-015 — Local RegistryStore

**Status:** not started
**Goal:** Implement the `RegistryStore` interface for the local provider, backed by a single JSON file.
**Description:** Provide whole-document read and overwrite of the registry artifact at the fixed local path `./feature_store/registry.json`. Serialization is deterministic so the file can be inspected and diffed per the storage contract. This is the only place that touches the local registry file on disk; higher-level registry logic in BB-04 calls this interface and never reads or writes the file directly.
**Watchpoints:** "Deterministic serialization" is a four-part spec in `docs/05-data-and-storage-contracts.md` — `sort_keys=True`, features sorted by name, join_keys sorted by name, trailing newline. `json.dumps` default order is not sufficient.
**Requirements and References:** [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact), [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [Registry JSON](05-data-and-storage-contracts.md#registry-json)

### T-016 — Local OfflineStore

**Status:** not started
**Goal:** Implement local offline storage with Parquet files and the prescribed partition layout.
**Description:** Write Parquet files under the managed directory with year/month partitioning and the documented file-naming convention (including the ingestion source prefix and short-id collision resolution). Reads support partition-scoped access. Writes are atomic (write-to-temp then rename) so that a failed write leaves no partial file visible.
**Watchpoints:** Reads must use `pyarrow.dataset` with `partitioning='hive'` and scanner filter pushdown — not manual filesystem walk or filename parsing. Partition path (year=/month=) is the only authoritative time signal; file-name timestamp is not used for filtering.
**Requirements and References:** [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes), [Offline Store Layout](05-data-and-storage-contracts.md)

### T-017 — Local OnlineStore

**Status:** not started
**Goal:** Implement local online storage with SQLite (one table per online-capable group).
**Description:** Create and manage SQLite tables for materialized online data per the documented schema. Support latest-per-entity upserts and key-based point lookups. Preserve prior committed state on write failure (no partial visibility).
**Watchpoints:** Write pattern is full-table replacement within one transaction (`BEGIN; DELETE FROM …; executemany INSERT …; COMMIT`) — not upsert. Set `journal_mode=WAL` and `busy_timeout=5000` on every connection open, not only at creation time.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-018 — Provider Factory Wiring

**Status:** not started
**Goal:** Wire the provider factory to return the local provider based on configuration.
**Description:** Build the `LocalProvider` bundle that returns the three local store implementations. Factory selects provider based on the resolved runtime target. AWS provider returns a not-implemented stub until P-12. Core modules receive only the interface types — never provider-specific clients.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [FR-CFG-002](02-product-requirements.md#fr-cfg-002--runtime-target-switching), [CON-007](02-product-requirements.md#con-007--local-and-aws-providers-only)

---

## P-7 — Registry Manager and First SDK Slice

**Goal:** `FeatureStore.apply`, `list_feature_groups`, and `describe_feature_group` work end-to-end on local (BB-04, BB-02).

**Demo outcome:** Users declare groups in Python, call `apply`, then list and describe them programmatically.

### T-019 — Definition Discovery

**Status:** not started
**Goal:** Automatically discover feature group objects from the definitions directory.
**Description:** Scan `./feature_store/definitions/` for Python modules. Collect all module-level `FeatureGroup` instances regardless of variable name. Files outside `definitions/` are not scanned. Report an actionable message when no definitions are found.
**Requirements and References:** [FR-REG-002](02-product-requirements.md#fr-reg-002--definition-discovery)

### T-020 — Cross-Definition Validation

**Status:** not started
**Goal:** Validate discovered definitions as a complete set before any registry write.
**Description:** Check for duplicate group names, invalid join references, join dtype mismatches between referencing and referenced join keys, and reserved field names (e.g. `year`, `month`). Collect all errors and report together in a single error before any registry write begins.
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation), [CON-009](02-product-requirements.md#con-009--identifier-naming-rules)

### T-021 — Registry Artifact Builder

**Status:** not started
**Goal:** Build the registry artifact from validated definitions.
**Description:** Produce a JSON-serializable registry structure per the storage contract. Preserve runtime-managed fields (notably `last_materialized_at`) for groups that survive regeneration. Update `applied_at` per registered group to the current UTC time on success.
**Watchpoints:** Output must be byte-deterministic per the Registry JSON contract (see T-015 watchpoint). Groups absent from the new definition set drop their registry entry entirely — no tombstoning.
**Requirements and References:** [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact), [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-022 — FeatureStore Construction and Public Surface

**Status:** not started
**Goal:** Implement `FeatureStore.__init__` and finalize the top-level package re-exports.
**Description:** Constructor treats the current working directory as the project root, follows the configuration loading sequence, and builds the provider. Raises `ConfigurationError` on missing or invalid configuration. Wire the public package surface (`from kitefs import FeatureStore, FeatureGroup, EntityKey, ...`) per the contracts doc.
**Requirements and References:** [FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration), [NFR-MAINT-001](02-product-requirements.md#nfr-maint-001--modular-architecture), [Public Package Surface](06-api-and-cli-contracts.md#public-package-surface)

### T-023 — FeatureStore.apply (Local)

**Status:** not started
**Goal:** Wire `FeatureStore.apply` for local-only registry generation.
**Description:** Orchestrate discovery → cross-validation → artifact build → local registry write. Return `ApplyResult`. A failure before registry writes begin leaves the registry unchanged. Publish mode is deferred to P-12.
**Watchpoints:** The atomicity invariant — any failure during discovery, cross-validation, or artifact build must leave the on-disk registry unchanged. Acceptance criteria must include a test scenario for each failure point.
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-024 — List and Describe Feature Groups

**Status:** not started
**Goal:** Implement `list_feature_groups` and `describe_feature_group` on the SDK.
**Description:** Read from the active registry. Return summaries or full descriptions including runtime-managed fields when present. Empty registry returns an empty list (not an error). Unknown group raises `FeatureGroupNotFoundError`. A missing or unreachable selected registry fails with an actionable error.
**Requirements and References:** [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe)

---

## P-8 — Local CLI Surface

**Goal:** End-to-end local producer workflow runs from the terminal (BB-01).

**Demo outcome:** Fresh machine quickstart — install → `kitefs init` → write a group → `kitefs apply` → `kitefs list`.

### T-025 — kitefs apply

**Status:** not started
**Goal:** Expose `apply` as a CLI subcommand.
**Description:** Call `FeatureStore.apply`. Wire the `--publish` and `--no-confirm` flags (actual remote write is deferred to P-12). Render `ApplyResult` as human-readable output.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations), [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-026 — kitefs list and kitefs describe

**Status:** not started
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
**Goal:** Implement append-only write coordination in the offline store manager (BB-06).
**Description:** Accept validated data, write through the `OfflineStore` interface with the ingestion source prefix and partition layout. Never modify or delete prior files. Multi-partition batch writes guarantee per-file atomicity.
**Requirements and References:** [FR-ING-002](02-product-requirements.md#fr-ing-002--append-only-writes), [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes)

### T-028 — FeatureStore.ingest

**Status:** not started
**Goal:** Wire SDK `ingest` for DataFrame input with shape checks and the ingestion validation gate.
**Description:** Verify the target group exists, check the input contains the entity key, event timestamp, join key, and declared feature fields, drop undeclared columns, apply the group's ingestion validation mode via the validation engine, then write through the offline store manager. Return `IngestResult` with row counts and the validation report (when produced).
**Watchpoints:** Five phases run in strict order with distinct error types: group lookup (`FeatureGroupNotFoundError`) → shape check (`IngestionShapeError`) → row-level structural checks (always-on, independent of mode) → feature checks (mode-driven, `ValidationError` with `error.report` in ERROR mode) → write. `IngestResult.written_files` carries absolute paths for local writes.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion), [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation), [CON-003](02-product-requirements.md#con-003--pandas-as-primary-dataframe)

### T-029 — File Input Support (CSV/Parquet)

**Status:** not started
**Goal:** Allow `FeatureStore.ingest` to accept a local `.csv` or `.parquet` file path in addition to a DataFrame.
**Description:** Detect format by file extension and load into a DataFrame inside the SDK, then follow the normal ingest flow. Reject unsupported extensions. File loading is the SDK's responsibility — the CLI passes the path directly without parsing.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion), [NFR-UX-001](02-product-requirements.md#nfr-ux-001--standard-python-interfaces)

### T-030 — kitefs ingest CLI

**Status:** not started
**Goal:** Expose ingestion as a CLI subcommand.
**Description:** Accept group name and file path arguments. Pass the path directly to the SDK `ingest`. Render result and any validation report to stdout/stderr.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations)

---

## P-10 — Historical Retrieval and Point-in-Time Joins

**Goal:** Training datasets retrievable with point-in-time correctness (read-path vertical slice).

**Demo outcome:** Users build a leak-free training set joining two feature groups.

### T-031 — Offline Store Manager Read Path

**Status:** not started
**Goal:** Implement offline reads with event-timestamp filtering and partition pruning.
**Description:** Read Parquet data through the `OfflineStore` interface. Apply partition-level pruning for year/month. Support timestamp comparison operators (`gt`, `gte`, `lt`, `lte`) on the event timestamp column.
**Watchpoints:** Use `pyarrow.dataset` with `partitioning='hive'` and scanner filter pushdown — do not enumerate files manually or parse filenames for filtering.
**Requirements and References:** [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval)

### T-032 — get_historical_features (Single Group)

**Status:** not started
**Goal:** Implement single-group historical retrieval with `select` and `where`.
**Description:** Validate request shape (group exists, `select` provided and fields valid, filters target the event timestamp column with supported operators) before any read. Read offline data with filters. Return a DataFrame containing the group's structural columns plus the selected feature fields.
**Requirements and References:** [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval), [NFR-UX-001](02-product-requirements.md#nfr-ux-001--standard-python-interfaces)

### T-033 — Join Engine

**Status:** not started
**Goal:** Implement point-in-time correct joins (BB-08).
**Description:** Stateless, no I/O. For each base row, find the most recent joined row with event timestamp ≤ base timestamp. Equality is eligible; rows with later timestamps are never selected. Ties resolve deterministically. Re-running against unchanged data returns the same rows in the same order. Unmatched base rows remain with null joined columns.
**Watchpoints:** Tie-break semantics (equal join-key + equal event timestamp) must use a pinned secondary sort key — refinement must define it explicitly so re-runs against unchanged data are provably identical, not just probably identical.
**Requirements and References:** [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins), [AP-6](04-architecture.md#architectural-design-principles)

### T-034 — get_historical_features (Joined)

**Status:** not started
**Goal:** Support one joined feature group in historical retrieval.
**Description:** Validate join shape (at most one joined group, registered join relationship exists, `select` dict shape valid) before any read. Read base and joined groups, apply the join engine, prefix joined columns with the joined group name; base columns remain unprefixed.
**Watchpoints:** `select` shape changes for the join path: `list[str] | "*"` for single-group, `dict[str, list[str] | "*"]` keyed by group name with join. Structural fields (entity key, event timestamp, join key) are always returned regardless of `select` — callers cannot exclude them.
**Requirements and References:** [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins)

### T-035 — Offline Retrieval Validation Gate

**Status:** not started
**Goal:** Apply validation to retrieved offline data per each group's retrieval mode.
**Description:** After reading data, apply the validation engine with the group's `offline_retrieval_validation` mode. For joined retrieval, validate the base group and the joined group independently per their respective modes.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes)

---

## P-11 — Materialization and Online Serving

**Goal:** Latest feature values served from the online store (serving-path vertical slice).

**Demo outcome:** Full local pipeline — apply → ingest → materialize → online retrieval.

### T-036 — Online Store Manager

**Status:** not started
**Goal:** Implement the online store manager for writes and reads (BB-07).
**Description:** Coordinate latest-per-entity materialization writes and key-based reads through the `OnlineStore` interface. Preserve prior committed online state on write failure. Surface the underlying error message for per-group failures.
**Watchpoints:** "Latest-per-entity" describes the _result_, not the write pattern. The SQLite implementation (T-017) uses full-table replacement — not upsert. On write failure the table state is whatever was last committed; no partial writes are visible.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-037 — FeatureStore.materialize (Named Group)

**Status:** not started
**Goal:** Materialize a single named online-eligible group.
**Description:** Validate the named group exists and is online-eligible; reject offline-only and unknown groups with actionable errors. Read latest-per-entity from offline, write to online. A group with no offline data is reported as skipped. Idempotent. Report a per-group outcome and update `last_materialized_at` in the local working registry on success.
**Watchpoints:** `last_materialized_at` is written to the _local_ working registry on success regardless of runtime target — it propagates to the remote registry only via a subsequent `apply --publish`. Write failures go into `MaterializeResult.failed`, not raised as exceptions.
**Requirements and References:** [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups)

### T-038 — FeatureStore.materialize (All Groups)

**Status:** not started
**Goal:** Materialize all online-eligible groups with per-group failure isolation.
**Description:** Silently exclude offline-only groups. Run materialization for each remaining group. Report per-group outcomes (succeeded, skipped, failed) through the same result shape as the named-group case. A per-group failure does not stop the run or roll back other groups.
**Watchpoints:** Offline-only groups are silently excluded from the run _and_ from the result — they do not appear in succeeded, skipped, or failed buckets. A per-group failure does not roll back already-completed groups.
**Requirements and References:** [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-039 — kitefs materialize CLI

**Status:** not started
**Goal:** Expose materialization as a CLI subcommand.
**Description:** Accept an optional group name. Call SDK `materialize`. Render per-group outcomes to stdout.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations)

### T-040 — FeatureStore.get_online_features

**Status:** not started
**Goal:** Implement single-entity online retrieval.
**Description:** Validate request shape (group exists and is online-eligible, `select` provided, `where` targets the entity key with a single `eq` operator, value is type-compatible). Return a dict on hit (structural fields plus selected features), empty dict on miss. No validation gate on online retrieval.
**Requirements and References:** [FR-ONL-002](02-product-requirements.md#fr-onl-002--single-entity-online-retrieval), [NFR-UX-001](02-product-requirements.md#nfr-ux-001--standard-python-interfaces)

---

## P-12 — Remote Registry and Publish

**Goal:** AWS packaging is introduced. Remote registry operations work. Users can publish and discover features from AWS.

**Demo outcome:** `apply --publish` writes to S3 → remote `list` and `describe` read from S3 → an `init-config` project can list and describe remote groups.

### T-041 — AWS Packaging Extra and Provider Stub

**Status:** not started
**Goal:** Introduce the `[aws]` optional install extra and the `providers/aws/` sub-package.
**Description:** Add the `[aws]` optional dependency group to `pyproject.toml` covering boto3 and any other AWS-only dependencies. Create the `providers/aws/` sub-package as the only place AWS clients may be imported. Replace the not-implemented AWS provider stub from T-018 with a real factory entry that resolves AWS implementations. Confirm `pip install kitefs` (without extras) still imports the base package cleanly without any AWS dependency available.
**Watchpoints:** Add a packaging-level integration test that `import kitefs` succeeds in a clean environment without the `[aws]` extra — verifies no top-level boto3 import path was accidentally introduced.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [CON-007](02-product-requirements.md#con-007--local-and-aws-providers-only), [Packaging Model](04-architecture.md#packaging-model)

### T-042 — AWS Credential Chain and Error Mapping

**Status:** not started
**Goal:** Rely on the standard AWS credential chain and map permission errors.
**Description:** Use the standard boto3 credential resolution (env vars, AWS config, IAM role). Map missing or insufficient credentials/permissions to actionable errors that identify the affected store. Never leak secret values.
**Requirements and References:** [FR-PROV-002](02-product-requirements.md#fr-prov-002--aws-credential-chain)

### T-043 — AWS RegistryStore

**Status:** not started
**Goal:** Implement AWS registry storage as a JSON object in S3.
**Description:** Read and overwrite the registry JSON at the configured S3 key (`s3://{bucket}/{s3_prefix}/registry.json`). Same interface as local.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact)

### T-044 — Per-Operation Remote Configuration Validation

**Status:** not started
**Goal:** Validate remote store availability before each operation that needs it.
**Description:** Before an operation touches a remote store, check that the required remote sub-section (registry, offline, or online) is present, fully configured, and internally valid. Fail with an actionable error that identifies the missing or invalid capability and the operation that triggered the check. This is the lazy validation counterpart to T-012's structural parse.
**Requirements and References:** [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation)

### T-045 — apply --publish End-to-End

**Status:** not started
**Goal:** Enable `apply --publish` to write local then remote registries with confirmation.
**Description:** Unless `--no-confirm` is passed, the CLI prompts for the exact confirmation word **before** the `./kitefs.yaml` check; any response other than the exact word aborts. On confirm: write the local registry, then write the remote registry. Handle partial failure (local succeeds, remote fails) so the local working registry may contain regenerated content while the remote remains stale, and the operation reports failure.
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation), [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations), [Project Root Discovery](03-system-behavior.md#project-root-discovery)

### T-046 — Remote List and Describe Verification

**Status:** not started
**Goal:** Verify list and describe work against the remote registry from both project types.
**Description:** Confirm that `list` and `describe` read from the S3 registry when the runtime target is remote. Confirm a project created by `init-config` can list and describe from the published registry without further setup.
**Requirements and References:** [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe), [FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization)

---

## P-13 — Remote Offline Store

**Goal:** Remote ingestion and historical retrieval produce equivalent results to local.

**Demo outcome:** Ingest to S3 → `get_historical_features` with PIT join returns the same results as the local provider.

### T-047 — AWS OfflineStore

**Status:** not started
**Goal:** Implement AWS offline storage with S3 Parquet via PyArrow and boto3.
**Description:** Same partition layout and file-naming convention as local. Atomic writes via S3 put semantics. Reads support partition-scoped access and event-timestamp filtering. Importable only from `providers/aws/` so the base package install does not require boto3.
**Requirements and References:** [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes)

### T-048 — Remote Offline End-to-End Verification

**Status:** not started
**Goal:** Verify ingestion and historical retrieval (single and joined) work against S3 and match local.
**Description:** Confirm `ingest` writes Parquet files to S3 in the same partition layout and naming as local, and that append-only semantics hold. Confirm `get_historical_features` with single-group and joined retrieval produces equivalent results on local and remote for the same logical data.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion), [FR-ING-002](02-product-requirements.md#fr-ing-002--append-only-writes), [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval), [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins)

---

## P-14 — Remote Online Store and Consumer Serving

**Goal:** Remote materialization and online serving work. A consumer project serves features from DynamoDB.

**Demo outcome:** Remote materialize → `get_online_features` from DynamoDB → consumer `init-config` project retrieves online features.

### T-049 — AWS OnlineStore

**Status:** not started
**Goal:** Implement AWS online storage with DynamoDB per-group tables.
**Description:** Create and manage per-group DynamoDB tables with the documented naming (`{dynamodb_table_prefix}{group_name}`). Support latest-per-entity upserts and key-based reads. Surface underlying errors for per-group failure isolation. Importable only from `providers/aws/`.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-050 — Remote Online End-to-End and Consumer Acceptance

**Status:** not started
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
