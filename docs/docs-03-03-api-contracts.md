# Kite Feature Store — API & Interface Contracts

> **Document Purpose:**
> This document pins down the exact public API contracts for KiteFS:
> what users import, what they call, what they get back, and what
> exceptions they catch. It also defines the internal module interfaces
> that building blocks expose to each other.
>
> This is the contract between the architecture documents and the code.
> A developer implementing a building block reads this document to know
> the exact signatures they must implement. A developer writing user
> stories references this document to specify acceptance criteria
> without ambiguity.
>
> **Structure:**
> - §1 — Public API surface: everything users `from kitefs import ...`
> - §2 — SDK method contracts: signatures, parameters, returns, exceptions
> - §3 — CLI contracts: commands, arguments, exit codes, output formats
> - §4 — Exception hierarchy: classes, inheritance, when each is raised
> - §5 — Internal module interfaces: Protocol/ABC signatures per building block
> - §6 — Cross-cutting contracts: structural columns, timestamps, type mapping
>
> **Relationship to other documents:**
> - Built on: [Architecture Overview (docs-03-01)](docs-03-01-architecture-overview.md),
>   [Internals & Data (docs-03-02)](docs-03-02-internals-and-data.md),
>   [Requirements (docs-02)](docs-02-project-requirements.md),
>   [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)
> - Feeds into: [Implementation Guide (docs-04)](docs-04-implementation-guide.md)
>
> **How to read this document:**
> §1–§3 define the **external** contracts — what users see.
> §4 defines the **error** contracts — what users catch.
> §5 defines the **internal** contracts — what implementers build.
> §6 defines **shared rules** that apply everywhere.
> Each section is self-contained and cross-referenced.
>
> **Stability:**
> These contracts are the reference for MVP implementation. Changes
> to any signature, return type, or exception require updating this
> document first, then propagating to affected code and tests.
>
> **Owner:** Fedai Paça
> **Last Updated:** 2026-04-13
> **Status:** Draft

---

## Conventions

**Signature notation:** All signatures use Python type hints. Optional parameters show their default values. `|` denotes union types (Python 3.12+, per CON-001).

**Requirement traceability:** Each contract references the functional requirement(s) it satisfies using `FR-XXX` identifiers from [docs-02](docs-02-project-requirements.md).

**Building block references:** Building blocks are cited as `BB-XX` from [docs-03-01 §3.2](docs-03-01-architecture-overview.md).

**Terminology:** All terms follow the domain glossary in [docs-01 §4](docs-01-project-charter.md). Key terms: entity key, event timestamp, feature group, feature, offline store, online store, materialization, point-in-time correctness.

---

## 1. Public API Surface

> _Everything a user can `from kitefs import ...`. This section lists
> every public symbol and its category. Detailed method contracts
> for `FeatureStore` are in §2._

### 1.1 Public Imports

```python
from kitefs import (
    # SDK entry point
    FeatureStore,

    # Definition types
    FeatureGroup,
    Feature,
    EntityKey,
    EventTimestamp,
    JoinKey,
    Metadata,
    Expect,

    # Enums
    FeatureType,
    StorageTarget,
    ValidationMode,
)
```

All public symbols are importable from the top-level `kitefs` package. No sub-package imports are required for standard usage. Exception classes (§4) are importable from `kitefs.exceptions`.

_(FR-DEF-001, FR-DEF-002, FR-DEF-003, FR-DEF-004, FR-DEF-005, FR-DEF-006)_

---

### 1.2 Enums

**`FeatureType`**

| Value | Description | Traces To |
| --- | --- | --- |
| `STRING` | Text values | FR-DEF-002 |
| `INTEGER` | Whole numbers (64-bit) | FR-DEF-002 |
| `FLOAT` | Decimal numbers (64-bit) | FR-DEF-002 |
| `DATETIME` | Timestamps (microsecond precision, timezone-naive) | FR-DEF-002 |

**`StorageTarget`**

| Value | Description | Traces To |
| --- | --- | --- |
| `OFFLINE` | Offline store only (historical retrieval and training) | FR-DEF-003 |
| `OFFLINE_AND_ONLINE` | Both stores (materializable to online for serving) | FR-DEF-003 |

**`ValidationMode`**

| Value | Description | Traces To |
| --- | --- | --- |
| `ERROR` | Reject entire operation if any record fails | FR-VAL-004 |
| `FILTER` | Exclude failing records, proceed with passing ones | FR-VAL-005 |
| `NONE` | Skip data validation entirely (schema validation still runs) | FR-VAL-006 |

---

### 1.3 Definition Types

All definition types are **frozen dataclasses** (immutable after creation). They are serializable via `dataclasses.asdict()`. _(KTD-6 in [docs-03-02 §2.3](docs-03-02-internals-and-data.md))_

#### `FeatureGroup`

The top-level definition type. One `FeatureGroup` instance per feature group, defined at module level in a `.py` file under `definitions/`.

```python
@dataclass(frozen=True)
class FeatureGroup:
    name: str
    storage_target: StorageTarget
    entity_key: EntityKey
    event_timestamp: EventTimestamp
    features: list[Feature]
    join_keys: list[JoinKey] = field(default_factory=list)
    ingestion_validation: ValidationMode = ValidationMode.ERROR
    offline_retrieval_validation: ValidationMode = ValidationMode.NONE
    metadata: Metadata = field(default_factory=Metadata)
```

| Parameter | Type | Default | Constraints | Traces To |
| --- | --- | --- | --- | --- |
| `name` | `str` | _(required)_ | Must be unique across all feature groups in the project | FR-DEF-001, FR-REG-004 |
| `storage_target` | `StorageTarget` | _(required)_ | — | FR-DEF-003 |
| `entity_key` | `EntityKey` | _(required)_ | Exactly one per group (enforced by constructor signature) | FR-DEF-001, FR-DEF-007 |
| `event_timestamp` | `EventTimestamp` | _(required)_ | Exactly one per group; dtype must be `DATETIME` | FR-DEF-001, FR-DEF-007 |
| `features` | `list[Feature]` | _(required)_ | At least one. Stored internally as tuple sorted by `name` | FR-DEF-001 |
| `join_keys` | `list[JoinKey]` | `[]` | Each must reference an existing feature group with matching entity key type and name | FR-OFF-004 |
| `ingestion_validation` | `ValidationMode` | `ERROR` | — | FR-DEF-005, FR-VAL-009 |
| `offline_retrieval_validation` | `ValidationMode` | `NONE` | — | FR-DEF-005, FR-VAL-009 |
| `metadata` | `Metadata` | `Metadata()` | All metadata fields are optional | FR-DEF-006 |

**`__post_init__` behavior:** The `features` list is normalized to a tuple sorted alphabetically by `name` for deterministic `__eq__` and serialization. _(KTD-16 in [docs-03-02 §2.3](docs-03-02-internals-and-data.md))_

**Field name uniqueness:** Field names must be unique across `entity_key.name`, `event_timestamp.name`, and all `feature.name` values. Enforced by BB-04 during `apply()`.

---

#### `EntityKey`

```python
@dataclass(frozen=True)
class EntityKey:
    name: str
    dtype: FeatureType
    description: str | None = None
```

