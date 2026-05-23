# Product Requirements

## Purpose

This file defines what KiteFS must do for MVP acceptance. Each requirement states an observable outcome and the conditions that confirm it.

## Owns

- Functional requirements (FR-XXX).
- Non-functional requirements (NFR-XXX).
- Constraints (CON-XXX).
- Acceptance criteria.
- Priority levels.

## Does Not Own

- Operation step-by-step behavior. See [03-system-behavior.md](03-system-behavior.md).
- Storage schemas and file layouts. See [05-data-and-storage-contracts.md](05-data-and-storage-contracts.md).
- SDK signatures and CLI syntax. See [06-api-and-cli-contracts.md](06-api-and-cli-contracts.md).

## Conventions

- **Must Have:** MVP cannot ship without this.
- **Should Have:** Valuable, but MVP can ship without it. Targeted post-MVP.
- **Could Have:** Nice to have. Considered only if time permits.
- Requirements describe _what_ is observable, not _how_ or _in what order_ the system achieves it.
- "Actionable error" means the message identifies the affected group, field, record, or setting when known, and tells the user what to do next. This applies to every user-facing failure in this document; individual requirements do not restate it.
- "UTC datetime" means timezone-naive values are accepted as UTC and timezone-aware values must be UTC; other zones are rejected. KiteFS does not convert between zones. This applies to every datetime in the MVP.

## Functional Requirements

### Definitions

#### FR-DEF-001 — Feature Group Definition as Code

- **Priority:** Must Have
- **Traces To:** G-1, PP-2

Users define feature groups in Python. A feature group has a name, storage target, exactly one entity key, exactly one event timestamp, at most one join key, at least one feature field, and optional metadata.

**Acceptance Criteria:**

- A feature group with the required fields can be declared through the public Python definition types.
- A definition missing the entity key, event timestamp, or all feature fields is rejected.
- A definition with more than one entity key, more than one event timestamp, or more than one join key is rejected.
- For MVP, only one join key is supported; a definition with more than one join key is rejected.
- Structural fields (entity key, event timestamp, join key) and feature fields are represented as distinct concepts.
- Metadata is optional, but when present, `description` and `owner` are required and non-empty.
- Metadata may contain optional `tags` which is a map of string keys to string values.

#### FR-DEF-002 — Field Type Definitions

- **Priority:** Must Have
- **Traces To:** G-1

Supported types are string, integer, float, and datetime types.

**Acceptance Criteria:**

- Entity key, join key, and feature fields require explicit type declarations.
- Entity keys must be `STRING` or `INTEGER`. Other types are rejected at definition time.
- Join keys must be `STRING` or `INTEGER`. Other types are rejected at definition time.
- Event timestamp fields must be `DATETIME`. An explicit non-`DATETIME` value is rejected at definition time.
- Feature fields must be `STRING`, `INTEGER`, `FLOAT`, or `DATETIME`.
- A missing field type declaration on an entity key, join key, or feature field is rejected at definition time.
- A declared type that is outside the supported set for that field role is rejected at definition time.

#### FR-DEF-003 — Storage Target

- **Priority:** Must Have
- **Traces To:** G-1, PP-3

A feature group is either offline-only or offline-and-online.

**Acceptance Criteria:**

- A feature group can be configured for offline-only or offline-and-online.
- An offline-only group cannot be materialized to the online store.

#### FR-DEF-004 — Feature Expectations

- **Priority:** Must Have
- **Traces To:** G-5, PP-7

Users attach business-level expectations to feature fields. Supported operators in MVP: `gt`, `gte`, `lt`, `lte`, `is_in` (allowed values), and `not_null`.

**Acceptance Criteria:**

- A feature field can declare zero or more of the supported operators.
- Structural fields do not accept expectations and are rejected if any are declared.

#### FR-DEF-005 — Per-Operation Validation Modes

- **Priority:** Must Have
- **Traces To:** G-5, PP-7

