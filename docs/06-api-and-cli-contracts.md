# API and CLI Contracts

## Purpose

This file defines every user-facing and internal interface contract. It owns public Python imports, SDK method signatures, CLI commands, the exception hierarchy, and internal module interfaces — including the provider boundary ABCs.

## Owns

- Public Python imports exposed from the `kitefs` package.
- SDK method signatures, parameters, and return types on `FeatureStore`.
- CLI command syntax, options, exit codes, and output formats.
- Public exception hierarchy and inheritance.
- Internal provider interface ABCs (`Provider`, `RegistryStore`, `OfflineStore`, `OnlineStore`).
- Public definition types and their constructor contracts.

## Does Not Own

- Operation step-by-step behavior. See [03-system-behavior.md](03-system-behavior.md).
- Storage formats, schemas, file layouts, partition rules, and type mapping. See [05-data-and-storage-contracts.md](05-data-and-storage-contracts.md).
- Architectural building blocks and dependency direction. See [04-architecture.md](04-architecture.md).
- Acceptance criteria. See [02-product-requirements.md](02-product-requirements.md).

## Conventions

- All signatures target Python 3.12+ and use [PEP 604](https://peps.python.org/pep-0604/) union syntax (`X | None` rather than `Optional[X]`).
- Datetime parameters and return values are `datetime.datetime`. The UTC rule in [CON-006](02-product-requirements.md#con-006--utc-only-datetimes) applies to every datetime crossing the API.
- DataFrame parameters and returns are `pandas.DataFrame`.
- All public methods raise exceptions from the [Exception Hierarchy](#exception-hierarchy). Internal modules raise the same hierarchy; they do not invent their own exception types.
- Method parameters listed as keyword-only follow a `*` separator in the signature.
- Return-type annotations use concrete classes from the public surface. Dataclass and `TypedDict` shapes used as return values are defined in [Return Types](#return-types).
- "Actionable error" follows [02-product-requirements.md - Conventions](02-product-requirements.md#conventions): every raised exception identifies the affected group, field, record, or setting when known, and indicates the next step.

---

## Public Package Surface

The `kitefs` package exports a small, stable surface. Everything below is importable as `from kitefs import <name>`.

### Entry Point

| Name           | Kind  | Purpose                                              |
| -------------- | ----- | ---------------------------------------------------- |
| `FeatureStore` | class | SDK entry point. Orchestrates all user-facing flows. |

### Definition Types

| Name             | Kind  | Purpose                                                        |
| ---------------- | ----- | -------------------------------------------------------------- |
| `FeatureGroup`   | class | Declarative feature group definition.                          |
| `EntityKey`      | class | Entity-key field declaration.                                  |
| `EventTimestamp` | class | Event-timestamp field declaration.                             |
| `Feature`        | class | Feature field declaration with type and optional expectations. |
| `JoinKey`        | class | Join-key field declaration referencing another feature group.  |
| `Metadata`       | class | Optional feature group metadata (description, owner, tags).    |
| `Expect`         | class | Fluent builder for feature expectations.                       |

### Enums

| Name             | Values                                   | Purpose                        |
| ---------------- | ---------------------------------------- | ------------------------------ |
| `FeatureType`    | `STRING`, `INTEGER`, `FLOAT`, `DATETIME` | Supported field types.         |
| `StorageTarget`  | `OFFLINE`, `OFFLINE_AND_ONLINE`          | Per-group storage target.      |
| `ValidationMode` | `ERROR`, `FILTER`, `NONE`                | Per-operation validation mode. |

### Return Type Classes

All return-type dataclasses are defined and listed in [Return Types](#return-types). They are re-exported from the top-level package.

### Exceptions

The full hierarchy is defined in [Exception Hierarchy](#exception-hierarchy). All public exception classes are re-exported from the top-level package.

### Versioning

The package exposes `kitefs.__version__` as a string following [Semantic Versioning](https://semver.org/). The MVP ships as `0.x.y` — the public surface above is stable within `0.x`, but pre-1.0 means breaking changes can occur on minor bumps with release-note callouts.

---

## Definition Types

These constructors are the source-of-truth shape for feature definitions. Field validation occurs at construction time so authoring errors fail fast in the user's editor or REPL.

### `FeatureGroup`

```python
class FeatureGroup:
    def __init__(
        self,
        *,
        name: str,
        storage_target: StorageTarget,
        entity_key: EntityKey,
        event_timestamp: EventTimestamp,
        features: list[Feature],
        join_keys: list[JoinKey] | None = None,
        ingestion_validation: ValidationMode = ValidationMode.ERROR,
        offline_retrieval_validation: ValidationMode = ValidationMode.NONE,
        metadata: Metadata | None = None,
    ) -> None: ...
```

**Construction-time checks:**

- `name` matches [CON-009](02-product-requirements.md#con-009--identifier-naming-rules).
- `features` is non-empty.
- `join_keys` is `None`, empty, or a single-element list (MVP single join, [FR-DEF-001](02-product-requirements.md#fr-def-001--feature-group-definition-as-code)).
- `event_timestamp.dtype` resolves to `FeatureType.DATETIME` (always true when the default is used; an explicit non-`DATETIME` value is already rejected by `EventTimestamp`).
- All field names within the group are unique across structural and feature fields.
- All field names match [CON-009](02-product-requirements.md#con-009--identifier-naming-rules).

Any violation raises `DefinitionError`. Cross-group validation (duplicate group names, join references) runs later during `apply` ([FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)).

### `EntityKey`

```python
class EntityKey:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType,
        description: str | None = None,
    ) -> None: ...
```

`dtype` must be `STRING` or `INTEGER` ([FR-DEF-002](02-product-requirements.md#fr-def-002--field-type-definitions)). Otherwise raises `DefinitionError`.

### `EventTimestamp`

```python
class EventTimestamp:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType = FeatureType.DATETIME,
        description: str | None = None,
    ) -> None: ...
```

`dtype` defaults to `FeatureType.DATETIME` and may be omitted. The event timestamp type is always `DATETIME`; passing any other value raises `DefinitionError`.

### `Feature`

```python
class Feature:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType,
        description: str | None = None,
        expect: Expect | None = None,
    ) -> None: ...
```

`dtype` must be one of `STRING`, `INTEGER`, `FLOAT`, `DATETIME`. `expect` is `None` when no expectations are declared.

### `JoinKey`

```python
class JoinKey:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType,
        referenced_group: str,
        description: str | None = None,
    ) -> None: ...
```

`dtype` must be `STRING` or `INTEGER`. `referenced_group` is the target feature group's `name`; existence and entity-key compatibility are checked during `apply`.

### `Metadata`

```python
class Metadata:
    def __init__(
        self,
        *,
        description: str,
        owner: str,
        tags: dict[str, str] | None = None,
    ) -> None: ...
```

When `metadata` is supplied on a `FeatureGroup`, both `description` and `owner` must be non-empty strings ([FR-DEF-001](02-product-requirements.md#fr-def-001--feature-group-definition-as-code)). `tags` defaults to an empty dict.

### `Expect`

`Expect` is a fluent builder. Each operator method returns the same instance and appends a constraint, so users can chain calls in any order.

```python
class Expect:
    def __init__(self) -> None: ...

    def not_null(self) -> "Expect": ...
    def gt(self, value: int | float) -> "Expect": ...
    def gte(self, value: int | float) -> "Expect": ...
    def lt(self, value: int | float) -> "Expect": ...
    def lte(self, value: int | float) -> "Expect": ...
    def is_in(self, values: list[str | int | float]) -> "Expect": ...
```

Operator argument types are validated at call time. Numeric operators reject non-numeric arguments; `is_in` requires a non-empty list. Violations raise `DefinitionError`.

---

## SDK: `FeatureStore`

`FeatureStore` is the single public orchestrator. One instance per process is the expected usage; constructing it loads configuration, builds the provider, and resolves the active runtime target.

### Construction

```python
class FeatureStore:
    def __init__(self) -> None: ...
```

- The constructor uses the current working directory as the project root. See [Project Root Discovery](03-system-behavior.md#project-root-discovery).
- The constructor reads and validates `./kitefs.yaml` per [Configuration Loading Sequence](03-system-behavior.md#configuration-loading-sequence).
- Raises `ConfigurationError` for missing or invalid configuration.

### Methods Overview

| Method                    | Returns                     | Maps To                                                                                                                                                              |
| ------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apply`                   | `ApplyResult`               | [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)                                                                                             |
| `pull`                    | `PullResult`                | [FR-REG-005](02-product-requirements.md#fr-reg-005--remote-registry-pull) _(post-MVP)_                                                                               |
| `list_feature_groups`     | `list[FeatureGroupSummary]` | [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe)                                                                            |
| `describe_feature_group`  | `FeatureGroupDescription`   | [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe)                                                                            |
| `ingest`                  | `IngestResult`              | [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion)                                                                                               |
| `get_historical_features` | `pandas.DataFrame`          | [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval) + [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins) |
| `materialize`             | `MaterializeResult`         | [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups)                                                                              |
| `get_online_features`     | `dict[str, Any]`            | [FR-ONL-002](02-product-requirements.md#fr-onl-002--single-entity-online-retrieval)                                                                                  |

### `apply`

```python
def apply(self, *, publish: bool = False) -> ApplyResult: ...
```

- `publish=False` regenerates and writes the local working registry only.
- `publish=True` writes both local and remote registry as a full overwrite ([FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)).
- Interactive confirmation is a CLI-only concern. The SDK does not prompt; callers in non-interactive contexts pass `publish=True` directly.
- Raises `DefinitionDiscoveryError` when no definitions are discovered.
- Raises `DefinitionValidationError` (aggregating all errors) when any definition is invalid.
- Raises `RegistryWriteError` when a registry write fails after validation passes.

**Cross-definition validation taxonomy:**

`apply` validates the full set of discovered definitions together before writing any registry. The following conditions are rejected and aggregated into a single `DefinitionValidationError`:

- Invalid field definitions (already caught at construction time by `DefinitionError`, but re-validated here for safety).
- Missing required structural fields (entity key, event timestamp).
- Non-`DATETIME` event timestamp fields.
- Duplicate feature group names across the discovered set.
- Duplicate field names within a single group (across structural and feature fields).
- Field names that collide with reserved offline-store partition columns (see [05 › Offline Store Parquet Layout › Partition Strategy](05-data-and-storage-contracts.md#partition-strategy)). In the MVP these are `year` and `month`.
- Field or group names violating [CON-009](02-product-requirements.md#con-009--identifier-naming-rules).
- Invalid join declarations (e.g., more than one join key in MVP).
- Missing referenced groups (a join key's `referenced_group` does not exist in the discovered set).
- Incompatible join metadata (join key dtype does not match the referenced group's entity key dtype).

All discovered errors are collected and reported together before any registry write. Duplicate-name failures identify the conflicting group name.

### `pull` _(post-MVP)_

```python
def pull(self) -> PullResult: ...
```

Overwrites the local working registry with the remote registry contents. Raises `ConfigurationError` if the remote registry is not configured, and `RegistryReadError` if the remote registry does not exist or cannot be read.

### `list_feature_groups`

```python
def list_feature_groups(self) -> list[FeatureGroupSummary]: ...
```

Returns one summary per registered group. An empty registry returns an empty list — not an error. Reads from the registry of the active runtime target ([FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe)). Raises `RegistryReadError` if the selected registry artifact is missing or unreachable.

### `describe_feature_group`

```python
def describe_feature_group(self, name: str) -> FeatureGroupDescription: ...
```

Returns the full registry entry for `name`. Raises `FeatureGroupNotFoundError` if the group is not registered. Raises `RegistryReadError` if the selected registry artifact is missing or unreachable.

### `ingest`

```python
def ingest(
    self,
    feature_group: str,
    data: pandas.DataFrame | str | os.PathLike[str],
) -> IngestResult: ...
```

- `data` is a Pandas DataFrame or a path to a local CSV or Parquet file. File-format detection is by extension: `.csv` and `.parquet` are supported.
- Returns an `IngestResult` with row counts and an optional validation report.
- Raises `FeatureGroupNotFoundError`, `IngestionShapeError`, `ValidationError`, or `OfflineStoreWriteError` per [03-system-behavior.md#ingest](03-system-behavior.md#ingest).

### `get_historical_features`

```python
def get_historical_features(
    self,
    *,
    from_: str,
    select: list[str] | str | dict[str, list[str] | str],
    join: list[str] | None = None,
    where: dict[str, dict[str, datetime.datetime]] | None = None,
) -> pandas.DataFrame: ...
```

- `from_` is the base feature group name. (Trailing underscore avoids the Python `from` keyword.)
- `select` is required. Its shape depends on whether a join is requested:
  - **Without `join`:** `list[str]` for specific feature field names, or `"*"` for all feature fields.
  - **With `join`:** `dict[str, list[str] | str]` keyed by feature group name. Each value is a list of feature field names or `"*"` for all feature fields of that group.
  - Structural fields (entity key, event timestamp, join keys) are always returned regardless of `select`.
- `join` is a list of at most one feature group name in the MVP ([FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins)).
- `where` filters the base group's event timestamp only. The shape is `{event_timestamp_name: {operator: value}}` where `operator` is one of `gt`, `gte`, `lt`, `lte`. Filters on any other column or with any other operator raise `RetrievalParameterError`.
- Returns a Pandas DataFrame with base columns unprefixed and joined columns prefixed with the joined group name (e.g. `town_market_features_avg_price_per_sqm`).
- Raises `FeatureGroupNotFoundError`, `RetrievalParameterError`, `JoinError`, `ValidationError`, or `OfflineStoreReadError`.

### `materialize`

```python
def materialize(
    self,
    feature_group: str | None = None,
) -> MaterializeResult: ...
```

- `feature_group=None` materializes all registered online-eligible groups.
- A named group must be `OFFLINE_AND_ONLINE`; otherwise raises `FeatureGroupNotMaterializableError`.
- Returns a `MaterializeResult` with per-group outcomes ([FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups)).

_Raises (no `MaterializeResult` is returned):_

- `FeatureGroupNotFoundError` — named group not in the registry.
- `FeatureGroupNotMaterializableError` — named group is `OFFLINE` only.
- `RegistryReadError` — registry unreadable.
- `OfflineStoreReadError` — offline data unreadable.

_Operational outcomes (returned in `MaterializeResult`):_

- Per-group write failures go into `MaterializeResult.failed`; the method does not raise `OnlineStoreWriteError`.
- Groups with no offline data go into `MaterializeResult.skipped`.

### `get_online_features`

```python
def get_online_features(
    self,
    *,
    from_: str,
    select: list[str] | str,
    where: dict[str, dict[str, str | int]],
) -> dict[str, Any]: ...
```

- `from_` is the target feature group name. Must be `OFFLINE_AND_ONLINE`; otherwise raises `FeatureGroupNotMaterializableError`.
- `select` is required. A list of feature field names returns those features plus structural fields. `"*"` returns all structural and feature fields.
- `where` filters by entity key using the same `{field_name: {operator: value}}` shape as `get_historical_features`. In the MVP the only accepted field name is the group's registered entity key, the only accepted operator is `eq`, and only a single value is allowed. Example: `where={"town_id": {"eq": 1}}`. Filters on any other field, operator, or with multiple values raise `RetrievalParameterError`.
- Returns an empty `dict` on miss (not an error). Returns a populated `dict` on hit, keyed by registered field names.
- Raises `FeatureGroupNotFoundError`, `FeatureGroupNotMaterializableError`, `RetrievalParameterError`, or `OnlineStoreReadError`.

> **Note:** Batch online retrieval ([FR-ONL-003](02-product-requirements.md#fr-onl-003--batch-online-retrieval)) is Could-Have and out of MVP scope. Future batch support can extend the same `where` shape with an `in` operator (e.g., `where={"town_id": {"in": [1, 2, 3]}}`) without changing the method name.

---

## Return Types

These container shapes are implemented as `@dataclass(frozen=True)`. They are part of the public surface and importable from `kitefs`.

### `ApplyResult`

```python
@dataclass(frozen=True)
class ApplyResult:
    registered_groups: list[str]
    published: bool
```

`registered_groups` lists feature group names in the regenerated registry, sorted alphabetically. `published` is `True` when the remote registry was also written.

### `PullResult` _(post-MVP)_

```python
@dataclass(frozen=True)
class PullResult:
    pulled_groups: list[str]
```

### `FeatureGroupSummary`

```python
@dataclass(frozen=True)
class FeatureGroupSummary:
    name: str
    owner: str | None
    description: str | None
    entity_key: str
    storage_target: StorageTarget
    feature_count: int
```

### `FeatureGroupDescription`

```python
@dataclass(frozen=True)
class FeatureGroupDescription:
    name: str
    storage_target: StorageTarget
    entity_key: FieldSpec
    event_timestamp: FieldSpec
    features: list[FieldSpec]
    join_keys: list[JoinKeySpec]
    ingestion_validation: ValidationMode
    offline_retrieval_validation: ValidationMode
    metadata: MetadataSpec
    applied_at: datetime.datetime | None
    last_materialized_at: datetime.datetime | None


@dataclass(frozen=True)
class FieldSpec:
    name: str
    dtype: FeatureType
    description: str | None
    expect: list[dict[str, Any]] | None  # None for structural fields


@dataclass(frozen=True)
class JoinKeySpec:
    name: str
    dtype: FeatureType
    referenced_group: str


@dataclass(frozen=True)
class MetadataSpec:
    description: str | None
    owner: str | None
    tags: dict[str, str]
```

The `expect` list mirrors the registry constraint shape defined in [05-data-and-storage-contracts.md - Field Notes](05-data-and-storage-contracts.md#field-notes).

### `IngestResult`

```python
@dataclass(frozen=True)
class IngestResult:
    feature_group: str
    accepted_rows: int
    rejected_rows: int
    written_files: list[str]
    validation_report: ValidationReport | None
```

`written_files` lists absolute paths (local) or `s3://...` URIs (AWS) for files written in this call. `validation_report` is `None` when `ingestion_validation=NONE`.

### `MaterializeResult`

The same shape is returned for both named-group and all-groups calls. Request-validation errors (unknown group, offline-only group) raise before the result is built; only operational outcomes (succeeded, skipped, failed) appear in the result.

```python
@dataclass(frozen=True)
class MaterializeResult:
    succeeded: list[str]
    skipped: list[SkippedGroup]
    failed: list[FailedGroup]


@dataclass(frozen=True)
class SkippedGroup:
    name: str
    reason: str  # human-readable, e.g. "no offline data"


@dataclass(frozen=True)
class FailedGroup:
    name: str
    error_message: str
```

### `ValidationReport`

```python
@dataclass(frozen=True)
class ValidationReport:
    pass_count: int
    fail_count: int
    failures: list[ValidationFailure]


@dataclass(frozen=True)
class ValidationFailure:
    field: str
    constraint: str        # e.g. "not_null", "gt(0)", "is_in([...])"
    actual_value: Any
    entity_key_value: Any | None
    row_index: int | None
```

`row_index` is the 0-based index into the input DataFrame when available; it is `None` when validation runs against retrieved data where the original row index is not meaningful.

### Summary

All return-type dataclasses below are importable as `from kitefs import <name>`.

| Name                      | Kind      | Purpose                                                  |
| ------------------------- | --------- | -------------------------------------------------------- |
| `ApplyResult`             | dataclass | Result of `apply()`.                                     |
| `PullResult`              | dataclass | Result of `pull()`. _(post-MVP)_                         |
| `FeatureGroupSummary`     | dataclass | Summary row returned by `list_feature_groups()`.         |
| `FeatureGroupDescription` | dataclass | Full description returned by `describe_feature_group()`. |
| `FieldSpec`               | dataclass | Field detail nested in `FeatureGroupDescription`.        |
| `JoinKeySpec`             | dataclass | Join-key detail nested in `FeatureGroupDescription`.     |
| `MetadataSpec`            | dataclass | Metadata detail nested in `FeatureGroupDescription`.     |
| `IngestResult`            | dataclass | Result of `ingest()`.                                    |
| `ValidationReport`        | dataclass | Validation detail nested in `IngestResult`.              |
| `ValidationFailure`       | dataclass | Single failure nested in `ValidationReport`.             |
| `MaterializeResult`       | dataclass | Result of `materialize()`.                               |
| `SkippedGroup`            | dataclass | Skipped-group detail nested in `MaterializeResult`.      |
| `FailedGroup`             | dataclass | Failed-group detail nested in `MaterializeResult`.       |

---

## CLI

The CLI command is `kitefs`, registered as a console script entry point ([FR-CLI-001](02-product-requirements.md#fr-cli-001--installed-cli-entry-point)). It is built with [Click](https://click.palletsprojects.com/).

### Global Behavior

| Topic            | Contract                                                                                                                            |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Help             | `kitefs --help` and `kitefs <subcommand> --help` print usage and exit `0`.                                                          |
| No subcommand    | `kitefs` with no subcommand prints help and exits non-zero.                                                                         |
| Exit codes       | `0` on success. `1` for user errors (invalid input, missing groups, configuration problems). `2` for unexpected internal errors.    |
| Error rendering  | Expected errors render as plain text on stderr without tracebacks ([CLI Error Boundary](03-system-behavior.md#cli-error-boundary)). |
| stdout vs stderr | Result content goes to stdout. Progress, prompts, and errors go to stderr.                                                          |
| Color and ANSI   | Disabled when stdout is not a TTY. Respects the `NO_COLOR` environment variable.                                                    |

### Commands

The table below is the complete MVP CLI command surface ([FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations)). SDK methods not listed as subcommands (such as `get_historical_features` and `get_online_features`) are SDK-only in the MVP.

| Subcommand    | Synopsis                                                       |
| ------------- | -------------------------------------------------------------- |
| `init`        | `kitefs init`                                                  |
| `init-config` | `kitefs init-config`                                           |
| `apply`       | `kitefs apply [--publish] [--no-confirm]`                      |
| `list`        | `kitefs list [--format text\|json] [--output PATH]`            |
| `describe`    | `kitefs describe <name> [--format text\|json] [--output PATH]` |
| `ingest`      | `kitefs ingest <name> <path>`                                  |
| `materialize` | `kitefs materialize [<name>]`                                  |

#### `init`

Creates a producer project scaffold ([FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization), [`kitefs init`](03-system-behavior.md#kitefs-init)). No flags. Exits `0` on success; non-zero if `./kitefs.yaml` already exists.

#### `init-config`

Creates a consumer-only `kitefs.yaml` ([FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization), [`kitefs init-config`](03-system-behavior.md#kitefs-init-config)). No flags. Same exit-code contract as `init`.

#### `apply`

```text
kitefs apply [--publish] [--no-confirm]
```

| Flag           | Effect                                                                                 |
| -------------- | -------------------------------------------------------------------------------------- |
| `--publish`    | Also overwrite the configured remote registry. Required for any remote registry write. |
| `--no-confirm` | Skip the publish confirmation prompt. Has no effect without `--publish`.               |

Without `--no-confirm`, `apply --publish` prints the prompt below to stderr and reads a line from stdin. Only the exact string `yes` continues; any other input aborts before configuration loading ([FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)):

```text
You are about to publish the registry to the remote target.
This overwrites the existing remote registry.
Type 'yes' to continue:
```

Successful output (stdout):

```text
Registered 2 feature group(s):
  - listing_features
  - town_market_features
Published to remote registry.
```

The "Published to remote registry." line is omitted when `--publish` is not set.

#### `list`

```text
kitefs list [--format text|json] [--output PATH]
```

| Flag       | Default | Effect                                                                  |
| ---------- | ------- | ----------------------------------------------------------------------- |
| `--format` | `text`  | Output format. `text` is a fixed-width human table. `json` is an array. |
| `--output` | stdout  | Write the result to the given file path instead of stdout.              |

Reads the registry selected by the active runtime target ([`list`](03-system-behavior.md#list)). An empty registry prints `No feature groups registered.` in text mode or `[]` in JSON mode and exits `0`.

JSON shape matches `list[FeatureGroupSummary]` serialized as:

```json
[
  {
    "name": "town_market_features",
    "owner": "data-science-team",
    "description": "Monthly town-level market aggregate",
    "entity_key": "town_id",
    "storage_target": "OFFLINE_AND_ONLINE",
    "feature_count": 1
  }
]
```

#### `describe`

```text
kitefs describe <name> [--format text|json] [--output PATH]
```

Same `--format` and `--output` semantics as `list`. JSON output matches the on-disk registry entry shape for the named group ([05-data-and-storage-contracts.md - Feature Group Entry Schema](05-data-and-storage-contracts.md#feature-group-entry-schema)). Exits non-zero with an actionable error when `<name>` is not registered.

#### `ingest`

```text
kitefs ingest <name> <path>
```

`<path>` is a local file path with extension `.csv` or `.parquet`. Other extensions are rejected before SDK work begins. CLI ingestion does not accept DataFrame input — that path is SDK-only ([FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations)).

Successful output (stdout):

```text
Ingested 1842 row(s) into 'listing_features'.
  Written files: 3
  Validation: 1842 passed, 0 failed.
```

When `ingestion_validation=NONE`, the `Validation:` line is omitted. When `ingestion_validation=FILTER`, both passed and failed counts are shown and a summary of the first failures is printed to stderr.

#### `materialize`

```text
kitefs materialize [<name>]
```

With `<name>`, materializes that group only. Without, materializes all online-eligible groups ([`materialize`](03-system-behavior.md#materialize)). CLI output is always rendered from `MaterializeResult`.

Output (stdout):

```text
Materialization summary:
  Succeeded (1): town_market_features
  Skipped (0):
  Failed (0):
```

A non-empty `Failed` list causes a non-zero exit code whether `<name>` is provided or omitted. Failure messages identify the affected group and the underlying error.

---

## Exception Hierarchy

All exceptions are defined in `kitefs.errors` and re-exported from the top-level package. The hierarchy is intentionally narrow — one base, one class per failure category that callers actually need to distinguish.

```text
KiteFSError                              # base for everything KiteFS-raised
├── ConfigurationError                   # missing/invalid kitefs.yaml or required setting
├── DefinitionError                      # invalid construction of a definition type
├── DefinitionDiscoveryError             # no definitions found in ./feature_store/definitions/
├── DefinitionValidationError            # cross-definition validation failed during apply
│
├── RegistryError                        # base for registry I/O
│   ├── RegistryReadError
│   └── RegistryWriteError
│
├── FeatureGroupNotFoundError            # name not registered
├── FeatureGroupNotMaterializableError   # group is OFFLINE-only but a materialize/online call referenced it
│
├── ValidationError                      # row-level validation failed in ERROR mode
│
├── IngestionShapeError                  # missing required columns; not row-level
│
├── RetrievalParameterError              # invalid request shape (filters, select, entity_key type)
├── JoinError                            # invalid join request (unknown referenced group, multi-join in MVP)
│
├── OfflineStoreError                    # base for offline I/O
│   ├── OfflineStoreReadError
│   └── OfflineStoreWriteError
│
├── OnlineStoreError                     # base for online I/O
│   ├── OnlineStoreReadError
│   └── OnlineStoreWriteError
│
└── ProviderError                        # provider-layer setup/auth issues not specific to a store
```

### Selection Rules

- `KiteFSError` is the catch-all. User code that needs to handle any KiteFS failure uniformly catches this.
- Configuration vs. operation: `ConfigurationError` always indicates a setup problem the user must fix in `kitefs.yaml` or environment variables. Everything else is operational.
- Validation vs. shape: `IngestionShapeError` and `RetrievalParameterError` fire before any row-level work. `ValidationError` is exclusively row-level and carries a `ValidationReport`.
- Store errors carry the underlying provider error message as their `__cause__`. They do not leak provider-specific exception types into the public API.

### `ValidationError` Attribute

```python
class ValidationError(KiteFSError):
    report: ValidationReport
```

Callers in `ERROR` mode can inspect `error.report` to display per-row failures without parsing the error message string.

---

## Internal Module Interfaces

These are the ABCs that BB-09 defines and BB-04, BB-06, and BB-07 depend on ([04-architecture.md - Provider Abstraction Boundary](04-architecture.md#provider-abstraction-boundary)). They are not part of the public surface — users do not import or implement them in MVP — but they are documented here because they are stable contracts inside the package.

Internal modules import these from `kitefs.providers.base`.

### `Provider`

```python
class Provider(abc.ABC):
    """Factory exposing the three storage interfaces for the active runtime target."""

    @abc.abstractmethod
    def registry_store(self) -> "RegistryStore": ...

    @abc.abstractmethod
    def offline_store(self) -> "OfflineStore": ...

    @abc.abstractmethod
    def online_store(self) -> "OnlineStore": ...
```

The `LocalProvider` and `AWSProvider` implementations are constructed by `kitefs.providers` based on `runtime.target` and the validated configuration.

### `RegistryStore`

```python
class RegistryStore(abc.ABC):
    """Whole-document read and overwrite of the registry artifact."""

    @abc.abstractmethod
    def read(self) -> dict[str, Any]:
        """Return the deserialized registry document.

        An existing registry with zero groups is returned normally as
        {"feature_groups": {}}.

        Raises:
            RegistryReadError: The registry artifact does not exist at
                the configured location (file missing locally, S3 object
                not found remotely), or an I/O / deserialization failure
                occurred.
        """

    @abc.abstractmethod
    def write(self, document: dict[str, Any]) -> None:
        """Atomically replace the registry document.

        Raises:
            RegistryWriteError: I/O failure. Prior document is preserved.
        """
```

### `OfflineStore`

```python
class OfflineStore(abc.ABC):
    """Append-only Parquet writes; partition-scoped reads with timestamp filters."""

    @abc.abstractmethod
    def write(
        self,
        feature_group: str,
        data: pyarrow.Table,
        *,
        event_timestamp_column: str,
        source_prefix: str,
    ) -> list[str]:
        """Append a Parquet payload, partitioned per [05-data-and-storage-contracts.md].

        Returns the list of written file paths (local) or URIs (AWS).

        Raises:
            OfflineStoreWriteError: I/O failure. No partial file is exposed.
        """

    @abc.abstractmethod
    def read(
        self,
        feature_group: str,
        *,
        event_timestamp_column: str,
        schema: pyarrow.Schema,
        timestamp_filter: TimestampFilter | None = None,
    ) -> pyarrow.Table:
        """Read offline rows for the group, applying partition pruning when possible.

        Returns an empty table with the expected schema when no files exist.

        Raises:
            OfflineStoreReadError: I/O or deserialization failure.
        """
```

`TimestampFilter` is a small internal value object:

```python
@dataclass(frozen=True)
class TimestampFilter:
    gt: datetime.datetime | None = None
    gte: datetime.datetime | None = None
    lt: datetime.datetime | None = None
    lte: datetime.datetime | None = None
```

### `OnlineStore`

```python
class OnlineStore(abc.ABC):
    """Latest-row-per-entity materialization writes; keyed point reads."""

    @abc.abstractmethod
    def materialize(
        self,
        feature_group: str,
        latest_rows: pyarrow.Table,
        *,
        entity_key_column: str,
    ) -> None:
        """Replace the group's online state with the supplied latest rows.

        Provider-specific atomicity rules apply per
        [05-data-and-storage-contracts.md].

        Raises:
            OnlineStoreWriteError: I/O failure.
        """

    @abc.abstractmethod
    def get(
        self,
        feature_group: str,
        entity_key_value: str | int,
        *,
        entity_key_column: str,
        select: list[str] | None,
    ) -> dict[str, Any]:
        """Return the row for the entity key, or an empty dict on miss.

        The SDK resolves ``"*"`` to a concrete field list before calling
        this method. ``None`` means return all fields.

        Raises:
            OnlineStoreReadError: I/O failure (not on miss).
        """
```

---

## Project Configuration File

The CLI and SDK both read `./kitefs.yaml`. The generated contents differ depending on the scaffold command used. Detailed semantics live in [FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration).

### Generated File Shapes

KiteFS generates two variants of `kitefs.yaml`:

| Aspect                          | `kitefs init`         | `kitefs init-config`                  |
| ------------------------------- | --------------------- | ------------------------------------- |
| Intended project type           | Full producer project | Consumer-only project (API / serving) |
| Default `runtime.target`        | `local`               | `remote`                              |
| Includes `remote.offline_store` | Yes                   | No                                    |
| Includes `remote.registry`      | Yes                   | Yes                                   |
| Includes `remote.online_store`  | Yes                   | Yes                                   |

Both variants share the same top-level keys (`version`, `project`, `runtime`, `remote`) and the same environment-variable interpolation syntax. The structural difference is that `kitefs init-config` omits `remote.offline_store` because consumer projects do not ingest or retrieve historical features.

### Fixed Remote Store Types

The `type` fields in `remote.registry`, `remote.offline_store`, and `remote.online_store` are fixed literal values. They identify the only supported backend for each store in the MVP. They are not user-selectable backend options and they do not support environment-variable interpolation.

| Setting                     | Required value | Present in                          |
| --------------------------- | -------------- | ----------------------------------- |
| `remote.registry.type`      | `aws_s3`       | `kitefs init`, `kitefs init-config` |
| `remote.offline_store.type` | `aws_s3`       | `kitefs init` only                  |
| `remote.online_store.type`  | `aws_dynamodb` | `kitefs init`, `kitefs init-config` |

Any other value — including an interpolation expression such as `${SOME_VAR:-aws_s3}` — is invalid configuration. Validation raises `ConfigurationError` identifying the exact setting and expected value ([FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration)).

### Full Project Configuration (`kitefs init`)

`kitefs init` generates the following `kitefs.yaml`. The inline comments are part of the generated output.

```yaml
# Generated by `kitefs init`.
#
# This configuration is for KiteFS feature store projects. It supports the full
# feature lifecycle that KiteFS provides: define, ingest, retrieve, materialize,
# and serve features.
#
# For projects that only need to consume an existing registry and online store,
# such as prediction services or REST APIs, use `kitefs init-config` to generate
# a lightweight configuration instead.
#
# runtime.target controls which configuration branch KiteFS uses:
#   local  = uses fixed conventional paths (see below)
#   remote = uses the settings in the `remote` section
#
# When runtime.target is "local", KiteFS uses these fixed paths relative to the
# project root:
#   Definitions:   ./feature_store/definitions/
#   Registry:      ./feature_store/registry.json
#   Offline store: ./feature_store/data/offline_store/
#   Online store:  ./feature_store/data/online_store/
#
# These paths are not configurable. They are created by `kitefs init` and used
# automatically when runtime.target is "local".

version: 1

project:
  # Project name. Generated as 'kitefs_featurestore_project'. You can change this manually.
  name: "kitefs_featurestore_project"

runtime:
  # Supported values: local, remote
  # Use "local" for local development and testing, "remote" for production.
  # Example:
  #   export KITEFS_RUNTIME_TARGET=remote
  target: "${KITEFS_RUNTIME_TARGET:-local}"

remote:
  # AWS region for S3 and DynamoDB access.
  # Used by all remote store backends.
  # Example:
  #   export KITEFS_AWS_REGION=eu-central-1
  region: "${KITEFS_AWS_REGION:-eu-central-1}"

  registry:
    type: aws_s3
    # S3 bucket for the published registry JSON file.
    # Example:
    #   export KITEFS_REMOTE_REGISTRY_S3_BUCKET=company-ml
    bucket: "${KITEFS_REMOTE_REGISTRY_S3_BUCKET:-}"
    # S3 object-key prefix for the registry.
    # The registry is stored at s3://{bucket}/{s3_prefix}/registry.json.
    # s3_prefix defaults to "kitefs".
    # Example:
    #   export KITEFS_REMOTE_REGISTRY_S3_PREFIX=kitefs
    s3_prefix: "${KITEFS_REMOTE_REGISTRY_S3_PREFIX:-kitefs}"

  offline_store:
    type: aws_s3
    # S3 bucket for remote offline Parquet files.
    # Example:
    #   export KITEFS_REMOTE_OFFLINE_S3_BUCKET=company-ml
    bucket: "${KITEFS_REMOTE_OFFLINE_S3_BUCKET:-}"
    # S3 object-key prefix for offline store data.
    # Offline data is stored under s3://{bucket}/{s3_prefix}/data/offline_store/.
    # s3_prefix defaults to "kitefs".
    # Example:
    #   export KITEFS_REMOTE_OFFLINE_S3_PREFIX=kitefs
    s3_prefix: "${KITEFS_REMOTE_OFFLINE_S3_PREFIX:-kitefs}"

  online_store:
    type: aws_dynamodb
    # Prefix for DynamoDB tables that store online feature values.
    # Each online-capable feature group gets a table named {dynamodb_table_prefix}{group_name}.
    # dynamodb_table_prefix defaults to "kitefs_".
    # Example:
    #   export KITEFS_REMOTE_ONLINE_DYNAMODB_TABLE_PREFIX=kitefs_
    dynamodb_table_prefix: "${KITEFS_REMOTE_ONLINE_DYNAMODB_TABLE_PREFIX:-kitefs_}"
```

### Consumer Configuration (`kitefs init-config`)

`kitefs init-config` generates a lighter `kitefs.yaml` for projects that only consume an existing registry and online store. The `remote.offline_store` block is omitted.

```yaml
# Generated by `kitefs init-config`.
#
# This configuration is for projects that only need to consume an existing
# KiteFS registry and online store, such as REST APIs or prediction services.
#
# It does not include feature definitions, offline store, or local development
# scaffolding. For the full feature lifecycle (define, ingest, retrieve,
# materialize, serve), use `kitefs init` instead.
#
# runtime.target controls which configuration branch KiteFS uses:
#   local  = uses fixed conventional paths (see below)
#   remote = uses the settings in the `remote` section
#
# When runtime.target is "local", KiteFS uses these fixed paths relative to the
# project root:
#   Registry:    ./feature_store/registry.json
#   Online store: ./feature_store/data/online_store/
#
# These paths are not configurable. If you need the full feature lifecycle
# (definitions, offline store), run `kitefs init` instead.

version: 1

project:
  # Project name. Generated as 'kitefs_featurestore_project'. You can change this manually.
  name: "kitefs_featurestore_project"

runtime:
  # Supported values: local, remote
  # Use "local" for local development and testing, "remote" for production.
  # Example:
  #   export KITEFS_RUNTIME_TARGET=local
  target: "${KITEFS_RUNTIME_TARGET:-remote}"

remote:
  # AWS region for S3 and DynamoDB access.
  # Used by all remote store backends.
  # Example:
  #   export KITEFS_AWS_REGION=eu-central-1
  region: "${KITEFS_AWS_REGION:-eu-central-1}"

  registry:
    type: aws_s3
    # S3 bucket for the published registry JSON file.
    # Example:
    #   export KITEFS_REMOTE_REGISTRY_S3_BUCKET=company-ml
    bucket: "${KITEFS_REMOTE_REGISTRY_S3_BUCKET:-}"
    # S3 object-key prefix for the registry.
    # The registry is stored at s3://{bucket}/{s3_prefix}/registry.json.
    # s3_prefix defaults to "kitefs".
    # Example:
    #   export KITEFS_REMOTE_REGISTRY_S3_PREFIX=kitefs
    s3_prefix: "${KITEFS_REMOTE_REGISTRY_S3_PREFIX:-kitefs}"

  online_store:
    type: aws_dynamodb
    # Prefix for DynamoDB tables that store online feature values.
    # Each online-capable feature group gets a table named {dynamodb_table_prefix}{group_name}.
    # dynamodb_table_prefix defaults to "kitefs_".
    # Example:
    #   export KITEFS_REMOTE_ONLINE_DYNAMODB_TABLE_PREFIX=kitefs_
    dynamodb_table_prefix: "${KITEFS_REMOTE_ONLINE_DYNAMODB_TABLE_PREFIX:-kitefs_}"
```

### Environment Variable Interpolation

Documented configurable values support `${VAR}` and `${VAR:-default}` interpolation ([FR-CFG-003](02-product-requirements.md#fr-cfg-003--environment-variable-interpolation)). Fixed remote store `type` fields are excluded from interpolation; see [Fixed Remote Store Types](#fixed-remote-store-types).

```yaml
remote:
  registry:
    bucket: "${KITEFS_REMOTE_REGISTRY_S3_BUCKET:-}"
    s3_prefix: "${KITEFS_REMOTE_REGISTRY_S3_PREFIX:-kitefs}"
```

When a variable is unset and no default is provided, expansion produces an empty string. When a default is provided after `:-`, that value is used if the variable is unset or empty.

### Runtime Target Override

The `KITEFS_RUNTIME_TARGET` environment variable overrides the file's `runtime.target` when set ([FR-CFG-002](02-product-requirements.md#fr-cfg-002--runtime-target-switching)). Supported values: `local`, `remote`. Any other value raises `ConfigurationError`.

Both generated files already interpolate this variable in `runtime.target`:

```yaml
runtime:
  target: "${KITEFS_RUNTIME_TARGET:-local}"   # kitefs init default
  target: "${KITEFS_RUNTIME_TARGET:-remote}"  # kitefs init-config default
```

### Local Paths

Local paths are fixed by convention and are not configurable in the MVP ([FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration)):

| Artifact          | Path                                          | Used by `init` | Used by `init-config` |
| ----------------- | --------------------------------------------- | -------------- | --------------------- |
| Configuration     | `./kitefs.yaml`                               | Yes            | Yes                   |
| Definitions       | `./feature_store/definitions/`                | Yes            | No                    |
| Registry          | `./feature_store/registry.json`               | Yes            | Yes                   |
| Offline data root | `./feature_store/data/offline_store/`         | Yes            | No                    |
| Online database   | `./feature_store/data/online_store/online.db` | Yes            | No                    |