| Parameter | Type | Default | Constraints |
| --- | --- | --- | --- |
| `name` | `str` | _(required)_ | Column name in ingested data |
| `dtype` | `FeatureType` | _(required)_ | Any supported type |
| `description` | `str \| None` | `None` | Human-readable description |

Structural column — always included in query results regardless of `select`. Implicitly not-null (null entity keys are rejected at schema validation, mode-independent). Does not accept expectations.

---

#### `EventTimestamp`

```python
@dataclass(frozen=True)
class EventTimestamp:
    name: str
    dtype: FeatureType
    description: str | None = None
```

| Parameter | Type | Default | Constraints |
| --- | --- | --- | --- |
| `name` | `str` | _(required)_ | Column name in ingested data |
| `dtype` | `FeatureType` | _(required)_ | Must be `FeatureType.DATETIME` (enforced by BB-04 at `apply()`) |
| `description` | `str \| None` | `None` | Human-readable description |

Structural column — always included in query results regardless of `select`. Implicitly not-null (null event timestamps are rejected at schema validation, mode-independent). Does not accept expectations. Used for partitioning and point-in-time joins.

---

#### `Feature`

```python
@dataclass(frozen=True)
class Feature:
    name: str
    dtype: FeatureType
    description: str | None = None
    expect: Expect | None = None
```

| Parameter | Type | Default | Constraints |
| --- | --- | --- | --- |
| `name` | `str` | _(required)_ | Column name in ingested data |
| `dtype` | `FeatureType` | _(required)_ | Any supported type |
| `description` | `str \| None` | `None` | Human-readable description |
| `expect` | `Expect \| None` | `None` | Feature-level validation expectations |

_(FR-DEF-001, FR-DEF-004)_

---

#### `Expect`

Fluent builder for feature expectations. Each method returns a **new** `Expect` instance (immutable chain). Internal representation: tuple of constraint dicts, serializable via `dataclasses.asdict()`.

```python
@dataclass(frozen=True)
class Expect:
    _constraints: tuple[dict, ...] = ()

    def not_null(self) -> Expect: ...
    def gt(self, value: int | float) -> Expect: ...
    def gte(self, value: int | float) -> Expect: ...
    def lt(self, value: int | float) -> Expect: ...
    def lte(self, value: int | float) -> Expect: ...
    def one_of(self, values: list) -> Expect: ...
```

| Method | Constraint | Example |
| --- | --- | --- |
| `.not_null()` | Value must not be null | `Expect().not_null()` |
| `.gt(v)` | Value must be greater than `v` | `Expect().gt(0)` |
| `.gte(v)` | Value must be greater than or equal to `v` | `Expect().gte(1900)` |
| `.lt(v)` | Value must be less than `v` | `Expect().lt(100)` |
| `.lte(v)` | Value must be less than or equal to `v` | `Expect().lte(2030)` |
| `.one_of(v)` | Value must be in the specified set | `Expect().one_of(["A", "B", "C"])` |

Methods can be chained: `Expect().not_null().gte(0).lte(1000)`.

_(FR-DEF-004, FR-VAL-008)_

---

#### `JoinKey`

```python
@dataclass(frozen=True)
class JoinKey:
    field_name: str
    referenced_group: str
```

| Parameter | Type | Default | Constraints |
| --- | --- | --- | --- |
| `field_name` | `str` | _(required)_ | Must match a feature name in this group AND match the entity key name of `referenced_group` |
| `referenced_group` | `str` | _(required)_ | Must be a registered feature group |

Join key constraints are validated by BB-04 during `apply()`: the referenced group must exist, the field name must match the referenced group's entity key name, and the field's dtype must match the referenced entity key's dtype.

_(FR-OFF-004)_

---

#### `Metadata`

```python
@dataclass(frozen=True)
class Metadata:
    description: str | None = None
    owner: str | None = None
    tags: dict[str, str] | None = None
```

| Parameter | Type | Default | Constraints |
| --- | --- | --- | --- |
| `description` | `str \| None` | `None` | Human-readable description of the feature group |
| `owner` | `str \| None` | `None` | Owner name or team |
| `tags` | `dict[str, str] \| None` | `None` | Arbitrary key-value tags |

All fields are optional. The `metadata` parameter on `FeatureGroup` defaults to `Metadata()`, so it can be omitted entirely.

_(FR-DEF-006)_

---

## 2. SDK Method Contracts (`FeatureStore`)

> _The `FeatureStore` class is the single entry point for all SDK
> operations. Each method maps to exactly one operational flow
> in [docs-03-01 §4](docs-03-01-architecture-overview.md)._

### 2.0 Constructor

```python
class FeatureStore:
    def __init__(self, project_root: str | Path | None = None) -> None: ...
```

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `project_root` | `str \| Path \| None` | `None` | Path to the project root containing `kitefs.yaml`. If `None`, searches upward from the current working directory. |

**Behavior:**
1. Locates `kitefs.yaml` — uses `project_root` if provided, otherwise walks up from `cwd`
2. Loads and validates configuration via BB-10 (Configuration Manager)
3. Instantiates the configured provider via BB-09 (Provider Layer)
4. Creates core module instances (BB-04, BB-05, BB-06, BB-07, BB-08) with provider injected

**Raises:**
- `ConfigurationError` — if `kitefs.yaml` is not found, malformed, or contains invalid values

_(FR-CFG-001, FR-CFG-003, FR-CFG-004)_

---

### 2.1 `apply()`

```python
def apply(self) -> ApplyResult: ...
```

Discovers all `FeatureGroup` definitions in the `definitions/` directory, validates them, and fully regenerates `registry.json`. All-or-nothing: if any definition is invalid, the registry remains unchanged and all errors are reported.

> **Note:** `apply()` is a project-level operation intended for CLI use, not for programmatic use in notebooks or scripts. _(FR-REG-002)_

**Parameters:** None.

**Returns:** A result describing the outcome of the apply operation — the number of feature groups registered and names of all registered groups.

**Raises:**
- `DefinitionError` — if no `FeatureGroup` instances are found in `definitions/`, or if any definition fails validation (duplicate names, invalid types, EventTimestamp dtype not DATETIME, field name collisions, invalid join key references). All errors are collected and reported together (KTD-9).
- `ProviderError` — if the registry file cannot be written (disk full, S3 permission denied)

**Preconditions:**
- `FeatureStore` is instantiated (config loaded, provider ready)
- `definitions/` directory exists with at least one `.py` file containing a `FeatureGroup` instance

**Postconditions:**
- `registry.json` is regenerated from current definitions
- Runtime fields (`last_materialized_at`) are preserved from the previous registry
- `applied_at` timestamp is set to the current time for each group

_(FR-REG-001, FR-REG-002, FR-REG-003, FR-REG-004, FR-REG-007)_

---

### 2.2 `ingest()`

```python
def ingest(
    self,
    feature_group_name: str,
    data: DataFrame | str,
) -> IngestResult: ...
```

Writes feature data to the offline store for a registered feature group. Validates schema and data according to the group's ingestion validation mode before writing.

**Parameters:**

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `feature_group_name` | `str` | _(required)_ | Name of the registered feature group |
| `data` | `DataFrame \| str` | _(required)_ | Pandas DataFrame, or path to a local CSV or Parquet file |