A feature group configures validation modes independently for ingestion and offline retrieval. Supported modes: `ERROR`, `FILTER`, `NONE`. Defaults: ingestion = `ERROR`, offline retrieval = `NONE`.

**Acceptance Criteria:**

- Ingestion and offline retrieval modes are configurable independently.
- Omitting a mode falls back to its default.
- Mode semantics are enforced by [FR-VAL-001](#fr-val-001--feature-data-validation).

### Registry

#### FR-REG-001 — Registry as Derived Artifact

- **Priority:** Must Have
- **Traces To:** G-1, PP-5, PP-6

KiteFS maintains a registry derived from source definitions. The registry is the input for discovery, retrieval, materialization, and serving. Source definitions stay the reviewed source of truth.

**Acceptance Criteria:**

- For each registered group, the registry holds its name, structural fields, feature fields, expectations, join key, storage target, metadata, validation modes, `applied_at`, and `last_materialized_at` when applicable.
- The registry file is human-inspectable as text.
- Manual edits to the registry are not required for any supported workflow.
- Project initialization adds a Git ignore rule for the local registry file while keeping source definitions trackable.

#### FR-REG-002 — Definition Discovery

- **Priority:** Must Have
- **Traces To:** G-1

KiteFS automatically discovers feature group definitions from a fixed project directory. No decorators, naming conventions, or registration calls are required.

**Acceptance Criteria:**

- Any feature group object in the definitions directory is discovered, regardless of variable name.
- Definitions outside the definitions directory are not part of the registry.

#### FR-REG-003 — Registry Generation

- **Priority:** Must Have
- **Traces To:** G-1, PP-6

KiteFS regenerates the registry from current source definitions through `apply` command.

**Acceptance Criteria:**

- Registry generation fails when no definitions are discovered, with an actionable message that suggests declaring groups.
- Registry generation validates all discovered definitions as one set before writing any registry.
- Definition validation reports all discovered errors together before any registry write.
- A failure before registry writes begin leaves all registries unchanged.
- If `apply --publish` fails while writing the remote registry after the local write succeeds, the operation fails and the local working registry may already contain the regenerated content.
- On success, runtime-managed fields like `last_materialized_at` are preserved for groups that still exist.
- On success, `applied_at` is updated per registered group to the current UTC time. This is sufficient for MVP scope.
- Plain `apply` never writes the remote registry, regardless of runtime target.
- `apply --publish` requires a configured remote registry location.
- `apply --publish` requires explicit user confirmation before any work starts, unless `--no-confirm` is passed. Any response other than the exact confirmation word aborts the command.

#### FR-REG-004 — Registry Discovery (List and Describe)

- **Priority:** Must Have
- **Traces To:** PP-5

Users list registered feature groups and describe individual feature groups from the registry selected by the current runtime target.

**Acceptance Criteria:**

- Listing returns each registered group with a summary including its name and key metadata.
- Listing an empty registry returns an empty result, not an error.
- Describing a registered group returns its full registry entry, including runtime-managed fields when present.
- Describing an unknown group fails with an actionable error.
- List and describe read from the registry selected by the current runtime target.
- If the selected registry is missing, unreachable, or not configured, list and describe fail with an actionable error.

The **registry artifact** is the registry file (`local`) or registry object (`remote`) at the location selected by `runtime.target`. Downstream documents may use this term to refer to either backing form.

#### FR-REG-005 — Remote Registry Pull

- **Priority:** Should Have
- **Traces To:** PP-5

Users pull a configured remote registry into the local working environment.

**Acceptance Criteria:**

- Pull reads from the configured remote registry location and overwrites the local working registry.
- Pull fails when the remote registry is not configured or unreachable.

### Ingestion

#### FR-ING-001 — Offline Ingestion

- **Priority:** Must Have
- **Traces To:** G-1, G-3, G-4

Users ingest prepared feature data into the offline store for a registered feature group.

**Acceptance Criteria:**

- Ingestion checks that the target feature group exists and the input contains the entity key, event timestamp, join key, and declared feature fields.
- Missing groups or required columns fail before row validation or writes, with an actionable error that identifies the missing group or column.
- Input shape checks do not evaluate row-level nulls, type compatibility, or feature expectations.
- Ingestion writes only the entity key, event timestamp, join key, and declared feature fields from the input. Undeclared columns are not written.
- Written ingested files use the ingestion source prefix.
- Row-level validation behavior is defined in [FR-VAL-001](#fr-val-001--feature-data-validation).

#### FR-ING-002 — Append-Only Writes

- **Priority:** Must Have
- **Traces To:** G-1

Ingestion never modifies or deletes prior offline data. Each successful ingestion adds new files.

**Acceptance Criteria:**

- Existing offline files are unchanged after a successful ingestion.
- Offline files use the partition layout and naming convention from the storage contracts.

### Offline Store and Historical Retrieval

#### FR-OFF-001 — Offline Storage Backend

- **Priority:** Must Have
- **Traces To:** G-3, G-4

Offline data is stored as Parquet — on the local filesystem for the local runtime target, and on AWS S3 for the remote runtime target. The SDK retrieval interface is identical for both targets.

**Acceptance Criteria:**

- Identical SDK calls produce equivalent results against either runtime target for the same logical data.

#### FR-OFF-002 — Historical Feature Retrieval

- **Priority:** Must Have
- **Traces To:** G-2, PP-1

Users retrieve historical features from one base feature group. The caller must specify which feature fields to retrieve. The result always contains the group's structural columns plus the selected feature fields.

**Acceptance Criteria:**

- A `select` specification is required; a missing `select` is rejected.
- Returned columns use the registered field names.
- Retrieval checks that the base feature group, selected feature fields, event timestamp filters, and requested join shape are valid before reading offline data or validating row values.
- Missing groups, unknown selected feature fields, unsupported filters, or invalid join shape fail with an actionable error before reading data.
- Request shape checks do not evaluate row-level nulls, type compatibility, or feature expectations.
- Retrieval supports filtering on the base group's event timestamp column with supported comparison operators.
- Filters on any other column or with unsupported operators are rejected.
- Row-level validation behavior is defined in [FR-VAL-001](#fr-val-001--feature-data-validation).

#### FR-OFF-003 — Point-in-Time Correct Joins

- **Priority:** Must Have
- **Traces To:** G-2, PP-1, PP-4

Historical retrieval supports joining one additional feature group via its registered join key. For each base row, KiteFS joins the most recent row from the joined group whose event timestamp is at or before the base row's event timestamp.

**Acceptance Criteria:**

- A joined row with an event timestamp after the base row's event timestamp is never selected.
- A joined row with an event timestamp equal to the base row's event timestamp is eligible.
- When several joined rows are eligible, the latest one wins, and ties resolve deterministically.
- Re-running the same query against unchanged data returns the same rows in the same order.
- A base row with no eligible joined match remains in the result; its joined columns are null.
- The MVP supports at most one joined feature group per request; requesting more is rejected.
- Joined output columns are prefixed with the joined feature group name; base output columns are unprefixed.
- A request to join a group with no registered join relationship from the base is rejected.
- Joined retrieval applies request shape checks before reading offline data, then applies row-level validation independently to the base group and joined group according to each group's offline retrieval validation mode.

### Materialization

#### FR-MAT-001 — Materialize Online-Eligible Groups

- **Priority:** Must Have
- **Traces To:** G-1, PP-3

Users explicitly trigger materialization for one named online-eligible group or for all online-eligible groups. Materialization writes the latest record per entity key (by event timestamp) from the offline store into the online store including all structural fields and all feature fields.

**Acceptance Criteria:**

_Request validation:_

- Materialization of a named offline-only group is rejected with an actionable error.
- A named group that does not exist in the registry is rejected with an actionable error.
- An all-groups run silently excludes offline-only groups from the target set.

_Operational outcomes (returned in the result):_

- Both named-group and all-groups runs report per-group outcomes (succeeded, skipped, failed) through the same result shape.
- A group with no offline data is reported as skipped; its existing online state is preserved.
- A per-group write failure reports the affected group as failed and does not update `last_materialized_at` for that group.
- In an all-groups run, a per-group failure does not roll back other successfully materialized groups and does not stop the run.
- Re-running materialization for a failed group is the supported repair action.
- A successful run updates `last_materialized_at` for each materialized group.
- `last_materialized_at` is written to the **local working registry** in both runtime targets. Propagation to the remote registry requires a subsequent `apply --publish`, consistent with [FR-REG-003](#fr-reg-003--registry-generation); until then the remote value is stale.

_General:_

- After successful materialization, the online store holds at most one row per entity key — the row with the latest event timestamp from the offline data.
- When two offline rows for the same entity key share the same event timestamp, the later-ingested row wins. "Later-ingested" is determined by the offline partition's ingest sequence (file write order).
- Re-running materialization against unchanged offline data produces the same online state (idempotent).
- Materialization never runs automatically; it is only triggered by an explicit SDK or CLI call.

### Online Store and Serving

#### FR-ONL-001 — Online Storage Backend

- **Priority:** Must Have
- **Traces To:** G-3, G-4

Online data is stored in SQLite for the local runtime target and AWS DynamoDB for the remote runtime target. The SDK retrieval interface is identical for both targets.

**Acceptance Criteria:**

- Identical SDK calls produce equivalent results against either runtime target for the same successfully materialized logical data.
- Materialization failure handling follows [NFR-REL-002](#nfr-rel-002--online-materialization-failure-handling).

#### FR-ONL-002 — Single-Entity Online Retrieval

- **Priority:** Must Have
- **Traces To:** G-1, PP-3

Users retrieve the latest stored feature values for one entity key.

**Acceptance Criteria:**

- A `select` specification is required and follows the same shape as offline retrieval.
- A hit returns all structural fields plus the requested feature fields.
- A miss returns an empty result (no rows), not an error.
- A group with no online row for the requested entity key returns an empty result, including before the group's first successful materialization.
- Retrieval from an offline-only group or with an unknown feature field is rejected with an actionable error.
- The `where` filter must target the group's registered entity key with a single equality match; any other field, operator, or multi-value filter is rejected with an actionable error.
- The value must be a single literal type-compatible with the entity key dtype; type-incompatible values are rejected with an actionable error.
- Online retrieval does not run row-level validation.

#### FR-ONL-003 — Batch Online Retrieval

- **Priority:** Could Have
- **Traces To:** PP-3

Online retrieval accepts multiple entity keys in one request, preserves input order in the result, and represents misses distinctly from hits. Single-key retrieval remains supported unchanged.

### Validation

#### FR-VAL-001 — Data Validation

- **Priority:** Must Have
- **Traces To:** G-5, PP-7

KiteFS validates row values at configured validation gates. Two classes of checks apply:

- **Structural checks** (always enforced, all modes): each row's entity key, event timestamp, and join key must be present, type-compatible with the declaration, and — for datetimes — UTC.
- **Feature checks** (mode-controlled): each feature field value is checked against its declared type and any declared expectations.

The active mode for an operation determines how feature-check failures are handled:

| Mode     | Effect on feature-check failures                                                                                                                              |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ERROR`  | The operation is rejected. No rows are written or returned. A validation report is provided.                                                                  |
| `FILTER` | Failing rows are excluded; passing rows continue. If no rows pass, an empty result is produced and reported. The report identifies excluded rows and reasons. |
| `NONE`   | Feature checks are skipped. Structural checks still apply. No report is produced.                                                                             |

**Acceptance Criteria:**

- Structural-check failures reject the operation in every mode, regardless of which validation gate is being applied.
- Feature-check behavior follows the table above for each of the three modes.
- The validation report (when produced) includes summary counts and per-failure details sufficient to identify which rows and fields failed and why.
- Ingestion applies validation per [FR-DEF-005](#fr-def-005--per-operation-validation-modes) ingestion mode; offline retrieval applies validation per offline retrieval mode.
- Materialization and online retrieval do not run data validation.

### Provider Abstraction

#### FR-PROV-001 — Provider Boundary

- **Priority:** Must Have
- **Traces To:** G-3, G-4, NG-4

All offline, online, and registry storage operations cross a single provider boundary. Adding a new provider requires implementing this boundary; it does not require changes to core logic, SDK methods, CLI commands, or feature definition types.

**Acceptance Criteria:**

- Core logic does not depend on provider-specific storage libraries directly.
- The MVP ships a local provider (filesystem + SQLite) and an AWS provider (S3 + DynamoDB).
- A new provider can be added by implementing only the provider interface.

#### FR-PROV-002 — AWS Credential Chain

- **Priority:** Must Have
- **Traces To:** G-4

The AWS provider relies on the standard AWS credential resolution chain (environment variables, AWS config, IAM role). KiteFS does not store or manage credentials.

**Acceptance Criteria:**

- AWS access succeeds with any standard credential source supported by the AWS SDK.
- Missing or insufficient credentials or permissions produce an actionable error that identifies the affected store and does not leak secret values.

### Configuration

#### FR-CFG-001 — Project Configuration

- **Priority:** Must Have
- **Traces To:** G-3, G-4

Project behavior is driven by a single configuration file. Required fields: configuration version, project name, and runtime target. A `remote` runtime target requires a `remote` section, but individual remote store settings are validated only when an operation needs them. Consumer-only projects may configure a remote registry and online store without a remote offline store. Local storage uses fixed conventions; configuring local paths is not supported. The MVP supports a single fixed remote backend per store type; alternative backends are not supported.

**Acceptance Criteria:**

- A configuration missing any required project-level field is rejected at startup with an error that identifies the missing field.
- A configuration with a remote runtime target and no remote section is rejected at startup.
- A remote configuration without an offline store is valid for online-only consumer workflows.
- A remote store block with an unsupported backend type is rejected with an actionable error that identifies the affected setting.
- Remote online-store configuration supports provider-managed table namespacing.
- Remote offline-store configuration supports a configurable bucket name for registry and offline store locations.
- When the runtime target is remote, any runtime operation that requires related remote configuration fails clearly when that configuration is missing or invalid.
- An invalid existing configuration during runtime operations is rejected without suggesting project initialization.
- A missing configuration file is rejected with a message that suggests initialization.

#### FR-CFG-002 — Runtime Target Switching

- **Priority:** Must Have
- **Traces To:** G-3, G-4

Switching between local and remote runtime targets is a configuration change only. SDK and CLI usage code does not change.

**Acceptance Criteria:**

- The same SDK code produces equivalent results against either runtime target for the same logical data.
- The runtime target can be overridden by environment variable without modifying the configuration file.

#### FR-CFG-003 — Environment Variable Interpolation

- **Priority:** Must Have
- **Traces To:** G-4

Configuration values support environment variable interpolation with default fallbacks. Interpolation applies only to fields documented as configurable values. Fixed fields such as remote store backend types are literal values and are not subject to interpolation.

**Acceptance Criteria:**

- When the environment variable is set, its value replaces the interpolation expression.
- When the environment variable is unset, the declared default is used.
- An interpolated value that fails configuration validation produces an error that identifies the source variable.
- A fixed field containing an interpolation expression is rejected as an invalid value.

#### FR-CFG-004 — Per-Operation Configuration Validation

- **Priority:** Must Have
- **Traces To:** G-3

Beyond startup validation, each operation validates that the stores and settings it needs are available before doing work.

**Acceptance Criteria:**

- An operation requiring the offline store fails clearly when the offline store is missing or misconfigured.
- An operation requiring the online store fails clearly when the online store is missing or misconfigured.
- Per-operation failures identify the missing capability and suggest a resolution.

### CLI

#### FR-CLI-001 — Installed CLI Entry Point

- **Priority:** Must Have
- **Traces To:** G-3

Installing the package exposes a CLI command. The CLI runs without requiring users to import KiteFS in Python.

**Acceptance Criteria:**

- The CLI command is available in the active environment after `pip install`.
- Running the CLI with no subcommand prints help and a non-zero exit code.
- Every subcommand has a `--help` flag and rejects invalid input before doing any work.
- Failures show actionable messages without raw stack traces for normal user errors.

#### FR-CLI-002 — Required CLI Operations

- **Priority:** Must Have
- **Traces To:** G-3, PP-5

The MVP CLI surface is the set of subcommands listed below. SDK operations not listed here are SDK-only in the MVP unless a later requirement adds CLI coverage, with one exception: `pull` ([FR-REG-005](#fr-reg-005--remote-registry-pull)) is **post-MVP for both SDK and CLI** and is not part of the MVP surface in either form. When a listed subcommand maps to an SDK operation, it produces the same observable outcome and does not define separate behavior.

| CLI Subcommand | Maps To                                                                                          |
| -------------- | ------------------------------------------------------------------------------------------------ |
| `init`         | Producer project initialization (see [FR-CLI-003](#fr-cli-003--project-initialization))          |
| `init-config`  | Consumer project initialization (see [FR-CLI-003](#fr-cli-003--project-initialization))          |
| `apply`        | [FR-REG-003](#fr-reg-003--registry-generation) (local generation; publish mode with `--publish`) |
| `list`         | [FR-REG-004](#fr-reg-004--registry-discovery-list-and-describe) (list)                           |
| `describe`     | [FR-REG-004](#fr-reg-004--registry-discovery-list-and-describe) (describe)                       |
| `ingest`       | [FR-ING-001](#fr-ing-001--offline-ingestion) (CSV/Parquet only)                                  |
| `materialize`  | [FR-MAT-001](#fr-mat-001--materialize-online-eligible-groups)                                    |

**Acceptance Criteria:**

- Each subcommand listed above is available and produces the same observable outcome as its referenced SDK operation.
- `apply --publish` prompts for exact `yes` unless `--no-confirm` is passed.
- `list` and `describe` support human-readable output (default), JSON output, and writing to a file path.

#### FR-CLI-003 — Project Initialization

- **Priority:** Must Have
- **Traces To:** G-3, G-4, PP-8

The CLI provides two initialization modes: a producer mode that creates the full project scaffold, and a consumer mode that creates configuration only.

**Acceptance Criteria:**

- Both commands abort without changes when a project configuration file already exists.
- Neither generated configuration file contains local store path fields.
- A project created by consumer initialization can list and describe feature groups from a configured remote registry, and can perform online retrieval against a configured remote online store, without further setup.

### Post-MVP Capabilities

The following are explicitly out of MVP scope and tracked here so the surrounding requirements remain consistent.

#### FR-MOCK-001 — Mock Data Generation

- **Priority:** Should Have
- **Traces To:** G-6, PP-8

KiteFS generates synthetic feature data for a registered feature group on the local runtime target only. Generated rows satisfy declared types and expectations, cover a configurable event-timestamp range, and are written to the local offline store readable by standard retrieval.

#### FR-SAM-001 — Smart Sampling

- **Priority:** Should Have
- **Traces To:** G-7, PP-8

KiteFS pulls a subset of remote offline data into the local offline store on the local runtime target only. Sampling supports selection by row count, percentage, or event-timestamp range. Sampled data preserves feature group structure and is queryable through standard historical retrieval.

#### FR-MAT-002 — Incremental Materialization

- **Priority:** Could Have
- **Traces To:** G-1

Materialization accepts an event-timestamp range. Only offline rows in range are considered, and the online store still holds at most one latest row per entity key after the run.

## Non-Functional Requirements

### NFR-REL-001 — Atomic Offline File Writes

- **Priority:** Must Have

A successful offline file write produces a complete, readable file. A failed write leaves no partial file visible.

**Acceptance Criteria:**

- A failed offline write leaves no partial file in the target location, regardless of runtime target.
- Multi-partition batch writes guarantee per-file atomicity, not batch-level rollback: completed files may remain after a partial batch failure, but no incomplete file is exposed as if it succeeded.

### NFR-REL-002 — Online Materialization Failure Handling

- **Priority:** Must Have

Online materialization failures must be visible and repairable.

**Acceptance Criteria:**

- A failed materialization keeps the group's prior committed online state visible (or unmaterialized if no prior state exists).
- A failed materialization does not update `last_materialized_at`; the prior value remains the last fully successful materialization marker.
- A failed materialization surfaces the underlying error message through the per-group outcome reported to the caller.
- Re-running materialization for the same group is the supported repair action. A successful rerun overwrites the group's online data with the latest rows from offline storage.

### NFR-UX-001 — Standard Python Interfaces

- **Priority:** Must Have

The SDK uses standard Python types for data exchange. No custom KiteFS container types are required for basic usage.

**Acceptance Criteria:**

- Batch data exchange (ingestion, historical retrieval) uses Pandas DataFrames.
- Single-record retrieval uses standard Python types (dict/list).
- Basic usage does not require importing or constructing custom KiteFS container types.

### NFR-MAINT-001 — Modular Architecture

- **Priority:** Must Have

Core feature-store logic, provider interface, provider implementations, SDK entry points, and CLI entry points are kept as separate concerns.

**Acceptance Criteria:**

- Core logic depends on the provider interface only — not on any concrete provider.
- CLI handlers do not implement domain logic; they call SDK functions.
- Provider implementations do not import SDK or CLI entry points.
- There are no circular dependencies between core, providers, SDK, and CLI.

## Constraints

### CON-001 — Python 3.12+

KiteFS targets Python 3.12 or higher. Package metadata declares this; installation or runtime on lower versions fails clearly.

### CON-002 — Pip-Installable Library

KiteFS is distributed as a single pip-installable package. Local workflows require no companion service, daemon, cloud credentials, container, or external database.

### CON-003 — Pandas as Primary DataFrame

Pandas is the primary DataFrame interface for ingestion and historical retrieval. Other DataFrame libraries are out of MVP scope; users convert in their own code if needed.

### CON-004 — Single Entity Key

A feature group has exactly one entity key. Composite keys are out of MVP scope.

### CON-005 — No Server or Daemon

KiteFS runs only as SDK calls or CLI invocations. No long-lived service is started by installation, initialization, or any operation. Materialization is user-triggered, never daemon-triggered.

### CON-006 — UTC-Only Datetimes

All datetimes in the MVP are UTC. KiteFS does not convert between time zones. Non-UTC timezone-aware values are rejected.

### CON-007 — Local and AWS Providers Only

MVP providers are local (filesystem + SQLite) and AWS (S3 + DynamoDB). Other cloud providers are out of MVP scope, but the provider boundary in [FR-PROV-001](#fr-prov-001--provider-boundary) permits adding them later.

### CON-008 — Out of Scope for MVP

The MVP excludes: streaming ingestion, web UI, drift detection, statistical monitoring, model hosting or serving, and custom authentication or authorization. Cloud access control relies on the cloud provider's mechanisms.

### CON-009 — Identifier Naming Rules

Feature group names, entity key names, event timestamp names, join key names, and feature field names must match `^[a-zA-Z_][a-zA-Z0-9_]*$`. This ensures names are safe as SQL identifiers, DynamoDB attribute names, Parquet column names, and filesystem path segments without escaping.