**Returns:** A result describing the outcome of the ingestion — rows written, partitions affected.

**Raises:**
- `FeatureGroupNotFoundError` — if `feature_group_name` is not in the registry
- `IngestionError` — if `data` is an unsupported type or file format cannot be determined
- `SchemaValidationError` — if required columns are missing, or entity key / event timestamp columns contain null values
- `DataValidationError` — if ingestion validation mode is `ERROR` and any record fails expectation checks
- `ProviderError` — if the Parquet write fails

**Preconditions:**
- Feature group is registered (i.e., `apply()` has been run)
- Data contains all required columns (entity key, event timestamp, declared features)

**Postconditions:**
- New Parquet file(s) created in the offline store under the appropriate partitions
- Existing offline store data is untouched (append-only)

**Behavioral notes:**
- Extra columns in `data` that are not in the definition are silently dropped _(FR-ING-002)_
- Schema validation (missing columns, null structural columns) always runs, regardless of validation mode _(BB-05)_
- In `FILTER` mode, failing records are excluded; if all rows are filtered, returns with 0 rows written (not an error)
- In `NONE` mode, data validation (Phase 2) is skipped; schema validation still runs
- File path input: the file extension (`.csv` or `.parquet`) determines the loader

_(FR-ING-001, FR-ING-002, FR-ING-003, FR-ING-004, FR-ING-005, FR-ING-006, FR-ING-007)_

---

### 2.3 `get_historical_features()`

```python
def get_historical_features(
    self,
    from_: str,
    select: list[str] | str | dict[str, list[str] | str],
    where: dict[str, dict[str, Any]] | None = None,
    join: list[str] | None = None,
) -> DataFrame: ...
```

Retrieves historical feature data from the offline store for model training. Supports point-in-time correct joins with other feature groups.

**Parameters:**

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `from_` | `str` | _(required)_ | Base feature group name — its rows define the output cardinality |
| `select` | `list[str] \| str \| dict[str, list[str] \| str]` | _(required)_ | Features to retrieve. Without `join`: list of feature names or `"*"`. With `join`: dict keyed by group name; `"*"` is valid as a value for any group. |
| `where` | `dict[str, dict[str, Any]] \| None` | `None` | Row filter on the base group. Uses unified where format (see below). |
| `join` | `list[str] \| None` | `None` | Feature groups to join via point-in-time correct join. MVP limit: one group. |

**Unified `where` format:**

```python
where = {
    "field_name": {
        "operator": value,
    }
}
```

Operators: `eq`, `in`, `gt`, `gte`, `lt`, `lte`. Multiple operators on the same field combine with AND semantics.

**MVP restriction:** Only `event_timestamp` is accepted as a field name, and only `gt`, `gte`, `lt`, `lte` operators are accepted. _(FR-OFF-007)_

Example:
```python
where={"event_timestamp": {"gte": datetime(2024, 2, 1), "lte": datetime(2024, 12, 31)}}
```

**`select` format:**

```python
# Without join — list or "*"
select = ["net_area", "number_of_rooms"]
select = "*"  # entity key + event timestamp + all features

# With join — dict keyed by group name; "*" valid as value
select = {
    "listing_features": ["net_area", "number_of_rooms", "build_year"],
    "town_market_features": ["avg_price_per_sqm"],
}
select = {
    "listing_features": "*",
    "town_market_features": "*",
}
```

For the `from_` group, `"*"` returns: entity key, event timestamp, and all features (including join key fields). For a joined group, `"*"` returns: all features plus `event_timestamp`; the entity key is not separately included because it is the join key already present from the `from_` group. _(FR-OFF-002)_

**Returns:** A Pandas DataFrame containing the requested features with structural columns (entity key, event timestamp) always included. When a join is performed, conflicting column names from the joined group are prefixed with `{joined_group_name}_` (e.g., `town_market_features_event_timestamp`). The join key column appears once from the base group (not duplicated). Base group columns are never renamed. _(FR-OFF-010)_

**Raises:**
- `FeatureGroupNotFoundError` — if `from_` or any group in `join` is not in the registry
- `JoinError` — if no valid join path exists between `from_` and a joined group, or if `join` contains more than one group (MVP)
- `RetrievalError` — if `select` references features that don't exist, or `where` uses an unsupported field/operator for this method
- `SchemaValidationError` — if offline data has schema issues (should not happen if ingestion validation was used)
- `DataValidationError` — if any group's offline retrieval validation mode is `ERROR` and data fails expectations
- `ProviderError` — if Parquet reads fail

**Preconditions:**
- Base feature group and all joined groups are registered
- Data has been ingested for the base group (and joined groups if `join` is specified)
- If `join` is specified, join keys are declared in the base group's definition linking to the joined group

**Postconditions:**
- Returns a DataFrame; no side effects on the store
- Unmatched joined rows produce null-filled columns (base rows are never dropped) _(FR-OFF-005)_
- Point-in-time correctness is enforced: `joined.event_timestamp ≤ base.event_timestamp` _(FR-OFF-003)_

**Behavioral notes:**
- `where` applies only to the base group; joined groups' temporal scope is determined by the PIT join condition _(FR-OFF-007)_
- Partition pruning is applied for efficient reads (month-level for base, upper-bound for joined) _(BB-06)_
- Validation runs after `select` is applied — only selected features are validated _(BB-05)_
- In `FILTER` mode, failing rows are removed before the join; the PIT join finds the next-most-recent valid record
- If the base DataFrame is empty after filtering, an empty DataFrame is returned (not an error)

_(FR-OFF-001, FR-OFF-002, FR-OFF-003, FR-OFF-004, FR-OFF-005, FR-OFF-006, FR-OFF-007, FR-OFF-008, FR-OFF-009, FR-OFF-010)_

---

### 2.4 `get_online_features()`

```python
def get_online_features(
    self,
    from_: str,
    select: list[str] | str,
    where: dict[str, dict[str, Any]],
) -> dict | None: ...
```

Retrieves the latest feature values for a single entity key from the online store.

**Parameters:**

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `from_` | `str` | _(required)_ | Feature group name (must be `OFFLINE_AND_ONLINE`) |
| `select` | `list[str] \| str` | _(required)_ | Feature names to retrieve, or `"*"` for all features |
| `where` | `dict[str, dict[str, Any]]` | _(required)_ | Entity key filter. Uses unified where format. |

**MVP restriction:** Only the entity key field is accepted as the `where` field name, only the `eq` operator is accepted, and only a single value is allowed. _(FR-ONL-002)_

Example:
```python
result = store.get_online_features(
    from_="town_market_features",
    select=["avg_price_per_sqm"],
    where={"town_id": {"eq": 1}},
)
# Returns: {"town_id": 1, "event_timestamp": "2025-01-01T00:00:00", "avg_price_per_sqm": 27200.0}
# or None if entity key not found
```

**Returns:** `dict | None` — a dict of feature values (including structural columns: entity key and event timestamp) if the entity key exists, or `None` if it does not. Structural columns are always included regardless of `select`. _(FR-ONL-002, NFR-UX-002)_

**Raises:**
- `FeatureGroupNotFoundError` — if `from_` is not in the registry
- `RetrievalError` — if the feature group's `storage_target` is `OFFLINE` only, or if `select` references features that don't exist, or if `where` uses an unsupported field/operator for this method
- `MaterializationError` — if the online store table does not exist (i.e., `materialize()` has never been run for this group)
- `ProviderError` — if the online store read fails

**Preconditions:**
- Feature group is registered with `storage_target=OFFLINE_AND_ONLINE`
- `materialize()` has been run at least once for this group

**Postconditions:**
- Returns a dict or None; no side effects on the store

**Behavioral notes:**
- No validation engine involvement on the serving path — data was validated at ingestion time
- `None` for a missing entity key is not an error; the caller decides how to handle it
- The online store holds only the latest values per entity key; previous values are overwritten on materialization

_(FR-ONL-001, FR-ONL-002)_

---

### 2.5 `materialize()`

```python
def materialize(
    self,
    feature_group_name: str | None = None,
) -> MaterializeResult: ...
```

Reads the latest value per entity key from the offline store and writes it to the online store. Full overwrite per group.

**Parameters:**

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `feature_group_name` | `str \| None` | `None` | If provided, materialize only this group. If `None`, materialize all `OFFLINE_AND_ONLINE` groups. |

**Returns:** A result describing the outcome — groups processed, entity key counts written per group. If materializing all groups, the result includes per-group status (success, skipped, or failed).

**Raises:**
- `FeatureGroupNotFoundError` — if specified group is not in the registry
- `MaterializationError` — if specified group's `storage_target` is `OFFLINE` only _(FR-MAT-002)_, or if no `OFFLINE_AND_ONLINE` groups exist when `feature_group_name=None`
- `ProviderError` — if offline read or online write fails

**Preconditions:**
- Feature group(s) are registered with `storage_target=OFFLINE_AND_ONLINE`

**Postconditions:**
- Online store contains exactly one row per entity key per materialized group (the latest by `event_timestamp`)
- `last_materialized_at` is updated in the registry for each successfully materialized group
- Materialization is idempotent: running twice with the same offline data produces the same online state _(FR-MAT-003)_

**Behavioral notes:**
- If a group's offline store is empty, it is skipped with a warning (not an error) _(FR-MAT-001)_
- When materializing all groups, a failure in one group does not prevent other groups from being materialized _(FR-MAT-001)_
- Online write is atomic: full overwrite within a single transaction _(NFR-REL-002)_
- Latest-per-entity extraction: group by entity key, select the row with maximum `event_timestamp`

_(FR-MAT-001, FR-MAT-002, FR-MAT-003, FR-MAT-004, FR-MAT-005)_

---

### 2.6 `list_feature_groups()`

```python
def list_feature_groups(
    self,
    format: str | None = None,
    target: str | None = None,
) -> list[dict] | str: ...
```

Returns a summary of all registered feature groups.

**Parameters:**

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `format` | `str \| None` | `None` | If `"json"`, returns a JSON string (or writes JSON to file if `target` is set) |
| `target` | `str \| None` | `None` | If provided, write JSON output to this file path |

**Returns:** depends on parameters:
- No `target`, no `format`: `list[dict]` — one dict per group with summary fields (name, owner, entity key name, storage target, feature count)
- `format="json"`, no `target`: `str` — JSON string
- `target` provided: writes JSON file, returns a success indicator

Returns an empty list if no feature groups are registered (not an error).

**Raises:**
- `ProviderError` — if registry cannot be read, or if file write fails when `target` is specified

**Summary fields per group:** `name`, `owner`, `entity_key` (name), `storage_target`, `feature_count`.

_(FR-REG-005, FR-CLI-012)_

---

### 2.7 `describe_feature_group()`

```python
def describe_feature_group(
    self,
    name: str,
    format: str | None = None,
    target: str | None = None,
) -> dict | str: ...
```

Returns the full definition of a specific registered feature group.

**Parameters:**

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | `str` | _(required)_ | Feature group name |
| `format` | `str \| None` | `None` | If `"json"`, returns a JSON string (or writes JSON to file if `target` is set) |
| `target` | `str \| None` | `None` | If provided, write JSON output to this file path |

**Returns:** depends on parameters:
- No `target`, no `format`: `dict` — full definition including name, storage target, entity key, event timestamp, all features with types and expectations, join keys, validation modes, metadata, `applied_at`, `last_materialized_at`
- `format="json"`, no `target`: `str` — JSON string
- `target` provided: writes JSON file, returns a success indicator

**Raises:**
- `FeatureGroupNotFoundError` — if `name` is not in the registry
- `ProviderError` — if registry cannot be read, or if file write fails when `target` is specified

_(FR-REG-006, FR-CLI-012)_

---

### 2.8 Future: `sync_registry()` and `pull_registry()`

> _Priority: Should Have. These contracts are defined for completeness
> but may not be implemented in the first MVP iteration._

```python
def sync_registry(self) -> None: ...
def pull_registry(self) -> None: ...
```

**`sync_registry()`** uploads the local `registry.json` to the configured remote storage (S3). Full overwrite. Requires a remote provider to be configured in `kitefs.yaml`.

**`pull_registry()`** downloads `registry.json` from the configured remote storage and overwrites the local copy. Requires a remote provider to be configured.

**Raises:**
- `ConfigurationError` — if no remote provider is configured
- `ProviderError` — if the upload/download fails

_(FR-REG-008, FR-REG-009)_

---

## 3. CLI Contracts

> _The CLI is a thin entry point (BB-01) that delegates to the SDK
> for all operations except `kitefs init`. All commands follow the
> same pattern: resolve project root → instantiate `FeatureStore`
> → call SDK method → render output → exit._
>
> _Exit codes: `0` for success, `1` for error. Errors are rendered
> to stderr in plain text. Python tracebacks are suppressed._

_(FR-CLI-001, FR-CLI-011)_

### 3.1 `kitefs init`

```
kitefs init [path]
```

Creates a new KiteFS project at the specified path (or current directory).

| Argument/Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `path` | positional | No | Current directory | Directory to initialize as a project |

**Delegates to:** Self-contained in BB-01 (no SDK instantiation — `kitefs.yaml` doesn't exist yet). _(KTD-4)_

**On success (exit 0):**
Creates the following structure:
- `kitefs.yaml` with default configuration (`provider: local`, `storage_root: ./feature_store/`)
- `feature_store/definitions/` with `__init__.py` and `example_features.py`
- `feature_store/data/offline_store/` (empty)
- `feature_store/data/online_store/` (empty)
- `feature_store/registry.json` seeded as `{ "version": "1.0", "feature_groups": {} }`
- `.gitignore` created or appended with `feature_store/data/`

Prints confirmation: project path, provider, config file location.

**On error (exit 1):**
- `kitefs.yaml` already exists at the target location → error: "KiteFS project already initialized at this location."

_(FR-CLI-002)_

---

### 3.2 `kitefs apply`

```
kitefs apply
```

Scans definitions, validates, and regenerates the registry.

| Argument/Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| _(none)_ | — | — | — | — |

**Delegates to:** `store.apply()`

**On success (exit 0):** Prints summary: "N feature groups registered."

**On error (exit 1):**
- No KiteFS project found → "No KiteFS project found. Run `kitefs init` to create one."
- SDK raises `DefinitionError` → renders all collected errors to stderr

_(FR-CLI-003)_

---

### 3.3 `kitefs ingest`

```
kitefs ingest <feature_group_name> <file_path>
```

Ingests data from a CSV or Parquet file into the offline store.

| Argument/Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `feature_group_name` | positional | Yes | — | Registered feature group name |
| `file_path` | positional | Yes | — | Path to CSV or Parquet file |

**Delegates to:** `store.ingest(feature_group_name, file_path)`

**On success (exit 0):** Prints ingestion summary (rows written, partitions affected).

**On error (exit 1):** Renders the SDK exception message to stderr.

**Note:** DataFrame ingestion is available only through the SDK (not CLI). _(FR-ING-001)_

_(FR-CLI-004)_

---

### 3.4 `kitefs list`

```
kitefs list [--format json] [--target <file_path>]
```

Lists all registered feature groups with summary information.

| Argument/Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `--format` | option | No | — | Output format. Supported: `json` |
| `--target` | option | No | — | File path to write output to |

**Delegates to:** `store.list_feature_groups(format, target)`

**On success (exit 0):**
- No groups registered → informational message: "No feature groups registered. Run `kitefs apply` first."
- `--target` provided → "Output written to {target}"
- `--format json` (no target) → prints JSON to stdout
- Default (no flags) → renders a human-readable table to stdout

_(FR-CLI-005, FR-CLI-012)_

---

### 3.5 `kitefs describe`

```
kitefs describe <feature_group_name> [--format json] [--target <file_path>]
```

Displays the full definition of a specific feature group.

| Argument/Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `feature_group_name` | positional | Yes | — | Registered feature group name |
| `--format` | option | No | — | Output format. Supported: `json` |
| `--target` | option | No | — | File path to write output to |

**Delegates to:** `store.describe_feature_group(name, format, target)`

**On success (exit 0):**
- `--target` provided → "Output written to {target}"
- `--format json` (no target) → prints JSON to stdout
- Default → renders human-readable key-value layout

**On error (exit 1):**
- Feature group not found → "Feature group '{name}' not found. Run `kitefs list` to see registered groups."

_(FR-CLI-006, FR-CLI-012)_

---

### 3.6 `kitefs materialize`

```
kitefs materialize [feature_group_name]
```

Triggers materialization for a specific group or all eligible groups.

| Argument/Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `feature_group_name` | positional | No | — | If omitted, materialize all `OFFLINE_AND_ONLINE` groups |

**Delegates to:** `store.materialize(feature_group_name)`

**On success (exit 0):** Prints materialization summary (groups processed, entity counts).

**On error (exit 1):** Renders the SDK exception message to stderr.

_(FR-CLI-007)_

---

### 3.7 Future: `kitefs registry-sync` and `kitefs registry-pull`

> _Priority: Should Have._

```
kitefs registry-sync
kitefs registry-pull
```

**`registry-sync`** uploads local registry to remote storage. No parameters.
**`registry-pull`** downloads remote registry to local. No parameters.

**Delegates to:** `store.sync_registry()` / `store.pull_registry()`

_(FR-CLI-008)_

---

### 3.8 Future: `kitefs mock`

> _Priority: Should Have._

```
kitefs mock [feature_group_name] [options]
```

Generates mock data for a feature group and ingests it into the local offline store. Available only with the `local` provider. Full design to be defined when prioritized.

_(FR-CLI-009)_

---

### 3.9 Future: `kitefs sample`

> _Priority: Should Have._

```
kitefs sample <feature_group_name> [options]
```

Pulls a filtered subset of data from a remote offline store into the local offline store. Available only with the `local` provider. Useful for working locally with a representative slice of production data. Full design to be defined when prioritized.

_(FR-CLI-010)_

---

## 4. Exception Hierarchy

> _All KiteFS exceptions inherit from `KiteFSError`. Users can catch
> `KiteFSError` for a broad handler or specific subclasses for
> targeted handling. All exceptions carry an actionable message
> (NFR-UX-001) describing what went wrong and how to fix it._
>
> _Importable from `kitefs.exceptions`._

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

---

### 4.1 `KiteFSError`

```python
class KiteFSError(Exception): ...
```

Base exception for all KiteFS errors. Users can catch this for a catch-all handler. All subclasses inherit from this.

---

### 4.2 `ConfigurationError`

```python
class ConfigurationError(KiteFSError): ...
```

Raised when `kitefs.yaml` is missing, malformed, or contains invalid values.

| When raised | By | Conditions |
| --- | --- | --- |
| `FeatureStore.__init__()` | BB-10 | `kitefs.yaml` not found, YAML syntax error, missing required fields (`provider`, `storage_root`), unsupported provider value, AWS fields missing when `provider: aws`, environment variable with invalid value |

_(FR-CFG-003, FR-CFG-004)_

---

### 4.3 `DefinitionError`

```python
class DefinitionError(KiteFSError): ...
```

Raised when feature group definitions are structurally invalid. Carries all collected errors (KTD-9 — not fail-fast).

| When raised | By | Conditions |
| --- | --- | --- |
| `apply()` | BB-04 | No `FeatureGroup` instances found in `definitions/`; import failure in a definition file; duplicate feature group names; `EventTimestamp` dtype is not `DATETIME`; unsupported feature type; field name collision within a group (entity key, event timestamp, features); join key references non-existent group; join key field name doesn't match referenced entity key name; join key type mismatch |

_(FR-REG-002, FR-REG-004, FR-DEF-007, FR-OFF-004)_

---

### 4.4 `RegistryError`

```python
class RegistryError(KiteFSError): ...
```

Raised when the registry is unavailable or corrupted.

| When raised | By | Conditions |
| --- | --- | --- |
| Any SDK method that reads registry | BB-04 | Registry file not found (should not happen after `init`), registry JSON is malformed |

---

### 4.5 `FeatureGroupNotFoundError`

```python
class FeatureGroupNotFoundError(KiteFSError): ...
```

Raised when a referenced feature group does not exist in the registry.

| When raised | By | Conditions |
| --- | --- | --- |
| `ingest()`, `get_historical_features()`, `get_online_features()`, `materialize()`, `describe_feature_group()` | BB-02 via BB-04 | The named feature group is not in `registry.json` |

---

### 4.6 `ValidationError`

```python
class ValidationError(KiteFSError): ...
```

Base class for validation failures. Not raised directly — use the subclasses below.

---

### 4.7 `SchemaValidationError`

```python
class SchemaValidationError(ValidationError): ...
```

Raised when a DataFrame's columns do not match the expected schema.

| When raised | By | Conditions |
| --- | --- | --- |
| `ingest()`, `get_historical_features()` | BB-05 | Missing required columns; entity key column contains null values; event timestamp column contains null values. Mode-independent — always-ERROR semantics for schema issues. |

The error message lists all missing columns and null-column issues.

_(FR-ING-002, FR-ING-005)_

---

### 4.8 `DataValidationError`

```python
class DataValidationError(ValidationError): ...
```

Raised when data fails type checks or feature expectation checks in `ERROR` mode.

| When raised | By | Conditions |
| --- | --- | --- |
| `ingest()` (ingestion gate), `get_historical_features()` (retrieval gate) | BB-05 | Any record fails validation when the gate's mode is `ERROR`. Carries the full `ValidationReport` (passed count, failed count, per-failure details: entity key, field, expected constraint, actual value). |

_(FR-VAL-004, FR-VAL-007)_

---

### 4.9 `IngestionError`

```python
class IngestionError(KiteFSError): ...
```

Raised for ingestion-specific failures not covered by validation errors.

| When raised | By | Conditions |
| --- | --- | --- |
| `ingest()` | BB-02 | Unsupported input type (not DataFrame, CSV path, or Parquet path); file not found or unreadable |

_(FR-ING-001)_

---

### 4.10 `RetrievalError`

```python
class RetrievalError(KiteFSError): ...
```

Raised for retrieval parameter or state errors.

| When raised | By | Conditions |
| --- | --- | --- |
| `get_historical_features()` | BB-02 | `select` references features that don't exist; `where` uses unsupported field or operator for this method; `select` format invalid for the query type (e.g., list when `join` requires dict) |
| `get_online_features()` | BB-02 | Feature group is `OFFLINE` only; `select` references features that don't exist; `where` uses unsupported field or operator (not entity key / not `eq`) |

_(FR-OFF-002, FR-OFF-007, FR-ONL-002)_

---

### 4.11 `MaterializationError`

```python
class MaterializationError(KiteFSError): ...
```

Raised for materialization-specific failures.

| When raised | By | Conditions |
| --- | --- | --- |
| `materialize()` | BB-02 | Feature group's `storage_target` is `OFFLINE` only; no `OFFLINE_AND_ONLINE` groups found (when materializing all) |
| `get_online_features()` | BB-07 | Online store table does not exist for the group (i.e., `materialize()` has never been run). Error message: "No online data for '{name}'. Run `kitefs materialize` first." |

_(FR-MAT-002, FR-ONL-002)_

---

### 4.12 `JoinError`

```python
class JoinError(KiteFSError): ...
```

Raised when a join cannot be executed due to invalid configuration.

| When raised | By | Conditions |
| --- | --- | --- |
| `get_historical_features()` | BB-02 | No valid join path exists between the base group and a joined group (no matching join key declared); `join` contains more than one group (MVP limit — FR-OFF-009) |

_(FR-OFF-008, FR-OFF-009)_

---

### 4.13 `ProviderError`

```python
class ProviderError(KiteFSError): ...
```

Raised when the underlying storage backend fails. Wraps provider-specific exceptions with KiteFS context.

| When raised | By | Conditions |
| --- | --- | --- |
| Any storage operation | BB-09 | Disk full; S3 permission denied; DynamoDB throttling (after retry exhaustion); SQLite corruption; SQLite table not found; AWS credentials not configured; network errors |

Carries context: which operation, which storage path, and the original exception.

_(FR-PROV-001)_

---

## 5. Internal Module Interfaces

> _These are the contracts between building blocks. Each interface
> is expressed as Python Protocol/ABC-style signatures. A developer
> implementing a building block programs against these interfaces._
>
> _Organized by dependency tier (Tier 0 → Tier 2). BB-01 (CLI) and
> BB-02 (SDK) are consumers of these interfaces, not providers —
> their contracts are defined in §2 and §3._

---

### 5.1 Configuration Manager (BB-10) — Tier 0

**Module responsibility:** Loads, validates, and exposes `kitefs.yaml` settings.

```python
def load_config(project_root: Path) -> Config: ...
```

| Parameter | Type | Description |
| --- | --- | --- |
| `project_root` | `Path` | Directory containing `kitefs.yaml` |
| **Returns** | `Config` | Validated configuration object |
| **Raises** | `ConfigurationError` | On any configuration issue (see §4.2) |

**`Config` object** exposes the following attributes:

| Attribute | Type | Description |
| --- | --- | --- |
| `provider` | `str` | Active provider name (`"local"` or `"aws"`) |
| `project_root` | `Path` | Absolute path to the project root |
| `storage_root` | `Path` | Absolute path to the storage root (resolved from `kitefs.yaml`) |
| `definitions_path` | `Path` | Absolute path to `definitions/` directory |
| `aws` | `AWSConfig \| None` | AWS-specific config (only when `provider="aws"`) |

**`AWSConfig`** (when `provider: aws`):

| Attribute | Type | Description | Traces To |
| --- | --- | --- | --- |
| `s3_bucket` | `str` | S3 bucket name for offline store and registry | FR-CFG-002 |
| `s3_prefix` | `str` | S3 key prefix | FR-CFG-002 |
| `dynamodb_table_prefix` | `str` | DynamoDB table name prefix for online store | FR-CFG-002 |

**Environment variable overrides** (FR-CFG-005):

| Variable | Overrides |
| --- | --- |
| `KITEFS_PROVIDER` | `provider` |
| `KITEFS_STORAGE_ROOT` | `storage_root` |
| `KITEFS_AWS_S3_BUCKET` | `aws.s3_bucket` |
| `KITEFS_AWS_S3_PREFIX` | `aws.s3_prefix` |
| `KITEFS_AWS_DYNAMODB_TABLE_PREFIX` | `aws.dynamodb_table_prefix` |

_(FR-CFG-001, FR-CFG-002, FR-CFG-003, FR-CFG-004, FR-CFG-005, FR-CFG-006)_

---

### 5.2 Definition Module (BB-03) — Tier 0

No callable interface. BB-03 provides **type definitions** only (§1.2 and §1.3). All other modules import these types for schema metadata and isinstance checks.

---

### 5.3 Validation Engine (BB-05) — Tier 0

**Module responsibility:** Stateless schema and data validator. No dependencies, no I/O, no side effects.

```python
def validate_schema(
    definition: FeatureGroup,
    df: DataFrame,
) -> ValidationReport: ...
```

Checks that the DataFrame's columns match the schema derived from the definition (`entity_key.name`, `event_timestamp.name`, all `feature.name`). Extra columns are silently dropped. Null values in entity key or event timestamp columns are reported as failures.

| Parameter | Type | Description |
| --- | --- | --- |
| `definition` | `FeatureGroup` | The feature group definition |
| `df` | `DataFrame` | Input DataFrame to validate |
| **Returns** | `ValidationReport` | Schema validation result |
| **Raises** | `SchemaValidationError` | If missing columns or null structural columns detected |

---

```python
def validate_data(
    definition: FeatureGroup,
    df: DataFrame,
    mode: ValidationMode,
) -> tuple[ValidationReport, DataFrame]: ...
```

Validates feature values (type checks + expectation enforcement) according to the specified mode.

| Parameter | Type | Description |
| --- | --- | --- |
| `definition` | `FeatureGroup` | The feature group definition |
| `df` | `DataFrame` | DataFrame that has passed schema validation |
| `mode` | `ValidationMode` | `ERROR`, `FILTER`, or `NONE` |
| **Returns** | `tuple[ValidationReport, DataFrame]` | Report and (in FILTER mode) the filtered DataFrame. In ERROR mode with failures, raises instead of returning. In NONE mode, returns the report as a no-op pass-all. |
| **Raises** | `DataValidationError` | In ERROR mode, if any record fails validation |

**`ValidationReport`** describes the following:
- Total record count
- Passed count
- Failed count
- Per-failure details: entity key value (where available), failing field name, expected constraint, actual value

_(FR-VAL-001, FR-VAL-002, FR-VAL-003, FR-VAL-004, FR-VAL-005, FR-VAL-006, FR-VAL-007, FR-VAL-008)_

---

### 5.4 Join Engine (BB-08) — Tier 0

**Module responsibility:** Point-in-time correct joins. Stateless, no I/O, no dependencies.

```python
def pit_join(
    base_df: DataFrame,
    joined_df: DataFrame,
    base_join_field: str,
    joined_entity_key: str,
    left_timestamp: str,
    right_timestamp: str,
    joined_group_name: str,
) -> DataFrame: ...
```

| Parameter | Type | Description |
| --- | --- | --- |
| `base_df` | `DataFrame` | Base group data (defines output cardinality) |
| `joined_df` | `DataFrame` | Joined group data |
| `base_join_field` | `str` | Column name in `base_df` used for joining (the join key) |
| `joined_entity_key` | `str` | Column name in `joined_df` used for joining (the entity key) |
| `left_timestamp` | `str` | Event timestamp column name in `base_df` |
| `right_timestamp` | `str` | Event timestamp column name in `joined_df` |
| `joined_group_name` | `str` | Name of the joined group (used for column conflict resolution) |
| **Returns** | `DataFrame` | Merged DataFrame with PIT-correct joins |

**Behavioral contract:**
- Both DataFrames are sorted by their respective timestamp columns internally before the join
- For each base row, selects the most recent joined row where `joined.event_timestamp ≤ base.event_timestamp` AND join key matches
- Unmatched base rows are preserved with null-filled joined columns _(FR-OFF-005)_
- Column name conflicts: conflicting joined columns are prefixed with `{joined_group_name}_`. Base columns are never renamed. The joined event timestamp is always prefixed (it always conflicts). The join key column is not duplicated. _(FR-OFF-010)_
- Implementation: `pd.merge_asof` with `direction='backward'` _(KTD-13)_

_(FR-OFF-003, FR-OFF-005, FR-OFF-010)_

---

### 5.5 Provider Layer (BB-09) — Tier 1

**Module responsibility:** Abstract interface for all storage I/O. The only formal ABC in the system. _(KTD-14)_

```python
from abc import ABC, abstractmethod

class StorageProvider(ABC):

    # --- Offline Store ---

    @abstractmethod
    def write_offline(
        self,
        group_name: str,
        partition_path: str,
        file_name: str,
        df: DataFrame,
    ) -> None: ...

    @abstractmethod
    def read_offline(
        self,
        group_name: str,
        partition_paths: list[str],
    ) -> DataFrame: ...

    @abstractmethod
    def list_partitions(
        self,
        group_name: str,
    ) -> list[str]: ...

    # --- Online Store ---

    @abstractmethod
    def write_online(
        self,
        group_name: str,
        df: DataFrame,
    ) -> None: ...

    @abstractmethod
    def read_online(
        self,
        group_name: str,
        entity_key_name: str,
        entity_key_value: Any,
    ) -> dict | None: ...

    # --- Registry ---

    @abstractmethod
    def write_registry(
        self,
        data: str,
    ) -> None: ...

    @abstractmethod
    def read_registry(self) -> str: ...
```

**Method contracts:**

| Method | Input | Output | Atomicity | Notes |
| --- | --- | --- | --- | --- |
| `write_offline` | Group name, partition path (e.g., `year=2024/month=03`), file name, DataFrame | `None` | Atomic per file (write-to-temp-rename on local; `put_object` on S3) | Creates directories/prefixes lazily |
| `read_offline` | Group name, list of partition paths | `DataFrame` (combined from all files in those partitions) | — | Returns empty DataFrame if no files exist |
| `list_partitions` | Group name | `list[str]` of available partition paths | — | Used for partition pruning |
| `write_online` | Group name, DataFrame (latest-per-entity rows) | `None` | Fully atomic (SQLite transaction; DynamoDB `TransactWriteItems`). Full overwrite: delete all existing → insert new. | NFR-REL-002 |
| `read_online` | Group name, entity key name, entity key value | `dict \| None` | — | `None` if entity not found. Raises `ProviderError` if table does not exist. |
| `write_registry` | JSON string | `None` | Atomic (write-to-temp-rename on local; `put_object` on S3) | — |
| `read_registry` | — | JSON string | — | Raises `ProviderError` if file does not exist |

**Implementations:**

| | `LocalProvider` | `AWSProvider` |
| --- | --- | --- |
| Offline | PyArrow ↔ filesystem (Parquet) | PyArrow ↔ boto3 ↔ S3 (Parquet) |
| Online | `sqlite3` (Python stdlib) | `boto3` DynamoDB |
| Registry | Standard file I/O | `boto3` S3 client |
| Credentials | None required | Standard AWS credential chain |

**Error handling:** All provider methods wrap underlying exceptions (OSError, botocore.ClientError, sqlite3.DatabaseError) in `ProviderError` with context (operation, path/key, original exception).

_(FR-PROV-001, FR-PROV-002, FR-PROV-003, FR-PROV-004, FR-PROV-005)_

---

### 5.6 Registry Manager (BB-04) — Tier 2

**Module responsibility:** Definition discovery, validation, registry lifecycle, and lookups.

```python
class RegistryManager:

    def __init__(self, provider: StorageProvider, definitions_path: Path) -> None: ...

    def apply(self) -> ApplyResult: ...

    def get_group(self, name: str) -> FeatureGroup: ...

    def list_groups(self) -> list[dict]: ...

    def group_exists(self, name: str) -> bool: ...

    def update_materialized_at(self, name: str, timestamp: datetime) -> None: ...

    def validate_query_params(
        self,
        from_: str,
        select: list[str] | str | dict[str, list[str] | str],
        where: dict[str, dict[str, Any]] | None,
        join: list[str] | None,
        method: str,
    ) -> None: ...
```

| Method | Description | Raises |
| --- | --- | --- |
| `__init__` | Receives provider and definitions path. Loads registry from provider into memory. | `ProviderError` |
| `apply()` | Discover `FeatureGroup` instances in `definitions/`, validate, regenerate `registry.json` via provider. All-or-nothing with collected errors. | `DefinitionError`, `ProviderError` |
| `get_group(name)` | Returns `FeatureGroup` from in-memory registry. | `FeatureGroupNotFoundError` |
| `list_groups()` | Returns list of summary dicts from in-memory registry. | — |
| `group_exists(name)` | Returns `True` if the group exists in the registry. | — |
| `update_materialized_at(name, timestamp)` | Sets `last_materialized_at` for a group and persists registry. Called by BB-02 after successful materialization. | `FeatureGroupNotFoundError`, `ProviderError` |
| `validate_query_params(...)` | Validates `select`, `where`, and `join` parameters against definitions. Checks: group existence, feature existence, where field + operator allowed for the method, join path validity, single-join limit. `method` is `"get_historical_features"` or `"get_online_features"` to apply per-method restrictions. | `FeatureGroupNotFoundError`, `RetrievalError`, `JoinError` |

**Discovery mechanism:** `importlib` dynamic import of `.py` files under `definitions/`. Module-level `FeatureGroup` instances found via `isinstance` checks. `__init__.py` is skipped. _(KTD-8, FR-REG-003)_

---

### 5.7 Offline Store Manager (BB-06) — Tier 2

**Module responsibility:** Partition derivation, file naming, append-only writes, partition-pruned reads.

```python
class OfflineStoreManager:

    def __init__(self, provider: StorageProvider) -> None: ...

    def write(
        self,
        group_name: str,
        df: DataFrame,
        source_prefix: str = "ing",
    ) -> WriteResult: ...

    def read(
        self,
        group_name: str,
        where: dict[str, dict[str, Any]] | None = None,
        upper_bound: datetime | None = None,
    ) -> DataFrame: ...
```

| Method | Description | Raises |
| --- | --- | --- |
| `write(group_name, df, source_prefix)` | Derives partitions from `event_timestamp`, generates file names (`{source}_{YYYYMMDDTHHMMSS}_{short_id}.parquet`), writes Parquet files via provider. Append-only. | `ProviderError` |
| `read(group_name, where, upper_bound)` | Lists partitions, applies partition pruning (from `where` time range or `upper_bound`), reads Parquet via provider, applies row-level where filter. Returns empty DataFrame if no data exists. | `ProviderError` |

**Partition derivation:** `event_timestamp → year=YYYY/month=MM/`. Records in a single ingestion may span multiple partitions.

**File naming:** `{source_prefix}_{YYYYMMDDTHHMMSS}_{short_id}.parquet`. The `source_prefix` is informational only — all `.parquet` files in a partition are read regardless of prefix. _(FR-ING-006, FR-ING-007)_

**Partition pruning:**
- For `where` time range: only partitions that could contain matching records are read
- For `upper_bound`: only partitions up to the month containing the upper bound are read (used for joined groups during `get_historical_features`)

_(FR-ING-004, FR-ING-006, FR-ING-007, FR-OFF-001)_

---

### 5.8 Online Store Manager (BB-07) — Tier 2

**Module responsibility:** Latest-per-entity extraction, entity key lookup, full-overwrite write semantics.

```python
class OnlineStoreManager:

    def __init__(self, provider: StorageProvider) -> None: ...

    def materialize(
        self,
        group_name: str,
        df: DataFrame,
    ) -> MaterializeGroupResult: ...

    def get(
        self,
        group_name: str,
        entity_key_name: str,
        entity_key_value: Any,
        select: list[str] | None = None,
    ) -> dict | None: ...
```

| Method | Description | Raises |
| --- | --- | --- |
| `materialize(group_name, df)` | Extracts latest record per entity key (group by entity key, max `event_timestamp`). Delegates full-overwrite write to provider. Returns count of entity keys written. | `ProviderError` |
| `get(group_name, entity_key_name, entity_key_value, select)` | Delegates key-based lookup to provider. Applies `select` to limit returned features. Structural columns always included. | `MaterializationError` (if table doesn't exist), `ProviderError` |

**Latest-per-entity extraction:** `df.sort_values(event_timestamp).groupby(entity_key).last()` — produces exactly one row per entity key.

**BB-02 is responsible for:** extracting entity key name/value from the user-facing `where` dict before calling `get()`. BB-07 receives resolved values, not the raw `where` dict.

_(FR-MAT-001, FR-MAT-003, FR-MAT-005, FR-ONL-002)_

---

## 6. Cross-Cutting Contracts

> _Rules that apply across all sections of this document and across
> all building blocks. These are the shared invariants that every
> implementer must respect._

---

### 6.1 Structural Columns Rule

Entity key and event timestamp are **always included** in query results, regardless of the `select` parameter. This applies to both `get_historical_features()` and `get_online_features()`.

- `get_historical_features()` returns a DataFrame that always contains the entity key and event timestamp columns of the base group, plus (when joining) the joined group's event timestamp (prefixed per FR-OFF-010)
- `get_online_features()` returns a dict that always contains the entity key and event timestamp fields

Users cannot exclude structural columns. They can be relied upon for verification, debugging, and downstream processing.

_(FR-OFF-002, FR-ONL-002)_

---

### 6.2 Timestamp Convention

All timestamps in KiteFS are **timezone-naive** and **interpreted as UTC**. This applies to:
- `event_timestamp` values in ingested data and query results
- `applied_at` and `last_materialized_at` in the registry
- File-name timestamps in Parquet file names
- `where` filter values provided by users

KiteFS does not perform timezone conversion. Users are responsible for ensuring their data uses a consistent timezone convention. The system stores and compares timestamps as-is.

Timestamp precision: microsecond (`timestamp[us]` in PyArrow, `datetime64[us]` in Pandas).

---

### 6.3 Type Mapping

The authoritative type mapping across all storage technologies:

| `FeatureType` | PyArrow | Pandas dtype | Python type | SQLite | DynamoDB |
| --- | --- | --- | --- | --- | --- |
| `STRING` | `pa.string()` | `object` (str) | `str` | `TEXT` | `S` |
| `INTEGER` | `pa.int64()` | `int64` | `int` | `INTEGER` | `N` |
| `FLOAT` | `pa.float64()` | `float64` | `float` | `REAL` | `N` |
| `DATETIME` | `pa.timestamp('us')` | `datetime64[us]` | `datetime` | `TEXT` (ISO 8601) | `S` (ISO 8601) |

This table is the single source of truth referenced by BB-05 (type validation), BB-06 (Parquet writes), BB-07 (online store writes), and BB-09 (both providers).

_(Source: [docs-03-02 §3.2](docs-03-02-internals-and-data.md))_

---

### 6.4 Null Representation

| Context | Null Representation |
| --- | --- |
| Offline store (Parquet) | Native Parquet null |
| Online store (SQLite) | SQL `NULL` |
| Online store (DynamoDB) | Attribute omitted (DynamoDB does not store null values by default) |
| DataFrames (Pandas) | `NaN` for numeric, `None`/`NaT` for string/datetime |
| `get_online_features()` dict | `None` for missing values in the returned dict |
| PIT join unmatched columns | `NaN` in the returned DataFrame _(FR-OFF-005)_ |

The system does not convert between null representations — each storage layer uses its native representation. Pandas handles conversion automatically when reading from Parquet or SQLite.

---

### 6.5 Unified `where` Format Reference

The `where` parameter uses the same dict-of-dicts format across all SDK retrieval methods:

```python
where = {
    "field_name": {
        "operator": value,
    }
}
```

**Full operator set:**

| Operator | Meaning | Value type |
| --- | --- | --- |
| `eq` | Equals | Scalar |
| `in` | In a list | `list` |
| `gt` | Greater than | Scalar |
| `gte` | Greater than or equal | Scalar |
| `lt` | Less than | Scalar |
| `lte` | Less than or equal | Scalar |

Multiple operators on the same field combine with AND semantics.

**Per-method MVP restrictions:**

| Method | Allowed fields | Allowed operators |
| --- | --- | --- |
| `get_historical_features()` | `event_timestamp` only | `gt`, `gte`, `lt`, `lte` |
| `get_online_features()` | Entity key field only | `eq` only |

These restrictions are enforced by BB-04's `validate_query_params()`. The format itself supports arbitrary fields and operators — relaxing restrictions requires only changing validation rules, not the API signature. _(FR-OFF-007)_
