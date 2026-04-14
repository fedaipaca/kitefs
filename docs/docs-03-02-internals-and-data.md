# Kite Feature Store — Building Block Internals & Data Architecture

> **Document Purpose:**
> This document is the companion to [docs-03-01 Architecture Overview](docs-03-01-architecture-overview.md).
> Where docs-03-01 answers "what are the pieces and how do they work
> together?", this document answers "what's inside each piece?" and
> "what do the data storage contracts look like?"
>
> This is the document a developer reads before implementing a
> specific building block or working with the data layer.
>
> **Structure:**
> - §1 — Conventions that apply across all building blocks
> - §2 — Building block internals: one subsection per block
> - §3 — Data architecture: storage layouts, schemas, access patterns
> - §4 — Known limitations and future considerations
>
> **Relationship to other documents:**
> - Companion to: [docs-03-01](docs-03-01-architecture-overview.md) (design principles, Level 1–Level 3, packaging)
> - Built on: [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md), [Requirements (docs-02)](docs-02-project-requirements.md), [Reference Use Case (docs-00-01)](docs-00-01-reference-use-case.md)
> - Feeds into: [API Contracts (docs-03-03)](docs-03-03-api-contracts.md), [Implementation Guide (docs-04)](docs-04-implementation-guide.md)
>
> **How to read this document:**
> §2 and §3 are designed as reference sections — you can jump
> directly to the subsection you need. A developer
> implementing the offline store can read §2's offline store subsection
> + §3's offline store layout and have everything they need. Cross-
> references connect to related sections rather than duplicating content.
>
> **Owner:** Fedai Paça
> **Last Updated:** 2026-03-31
> **Status:** Draft

---

## 1. Conventions

This section establishes conventions that apply across all building block descriptions in §2. It is a reference header, not a design section.

### 1.1 Naming and Identification

Building blocks use the **BB-XX** identifiers defined in [docs-03-01 §3.2](docs-03-01-architecture-overview.md). The ten building blocks are:

| ID | Building Block |
| --- | --- |
| BB-01 | CLI |
| BB-02 | SDK (`FeatureStore`) |
| BB-03 | Definition Module |
| BB-04 | Registry Manager |
| BB-05 | Validation Engine |
| BB-06 | Offline Store Manager |
| BB-07 | Online Store Manager |
| BB-08 | Join Engine |
| BB-09 | Provider Layer |
| BB-10 | Configuration Manager |

### 1.2 Dependency Direction

Dependencies flow strictly downward through four layers: **Entry Points → Core Logic → Infrastructure → Foundation**. No circular dependencies exist. The full dependency graph and build tiers are documented in [docs-03-01 §3.3](docs-03-01-architecture-overview.md). This document does not repeat those relationships — each building block subsection states only its own direct dependencies.

### 1.3 Interface Style

- **Most blocks** expose their capabilities via **direct imports**. The SDK (BB-02) imports and instantiates core modules directly. No dependency injection framework is used — the SDK constructs dependencies in its `__init__` method and passes them explicitly (constructor injection by hand).
- **The Provider Layer (BB-09)** is the exception: it defines an **abstract base class** (`abc.ABC` with `@abstractmethod`) that `LocalProvider` and `AWSProvider` implement. This is the only formal interface contract in the system. The rationale is documented in KTD-14 (§2.9).

### 1.4 Subsection Structure

Each building block subsection in §2 follows a consistent template. Not every block uses every section — simple blocks include only the sections that add value:

- **Responsibility** — what the block does and does NOT do
- **Internal Structure** — key components (table format for complex blocks)
- **Behavioral Rules** — implementation-critical rules and ordering constraints
- **Interface Contract** — what the block exposes and depends on (intent-level, not signatures)
- **Architectural Decisions** — KTDs for non-obvious choices (continues from KTD-6; docs-03-01 ends at KTD-5)
- **Error Scenarios** — what can go wrong and how it's signaled
- **Complex Algorithm** — only for BB-08 (Join Engine)

---

## 2. Building Block Internals

> _One subsection per building block from [docs-03-01 §3](docs-03-01-architecture-overview.md).
> Each subsection follows the structure defined in §1.4._

### 2.1 CLI (BB-01)

**Responsibility:**

Parses command-line arguments via Click, resolves the project root directory (by locating `kitefs.yaml`), delegates to the SDK (`FeatureStore`) for all operations, and renders console output (tables, JSON, success/error messages).

The CLI does NOT contain domain logic. The single exception is `kitefs init`, which creates the project scaffold before a `FeatureStore` can be instantiated — there is no `kitefs.yaml` yet for the SDK to load. This exception is documented in [KTD-4 (docs-03-01)](docs-03-01-architecture-overview.md).

**Behavioral Rules:**

- All commands except `init` follow the same pattern: resolve project root → instantiate `FeatureStore` → call the corresponding SDK method → render output → exit.
- `kitefs init` is self-contained within BB-01. It creates `kitefs.yaml`, the directory scaffold, seeds `registry.json`, and creates/appends `.gitignore`. See [docs-03-01 §4.2](docs-03-01-architecture-overview.md) for the full flow.
- Exit codes: `0` for success, non-zero for failure.
- Error messages are rendered to stderr in plain text. Python tracebacks are suppressed in normal operation.
- The CLI supports `--format json` for machine-readable output on inspection commands (`list`, `describe`) and `--target <path>` for file output. These parameters are passed through to the SDK — the CLI does not implement serialization logic (KTD-4).

**Error Scenarios:**

The CLI is the outermost error boundary — it catches all exceptions from the SDK and translates them into user-facing output. Python tracebacks are never exposed in normal operation.

| Scenario | Source | CLI Behavior |
| --- | --- | --- |
| `kitefs.yaml` not found when resolving project root | BB-01 (own logic) | Error: "No KiteFS project found. Run `kitefs init` to create one." Exit 1. |
| Project already initialized | BB-01 (`init` logic) | Error: "KiteFS project already initialized at this location." Exit 1. |
| SDK method raises any domain exception | BB-02 → core blocks | Render the exception message to stderr. Exit 1. |
| Unexpected exception | Any | Render a generic error message. Exit 1. In debug mode (future), show traceback. |

---

### 2.2 SDK / FeatureStore (BB-02)

**Responsibility:**

User-facing Python class that orchestrates every operation by calling core modules in the correct sequence. The SDK is the integration point — it wires modules together and defines the calling order documented in the operational flows ([docs-03-01 §4](docs-03-01-architecture-overview.md)).

The SDK does NOT contain domain logic. It does not validate definitions (BB-04), validate data (BB-05), manage storage layout (BB-06/BB-07), perform joins (BB-08), or interact with storage directly (BB-09). It calls the module that does.

**Internal Structure:**

| Component | Responsibility | Notes |
| --- | --- | --- |
| `FeatureStore.__init__` | Initialization sequence: load config (BB-10), instantiate provider (BB-09), create core module instances with provider injected | Constructor injection — no DI framework |
| `apply()` | Orchestrate definition discovery and registry regeneration | Delegates to BB-04 |
| `ingest(name, data)` | Orchestrate ingestion: look up definition → resolve input to DataFrame → schema validation → data validation → offline write | Delegates to BB-04 (lookup), BB-05 (validation), BB-06 (write) |
| `get_historical_features(...)` | Orchestrate historical retrieval: validate params → read → select → validate → join | Delegates to BB-04, BB-06, BB-05, BB-08 |
| `get_online_features(...)` | Orchestrate online lookup: validate params → read from online store | Delegates to BB-04, BB-07 |
| `materialize(name=None)` | Orchestrate materialization: resolve targets → read offline → extract latest → write online → update registry (`last_materialized_at`) | Delegates to BB-04, BB-06, BB-07 |
| `list_feature_groups(...)` | Query registry and format output | Delegates to BB-04 |
| `describe_feature_group(...)` | Look up single group and format output | Delegates to BB-04 |

**Behavioral Rules:**

- The constructor is the only place where module wiring occurs. All core modules receive their dependencies at construction time.
- Each public method maps to exactly one operational flow in [docs-03-01 §4](docs-03-01-architecture-overview.md). The method implements the sequence shown in the corresponding flow diagram.
- The SDK catches domain exceptions from core modules, adds operation-level context (which operation, which feature group), and re-raises. It does not swallow exceptions.
- The SDK exposes Pandas DataFrames as the data exchange format for `ingest()` and `get_historical_features()`, and `dict | None` for `get_online_features()` (FR-ONL-002).

**Interface Contract:**

- **Exposes to consumers (users):** The public API surface — one class (`FeatureStore`) with methods for each operation. This is what users import and call.
- **Depends on:** BB-10 (config), BB-09 (provider — instantiated, then injected into core modules), BB-04 (registry), BB-05 (validation), BB-06 (offline), BB-07 (online), BB-08 (joins).

**Error Scenarios:**

The SDK does not define its own exception types. It is the error propagation seam: it catches domain exceptions from core blocks, adds operation-level context (e.g., "during ingest of feature group 'listing_features'"), and re-raises. This ensures that every error a user sees includes both the root cause (from the core block) and the operation context (from the SDK).

| Scenario | Source | SDK Behavior |
| --- | --- | --- |
| Configuration invalid at construction | BB-10 | `ConfigurationError` propagated — `FeatureStore` cannot be instantiated |
| Feature group not found for any operation | BB-04 | `RegistryError` propagated with group name context |
| Validation failure during ingest or retrieval | BB-05 | `ValidationError` propagated with operation context |
| Storage I/O failure | BB-09 | `ProviderError` propagated with operation context |

---

### 2.3 Definition Module (BB-03)

**Responsibility:**

Provides the foundational data model for KiteFS — the Python types that users write in `definitions/` files and that all other modules reference for schema metadata. This module defines `FeatureGroup`, `EntityKey`, `EventTimestamp`, `Feature`, `Expect`, `StorageTarget`, `JoinKey`, `FeatureType`, and `ValidationMode`.

The Definition Module does NOT validate definitions — structural validation of `FeatureGroup` objects is BB-04's (Registry Manager) responsibility. The Definition Module does NOT persist definitions — they live as `.py` files in Git, version-controlled alongside application code (AP-4).

**Internal Structure:**

| Component | Responsibility | Notes |
| --- | --- | --- |
| `FeatureGroup` | Top-level definition type. Holds name, `entity_key` (single `EntityKey`), `event_timestamp` (single `EventTimestamp`), `features` (tuple of `Feature` instances, sorted by name — see KTD-16), storage target, join keys, validation modes, metadata (`Metadata` instance). | Frozen dataclass (KTD-6) |
| `EntityKey` | Structural column: the entity's unique identifier. Required constructor parameter — exactly one per group enforced by the type system. Holds name, dtype, optional description. Does not accept expectations. Always included in query results regardless of `select`. | Frozen dataclass. Implicitly not-null. |
| `EventTimestamp` | Structural column: the temporal anchor for PIT joins and partitioning. Required constructor parameter — exactly one per group enforced by the type system. Holds name, dtype (must be `DATETIME`), optional description. Does not accept expectations. Always included in query results regardless of `select`. | Frozen dataclass. Implicitly not-null. |
| `Feature` | A data field — model feature, label, or join key field. Holds name, dtype, optional description, optional `Expect`. | Frozen dataclass. |
| `Expect` | Fluent builder for feature expectations. Methods: `.not_null()`, `.gt(v)`, `.gte(v)`, `.lt(v)`, `.lte(v)`, `.one_of(v)`. Each method returns a new `Expect` instance (immutable). Internal representation: tuple of dicts (normalized in `__post_init__`, consistent with `features` — see KTD-16). | Frozen dataclass. Serializable via `dataclasses.asdict()`. |
| `FeatureType` | Enum: `STRING`, `INTEGER`, `FLOAT`, `DATETIME`. | Maps to storage types in §3.2 |
| `StorageTarget` | Enum: `OFFLINE`, `OFFLINE_AND_ONLINE`. | FR-DEF-003 |
| `ValidationMode` | Enum: `ERROR`, `FILTER`, `NONE`. | FR-VAL-003 |
| `JoinKey` | Declares a field in this group that references another group's entity key. Holds field name and referenced group name. | FR-OFF-004 |
| `Metadata` | Structured metadata for a feature group. Holds `description: str \| None`, `owner: str \| None`, `tags: dict[str, str] \| None`. All fields default to `None`. The `FeatureGroup` constructor defaults `metadata` to `Metadata()`, so the parameter can be omitted entirely. | Frozen dataclass (KTD-6). FR-DEF-006. `tags` is `dict` for ergonomics — technically mutable inside a frozen dataclass, but acceptable for write-once-read-many definitions. |

**Concrete example using the reference use case** ([docs-00-01](docs-00-01-reference-use-case.md)):

```python
# definitions/listing_features.py

from kitefs import FeatureGroup, Feature, EntityKey, EventTimestamp
from kitefs import FeatureType, StorageTarget, Expect
from kitefs import JoinKey, ValidationMode, Metadata

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(
        name="listing_id",
        dtype=FeatureType.INTEGER,
        description="Unique identifier for each listing",
    ),
    event_timestamp=EventTimestamp(
        name="event_timestamp",
        dtype=FeatureType.DATETIME,
        description="When the listing was sold",
    ),
    features=[
        Feature(name="net_area", dtype=FeatureType.INTEGER,
                description="Usable area in sqm",
                expect=Expect().not_null().gt(0)),
        Feature(name="number_of_rooms", dtype=FeatureType.INTEGER,
                description="Number of rooms",
                expect=Expect().not_null().gt(0)),
        Feature(name="build_year", dtype=FeatureType.INTEGER,
                description="Year the building was constructed",
                expect=Expect().not_null().gte(1900).lte(2030)),
        Feature(name="sold_price", dtype=FeatureType.FLOAT,
                description="Sold price in TL (training label)",
                expect=Expect().not_null().gt(0)),
        Feature(name="town_id", dtype=FeatureType.INTEGER,
                description="Join key to town_market_features"),
    ],
    join_keys=[
        JoinKey(field_name="town_id",
                referenced_group="town_market_features"),
    ],
    ingestion_validation=ValidationMode.ERROR,
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(
        description="Historical sold listing attributes and prices",
        owner="data-science-team",
        tags={"domain": "real-estate", "cadence": "monthly"},
    ),
)
```

```python
# definitions/town_market_features.py

from kitefs import FeatureGroup, Feature, EntityKey, EventTimestamp
from kitefs import FeatureType, StorageTarget, Expect
from kitefs import ValidationMode, Metadata

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(
        name="town_id",
        dtype=FeatureType.INTEGER,
        description="Unique town identifier",
    ),
    event_timestamp=EventTimestamp(
        name="event_timestamp",
        dtype=FeatureType.DATETIME,
        description="When this value became available",
    ),
    features=[
        Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT,
                description="Average sold price per sqm in this town last month",
                expect=Expect().not_null().gt(0)),
    ],
    ingestion_validation=ValidationMode.ERROR,
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(
        description="Monthly town-level market aggregate",
        owner="data-science-team",
        tags={"domain": "real-estate", "cadence": "monthly"},
    ),
)
```

**Behavioral Rules:**

- `FeatureGroup`, `EntityKey`, `EventTimestamp`, `Feature`, `Expect`, and `Metadata` instances are **immutable after creation** (frozen dataclasses). To change a definition, the user edits the `.py` source file and re-runs `apply()`. There is no programmatic mutation API.
- Default validation modes: `ingestion_validation` defaults to `ValidationMode.ERROR`, `offline_retrieval_validation` defaults to `ValidationMode.NONE` (FR-VAL-009, KTD-7). These defaults are constructor parameters — visible in the definition code and in the registry.
- `entity_key` and `event_timestamp` are **required constructor parameters** (FR-DEF-007, KTD-16). Omitting either produces a Python `TypeError` at definition time — not at `apply()`. This constraint is enforced by the type system, not by runtime validation.
- The `event_timestamp` parameter's dtype must be `DATETIME`. This is enforced by BB-04 during `apply()`. It is not configurable — the field must contain valid timestamps for partitioning and point-in-time joins to work.
- `EntityKey` and `EventTimestamp` are **structural columns** — they are always included in query results (`get_historical_features`, `get_online_features`) regardless of the `select` parameter. They do not accept expectations. They are always implicitly not-null — the system rejects records with null entity key or null event timestamp at schema validation (BB-05), regardless of validation mode.
- The `features` parameter accepts a list of `Feature` instances but is stored internally as a **tuple sorted alphabetically by `name`** (normalized in `__post_init__`). This makes `__eq__` and `dataclasses.asdict()` deterministic regardless of user-provided order (KTD-16).
- `dataclasses.asdict()` converts any definition to a plain dictionary for JSON serialization (used by BB-04 when writing the registry). The `entity_key` and `event_timestamp` attributes serialize as nested dicts; the `features` tuple serializes as a list of dicts. All nested types (`EntityKey`, `EventTimestamp`, `Feature`, `Expect`, `Metadata`, enums) are frozen dataclasses or enums that support `asdict()`.
- The `metadata` parameter is optional, defaulting to `Metadata()` (all fields `None`). A minimal `FeatureGroup` definition can omit metadata entirely. When present, `Metadata` provides structured access to `description`, `owner`, and `tags` — downstream modules (BB-04 for registry serialization, `list_feature_groups` for summary extraction) can access these fields directly without `dict.get()` fallbacks.
- Field names within a `FeatureGroup` must be unique across `entity_key.name`, `event_timestamp.name`, and all `feature.name` values. BB-04 enforces this during `apply()`.

**Interface Contract:**

- **Exposes:** Type definitions (`FeatureGroup`, `EntityKey`, `EventTimestamp`, `Feature`, `Expect`, `Metadata`, `FeatureType`, `StorageTarget`, `ValidationMode`, `JoinKey`) for use in definition files and by all other modules.
- **Depends on:** Nothing. BB-03 is a foundation module with zero dependencies.

**Architectural Decisions:**

---

**KTD-6: Definition Types as Frozen Dataclasses**

- **Context:** How should `FeatureGroup` and `Feature` be represented in Python? Users write these in definition files; BB-04 discovers them; BB-04 serializes them to JSON for the registry; multiple modules reference them for schema metadata.
- **Options considered:**
  - (A) *Plain classes with `__init__`:* Maximum flexibility. But verbose — users must write boilerplate constructors, and equality/repr behavior needs manual implementation.
  - (B) *Dataclasses (`@dataclass`):* Concise syntax, auto-generated `__init__`, `__repr__`, `__eq__`. `dataclasses.asdict()` handles JSON serialization. Mutable by default.
  - (C) *Frozen dataclasses (`@dataclass(frozen=True)`):* Same as (B) but immutable after creation. Prevents accidental mutation.
- **Decision:** (C) Frozen dataclasses.
- **Rationale:** AP-4 (definitions are code, not runtime-mutable state), AP-7 (stdlib only, no external dependency like attrs or pydantic). Immutability prevents a class of bugs where a module accidentally modifies a shared definition object. `dataclasses.asdict()` provides built-in serialization without custom logic.
- **Consequences:** Users cannot modify a `FeatureGroup` after creation. This is the intended behavior — definitions are declarative. To change a feature group, edit the `.py` source file and re-run `apply()`. All nested types (`EntityKey`, `EventTimestamp`, `Feature`, `Expect`, `JoinKey`, `Metadata`, enums) must be serializable via `asdict()` — frozen dataclasses and enums satisfy this. The `Expect` builder returns new instances on each method call, so the final object is a plain frozen dataclass holding a list of constraint dicts.
- **Revisit if:** User experience testing reveals that frozen dataclasses are too restrictive for common workflows. Unlikely — definitions are written once and read many times, not mutated at runtime.

---

**KTD-7: Validation Mode Defaults in the Definition**

- **Context:** Where should the default validation modes (ERROR for ingestion, NONE for retrieval, per FR-VAL-009) be applied? The defaults need to exist somewhere — the question is whether they're visible in the definition or hidden in the validation engine.
- **Options considered:**
  - (A) *In the `FeatureGroup` constructor as default parameter values:* The definition code shows the active modes. The registry contains the actual modes. No hidden behavior.
  - (B) *Applied by BB-05 (Validation Engine) when mode is not specified:* The definition can omit validation modes, and the engine fills in defaults at runtime.
- **Decision:** (A) Constructor defaults.
- **Rationale:** AP-4 (definitions are the source of truth). If a user reads a definition file and sees no validation mode specified, the constructor defaults make the behavior explicit — `ingestion_validation=ValidationMode.ERROR` and `offline_retrieval_validation=ValidationMode.NONE`. The registry always reflects the actual modes, whether explicitly set or defaulted.
- **Consequences:** Every definition in the registry has explicit validation modes. There is no difference between a "default" and an "explicitly set to the default value" definition. This eliminates ambiguity.
- **Revisit if:** New validation gates are added beyond ingestion and offline retrieval. The constructor signature would need to grow, but the principle remains sound.

---

**KTD-16: Structural Columns as Separate Parameters (Not a Mixed `fields` List)**

- **Context:** The original design used a single `fields` list containing a mix of `EntityKey`, `EventTimestamp`, and `Feature` instances. This raised several issues: (1) list ordering is significant for `__eq__` and `dataclasses.asdict()`, so reordering fields in the definition file could cause spurious registry diffs; (2) the "exactly one `EntityKey`, exactly one `EventTimestamp`" constraint could only be enforced at runtime (BB-04 during `apply()`), not by the type system; (3) the mixed-type list required a `field_type` discriminator in the registry JSON schema.
- **Options considered:**
  - (A) *Normalize inside the constructor:* Keep `fields` as a list, but sort it in `__post_init__` into a canonical order (EntityKey first, EventTimestamp second, Features sorted by name). Fixes ordering but still requires runtime validation for the exactly-one constraints.
  - (B) *Separate parameters:* Make `entity_key` and `event_timestamp` required top-level constructor parameters (each accepting exactly one instance), and `features` a separate list of `Feature` instances only.
- **Decision:** (B) Separate parameters.
- **Rationale:** AP-7 (constraints that can be enforced by structure should not rely on runtime validation). Making `entity_key` and `event_timestamp` required parameters means omitting either raises a Python `TypeError` at definition time — the developer gets immediate feedback from the IDE and interpreter, not a deferred `RegistryError` during `apply()`. This eliminates three BB-04 validation checks entirely (missing EntityKey, missing EventTimestamp, multiple of either). The `features` list contains only homogeneous `Feature` instances, making ordering clearly semantically irrelevant — sorted by name in `__post_init__` for determinism.
- **Consequences:** The registry JSON schema changes: `entity_key` and `event_timestamp` become top-level objects, `features` becomes a list of feature-only objects, and the `field_type` discriminator is removed (position in JSON structure encodes the type). The `FeatureGroup` constructor signature becomes self-documenting: a user reading the signature immediately understands that exactly one entity key and one event timestamp are required. Three BB-04 error scenarios are eliminated. FR-DEF-007 is now satisfied by the type system rather than runtime validation.
- **Revisit if:** A use case emerges that requires multiple entity keys or multiple event timestamps per feature group. Extremely unlikely for a feature store — these are fundamental structural constraints.

---

**Error Scenarios:**

BB-03 itself does not raise errors at runtime — it provides type definitions. Errors related to definitions are raised by BB-04 during `apply()` when it discovers and validates `FeatureGroup` instances. However, Python's `dataclass(frozen=True)` will raise `FrozenInstanceError` if code attempts to mutate a definition after creation — this is by design and surfaces as a standard Python error.

---

### 2.4 Registry Manager (BB-04)

**Responsibility:**

Manages the `registry.json` lifecycle: definition discovery (scanning `definitions/` for `FeatureGroup` instances), structural validation of definitions, full registry regeneration, persistence via the provider, and lookup queries for other modules.

The Registry Manager does NOT validate DataFrame data — that is BB-05's (Validation Engine) responsibility (KTD-5 in [docs-03-01](docs-03-01-architecture-overview.md)). It does NOT write Parquet files or interact with the offline/online stores. It reads and writes only the registry file, via BB-09.

**Internal Structure:**

| Component | Responsibility | Notes |
| --- | --- | --- |
| Discovery | Scans `definitions/` directory, dynamically imports `.py` modules via `importlib`, finds `FeatureGroup` instances via `isinstance` checks on module-level attributes | FR-REG-003 — no decorators or registration calls needed |
| Definition Validator | Structural checks on `FeatureGroup` objects: `EventTimestamp` dtype must be `DATETIME`, feature types from supported set, field names unique within group (across `entity_key`, `event_timestamp`, and `features`), join keys reference existing groups with matching types. Note: exactly-one constraints for `EntityKey` and `EventTimestamp` are enforced by the constructor signature (KTD-16) — BB-04 does not check these. | Operates on Python objects, not DataFrames |
| Registry Serializer | Converts validated definitions to deterministic JSON (`sort_keys=True`, `indent=2`) | FR-REG-001 — meaningful Git diffs |
| Registry Reader | Loads existing `registry.json` from the provider | Used by lookup methods |
| Lookup Methods | `get_group(name)`, `list_groups()`, `group_exists(name)` | Used by BB-02 for all operations that need a definition |

**Behavioral Rules:**

- **Full regeneration on every `apply()` (KTD-3 in [docs-03-01](docs-03-01-architecture-overview.md)).** The existing registry is ignored. All definitions are discovered, validated, and a new `registry.json` is written from scratch. Deleted definition files automatically vanish from the registry.
- **Discovery via `importlib` (KTD-8).** Each `.py` file under `definitions/` is imported into a fresh namespace. Module-level attributes are inspected with `isinstance(attr, FeatureGroup)`. No naming convention, decorator, or registration call is required.
- **Validation ordering:** Individual group validation runs first (`EventTimestamp` dtype is `DATETIME`, feature types from supported set, field names unique within group across `entity_key.name`, `event_timestamp.name`, and all `feature.name` values). Cross-group validation runs second (join key references valid — referenced group exists, join key field name matches referenced group's entity key name, join key field dtype matches referenced entity key dtype). This ordering ensures that cross-group validation can rely on individually valid groups.
- **All errors collected, not fail-fast (KTD-9).** If multiple definitions have issues, all errors are collected and reported together. The user fixes all issues in one pass. If any error exists, the registry remains unchanged.
- **Deterministic JSON output.** The registry uses `json.dumps(sort_keys=True, indent=2)`. Given the same set of definitions, the output is byte-for-byte identical. This enables meaningful Git diffs (FR-REG-001).
- **Lookup methods read from the loaded registry** (in-memory after first load), not from `definitions/`. The registry is the compiled source of truth for runtime operations (AP-4). Discovery and import only happen during `apply()`.

**Interface Contract:**

- **Exposes to BB-02:** `apply()` (discover + validate + regenerate), `get_group(name) → FeatureGroup`, `list_groups() → list[dict]`, `group_exists(name) → bool`, `validate_query_params(...)` (for `get_historical_features` and `get_online_features` — checks that requested groups, features, join paths, and `where` clauses are valid against the unified where format: field name must be in the allowed set for the method, operators must be in the allowed set for the method, and value types must match the field's declared type).
- **Depends on:** BB-03 (for `FeatureGroup` type and `isinstance` checks), BB-09 (for registry file read/write via the provider).

**Architectural Decisions:**

---

**KTD-8: Definition Discovery via importlib**

- **Context:** How does `apply()` find `FeatureGroup` instances in the `definitions/` directory? The discovery mechanism determines the developer experience of defining features.
- **Options considered:**
  - (A) *`importlib` dynamic import:* Walk `.py` files under `definitions/`, import each module, inspect module-level attributes with `isinstance(attr, FeatureGroup)`. No ceremony required from the user.
  - (B) *Explicit registration:* Users call `register(my_feature_group)` somewhere. Provides explicit control but adds boilerplate.
  - (C) *Decorator-based:* Users decorate classes or functions with `@feature_group`. Provides discoverability but couples definition syntax to the registration mechanism.
- **Decision:** (A) `importlib` dynamic import.
- **Rationale:** AP-4 (definitions as code — defining a `FeatureGroup` object is sufficient), FR-REG-003 (no decorators, naming conventions, or registration calls). The user experience is minimal friction: create a `.py` file, define a `FeatureGroup`, run `apply()`. No additional ceremony.
- **Consequences:** Any `FeatureGroup` instance at module level in any `.py` file under `definitions/` is automatically discovered. Users can organize definitions across multiple files freely. Import errors in definition files surface as clear `RegistryError` messages during `apply()`, including the file path and error details.
- **Revisit if:** Security concerns arise about executing arbitrary Python during `apply()`. This is acceptable for a developer tool — the user controls what's in `definitions/`. If KiteFS were ever exposed as a shared service (unlikely per AP-1), sandboxing would need consideration.

---

**KTD-9: All-or-Nothing Apply with Collected Errors**

- **Context:** When `apply()` encounters multiple invalid definitions, should it fail on the first error or collect all errors and report them together?
- **Options considered:**
  - (A) *Fail-fast:* Stop at the first error. Simple to implement but poor developer experience — the user fixes one issue, re-runs, discovers the next issue, repeat.
  - (B) *Collect all errors:* Continue validation after individual failures, collect all errors, report them together, then fail. The user fixes all issues in one pass.
- **Decision:** (B) Collect all errors.
- **Rationale:** AP-7 (single-developer sustainability — minimize the fix-rerun cycle). A single `apply()` run should surface every issue, not force iterative discovery.
- **Consequences:** The validation logic must be structured to continue processing after individual failures. Each validation check adds errors to a collection rather than raising immediately. After all checks complete, if the collection is non-empty, apply fails and reports all errors. The registry remains unchanged.
- **Revisit if:** The error collection complicates validation logic significantly. Unlikely — the checks are independent and naturally parallelizable.

---

**Error Scenarios:**

| Scenario | Error Type | Details |
| --- | --- | --- |
| Import failure in a definition file | `DefinitionError` | Includes file path and the original Python error (SyntaxError, ImportError, etc.) |
| Duplicate feature group names | `DefinitionError` | Lists all duplicates with their source file paths |
| Unsupported feature type | `DefinitionError` | Names the feature, the invalid type, and the list of supported types |
| Join key references non-existent group | `DefinitionError` | Names the source group, the join key field, and the missing referenced group |
| Join key type mismatch | `DefinitionError` | Names both groups, the field names, and the mismatched types |
| Join key field name differs from referenced entity key name | `DefinitionError` | "Join key 'location_id' in group 'listing_features' must match entity key name 'town_id' of referenced group 'town_market_features'. Rename the field to 'town_id'." |
| `EventTimestamp` dtype is not `DATETIME` | `DefinitionError` | "EventTimestamp field '{name}' must have dtype DATETIME, got {actual}." |
| Registry file write failure | `ProviderError` | Propagated from BB-09 (disk full, S3 permission denied, etc.) |

---

### 2.5 Validation Engine (BB-05)

**Responsibility:**

Stateless data validator that enforces schema and value constraints on DataFrames. Operates at two gates: **ingestion** (before data enters the offline store) and **offline retrieval** (before training data is returned from `get_historical_features()`). Supports three modes: `ERROR`, `FILTER`, `NONE`.

The Validation Engine does NOT validate `FeatureGroup` Python objects — that is BB-04's (Registry Manager) responsibility (KTD-5 in [docs-03-01](docs-03-01-architecture-overview.md)). It does NOT decide when to run — the caller (BB-02) invokes it at the appropriate gate with the appropriate mode.

**Internal Structure:**

| Component | Responsibility | Notes |
| --- | --- | --- |
| Schema Validator | Checks that a DataFrame's columns match the expected schema derived from the definition's `entity_key`, `event_timestamp`, and `features`: all required field names present. Extra columns (present in DataFrame but not in definition) are silently dropped. Additionally, checks that every row of the `entity_key` and `event_timestamp` columns is non-null — null structural column values are treated as schema failures. | Mode-independent — always ERROR semantics for missing columns and for null structural column values. Extra columns are dropped, not rejected. |
| Data Validator | Per-column type checking and per-feature expectation enforcement | Respects the configured mode (ERROR / FILTER / NONE) |
| Expectation Evaluators | Individual evaluation functions for each expectation type: `gt`, `gte`, `lt`, `lte`, `one_of`, `not_null` | Stateless functions that receive a Series and a constraint, return a boolean mask |
| Report Builder | Constructs a structured `ValidationReport`: pass count, fail count, per-failure details (entity key, field, expected, actual) | FR-VAL-007 |

**Behavioral Rules:**

- **Two-phase validation with hard gate.** Phase 1: schema validation. Phase 2: data validation. If schema validation fails (missing columns, misnamed columns), data validation is never reached — the operation aborts immediately. This is because data validation cannot run on columns that don't exist. Schema is a structural precondition. (See [docs-03-01 §4.4](docs-03-01-architecture-overview.md) observation.)
- **Schema validation is always ERROR semantics for missing columns and null structural column values.** Regardless of the configured mode, missing required columns cause immediate failure. The expected column set is derived from `entity_key.name`, `event_timestamp.name`, and each `feature.name` in the definition — all must be present in the DataFrame. **Extra columns** (present in the DataFrame but not declared in the definition) are silently dropped before proceeding to data validation. This tolerates common scenarios like helper columns left over from feature engineering or DataFrames with more columns than a single feature group needs. Additionally, any null value in the `entity_key` or `event_timestamp` column is a Phase 1 failure — treated identically to a missing column (mode-independent, always-ERROR). Rationale: (1) null `event_timestamp` values cannot be partitioned — `DERIVE_PARTITIONS` derives `year` and `month` from this column, so a null would cause a downstream crash rather than a clean error; (2) `Expect` is not available on structural columns (FR-DEF-004), so Phase 2 has no mechanism to enforce not-null on them regardless of mode. The mode setting (ERROR / FILTER / NONE) applies exclusively to data validation (Phase 2) of `Feature` fields.
- **Data validation respects the configured mode:**
  - `ERROR`: If any record fails any expectation, the entire operation is rejected. No data is written (ingestion) or returned (retrieval). A full validation report is included in the error.
  - `FILTER`: Failing records are excluded. Passing records proceed. The validation report documents what was filtered and why.
  - `NONE`: Data validation is skipped entirely. Schema validation still runs.
- **Validation report structure (FR-VAL-007):** Every validation run (in ERROR and FILTER modes) produces a `ValidationReport` containing: total record count, passed count, failed count, and for each failure: the entity key value (if available), the failing field name, the expected constraint, and the actual value.
- **Fully stateless.** The validation engine receives a schema definition (from `FeatureGroup`) and a DataFrame as function arguments. It returns a `ValidationReport` and (in FILTER mode) the filtered DataFrame. No internal state, no I/O, no side effects. This makes it trivially testable and reusable across both gates.
- **Type checking maps `FeatureType` to expected Pandas dtypes.** The mapping is defined in §3.2 (Type Mapping). The engine checks that each column's actual dtype is compatible with the declared `FeatureType`.

**Interface Contract:**

- **Exposes to BB-02:** `validate_schema(definition, df) → ValidationReport`, `validate_data(definition, df, mode) → (ValidationReport, filtered_df)`. The SDK calls `validate_schema` first; if it passes, calls `validate_data` with the configured mode.
- **Depends on:** Nothing. BB-05 is a stateless leaf module with zero module dependencies. It receives everything it needs as function arguments.

**Error Scenarios:**

| Scenario | Error Type | Details |
| --- | --- | --- |
| Missing required column(s) | `ValidationError` | Lists all missing columns. Operation aborts (schema failure). |
| Entity key column missing | `ValidationError` | Specific message identifying the expected entity key name. |
| Event timestamp column missing | `ValidationError` | Specific message. |
| Null value(s) in entity key column | `ValidationError` | Lists the count of null rows. Operation aborts (schema failure — mode-independent). |
| Null value(s) in event timestamp column | `ValidationError` | Lists the count of null rows. Operation aborts — null event timestamps cannot be partitioned. Mode-independent. |
| Type mismatch on a feature column | Captured in `ValidationReport` | The column exists but its dtype is incompatible with the declared `FeatureType`. Behavior depends on mode. |
| Feature expectation violation | Captured in `ValidationReport` | Per-record failures with entity key, field, constraint, and actual value. Behavior depends on mode. |

---

### 2.6 Offline Store Manager (BB-06)

**Responsibility:**

Orchestrates all offline store operations: deriving partition paths from event timestamps, naming Parquet files, performing append-only writes, reading data with partition pruning, and applying row-level where filters. All physical I/O is delegated to BB-09 (Provider Layer).

The Offline Store Manager does NOT validate data — that is BB-05's job, invoked by BB-02 before calling BB-06. It does NOT perform joins — that is BB-08's job. It does NOT interact with the online store — that is BB-07's domain.

**Internal Structure:**

| Component | Responsibility | Notes |
| --- | --- | --- |
| Partition Manager | Derives Hive-style partition path (`year=YYYY/month=MM/`) from `event_timestamp` values in a DataFrame | FR-ING-006. See KTD-10 for granularity rationale. |
| File Namer | Generates unique file names: `{source}_{YYYYMMDDTHHMMSS}_{short_id}.parquet` | FR-ING-007. See KTD-11 for naming rationale. |
| Write Orchestrator | Groups a DataFrame by partition, generates a file name per partition, delegates per-partition Parquet writes to BB-09 | Append-only — never modifies existing files (FR-ING-004) |
| Read Orchestrator | Determines which partitions to read (pruning), delegates reads to BB-09, combines multi-partition results into a single DataFrame | PyArrow handles multi-file reads within a partition natively |
| Partition Pruner | Given a time range (from `where` clause) or an upper-bound timestamp, determines which `year=YYYY/month=MM/` partitions to read vs. skip | Reduces I/O for time-bounded queries |
| Where Filter | Applies row-level `event_timestamp` filters after partition-level pruning | Partition pruning is coarse (month granularity); row-level filter is precise |

**Behavioral Rules:**

- **Writes are append-only (FR-ING-004, KTD-11).** Each ingestion creates new Parquet file(s). Existing files are never modified, overwritten, or deleted by BB-06. This eliminates conflict resolution and supports idempotent re-ingestion (same data ingested twice creates additional files — no data loss, no corruption).
- **Partition paths are deterministic from `event_timestamp`.** A record with `event_timestamp = 2024-03-15 11:00:00` is written to `{group_name}/year=2024/month=03/`. Records in the same ingestion batch may span multiple partitions.
- **All `.parquet` files in a partition are read regardless of source prefix (FR-ING-007).** The `source` prefix in the file name (`ing_`, `mock_`, etc.) is informational only. BB-06 reads everything in a partition directory.
- **Partition pruning for reads.** When a `where` clause specifies a time range, only partitions that could contain matching records are read. For joined group reads during `get_historical_features()`, the upper bound for pruning comes from the base group's maximum `event_timestamp` — joined data after the latest base record is irrelevant.
- **Row-level where filter is applied after read.** Partition pruning operates at month granularity. The row-level filter on `event_timestamp` applies the precise time conditions (`gt`, `gte`, `lt`, `lte`) from the `where` clause.

**Interface Contract:**

- **Exposes to BB-02:** `write(group_name, df, source_prefix)` for ingestion, `read(group_name, where=None, upper_bound=None) → DataFrame` for retrieval and materialization.
- **Depends on:** BB-09 (Provider Layer) — all Parquet I/O is delegated.

**Architectural Decisions:**

---

**KTD-10: Year/Month Partition Granularity**

- **Context:** Hive-style partitioning is used for the offline store. What time granularity should partitions use?
- **Options considered:**
  - (A) *Year only (`year=YYYY/`):* Too coarse — reads an entire year even when only one month is needed. Pruning benefit is minimal for the reference use case's 12-month span.
  - (B) *Year/Month (`year=YYYY/month=MM/`):* Good balance. The reference use case spans 12 months across ~2M records — monthly partitions provide effective pruning (~170K records per partition) without directory explosion (12 directories per year).
  - (C) *Year/Month/Day (`year=YYYY/month=MM/day=DD/`):* Finer pruning but creates ~365 directories per year. For the reference use case's volume, daily partitions would contain only ~5,500 records each — overhead of many small Parquet files outweighs the pruning benefit.
- **Decision:** (B) Year/Month.
- **Rationale:** AP-7 (simplicity — fewer directories, larger files), FR-ING-006 (requirement explicitly specifies `year=YYYY/month=MM/`). Monthly granularity matches the reference use case's monthly batch cadence.
- **Consequences:** Pruning is effective for month-level queries. Queries spanning a few days within a month still read the full month's partition, but the overhead is acceptable at the reference use case's scale.
- **Revisit if:** Users have very high daily ingestion volumes where monthly partitions exceed practical Parquet file sizes. At that point, day-level partitioning or intra-partition file splitting could be considered.

---

**KTD-11: Append-Only Writes with Unique File Naming**

- **Context:** Each ingestion creates new Parquet files within existing partitions. How are file names generated to prevent collisions and preserve data integrity?
- **Options considered:**
  - (A) *Overwrite existing files:* Simpler, but destroys history and makes ingestion non-idempotent. Violates FR-ING-004.
  - (B) *Append-only with unique file names:* Each ingestion creates a new file with a unique name. Uses pattern: `{source}_{YYYYMMDDTHHMMSS}_{short_id}.parquet`. The `source` prefix identifies write origin (`ing` for ingestion, `mock` for mock data). The timestamp provides temporal ordering. The short random ID (e.g., 8-character alphanumeric) prevents collisions if two ingestions happen within the same second.
- **Decision:** (B) Append-only with unique file names.
- **Rationale:** AP-7 (no conflict resolution or locking needed), FR-ING-004 (append-only), FR-ING-007 (naming pattern). Immutable files are the simplest correct approach — once written, a file is never touched again.
- **Consequences:** Reading a partition means reading all `.parquet` files in it. PyArrow's `read_table` on a directory handles this natively. Disk usage grows monotonically — there is no compaction in the MVP (see §4, Limitation 6). Re-ingesting the same data creates duplicate records — deduplication is the user's responsibility.
- **Revisit if:** Storage costs or read performance degrade due to many small files accumulating over time. A compaction utility could be added as a future enhancement.

---

**Error Scenarios:**

| Scenario | Error Type | Details |
| --- | --- | --- |
| Write failure (disk full, S3 permission denied) | `ProviderError` | Propagated from BB-09. No partial writes — the write either completes fully or fails. |
| No data in requested partitions | Returns empty DataFrame | Not an error — the caller (BB-02) decides how to handle empty results. |
| Corrupt Parquet file during read | `ProviderError` | Propagated from BB-09/PyArrow. |
| Partition derivation failure (null event_timestamp) | `IngestionError` | Records without a valid `event_timestamp` cannot be partitioned. Caught before write. |

---

### 2.7 Online Store Manager (BB-07)

**Responsibility:**

Orchestrates all online store operations: extracting the latest value per entity key from a DataFrame (materialization write), performing entity key lookups (serving read), and managing full-overwrite write semantics. All physical I/O is delegated to BB-09 (Provider Layer).

The Online Store Manager does NOT read from the offline store — BB-06 handles that during materialization, and BB-02 orchestrates the handoff. It does NOT validate data — data was already validated at ingestion time. It does NOT decide which groups to materialize — BB-02 resolves the target list.

**Internal Structure:**

| Component | Responsibility | Notes |
| --- | --- | --- |
| Latest Extractor | Given a DataFrame, groups by entity key, selects the row with the maximum `event_timestamp` per entity. Produces a DataFrame with exactly one row per entity key. | This is BB-07's core transformation — extracting the online store's invariant from offline data |
| Write Orchestrator | Takes the extracted latest-per-entity DataFrame, delegates a full-overwrite write to BB-09 | Full overwrite per group: all existing data for the group is replaced (KTD-12) |
| Read Orchestrator | Receives entity key name and value (extracted from the unified `where` parameter by BB-02), delegates a key-based lookup to BB-09, applies `select` to limit returned features | Returns `dict` per entity key, or `None` if not found (FR-ONL-002) |

**Behavioral Rules:**

- **Online store holds exactly one row per entity key per feature group.** This is the fundamental invariant. The Latest Extractor enforces this when preparing data for write; the store schema enforces it via PRIMARY KEY (SQLite) or partition key (DynamoDB). See §3.3 for schema details.
- **Materialization write is full overwrite per group (KTD-12).** All existing rows for the group are deleted, then the latest-per-entity rows are inserted. This happens within a single transaction (SQLite) or a single `TransactWriteItems` call (DynamoDB). Both paths are fully atomic (all-or-nothing), fulfilling NFR-REL-002. No merge logic, no conflict resolution — the simplest correct approach (AP-7).
- **Materialization is idempotent (FR-MAT-003).** Running materialization twice with the same offline data produces the same online store state. Full overwrite guarantees this.
- **Serving read returns `None` for missing entity keys (FR-ONL-002).** If an entity key is not in the online store, the result is `None` — not an error. The caller decides how to handle missing data.
- **`event_timestamp` and entity key are always included in results (FR-ONL-002).** Regardless of the `select` parameter, these structural columns are always present in the returned dictionary. They enable callers to verify data freshness.
- **No validation engine involvement on the serving path.** Online data was validated at ingestion. Re-validating on every serving request would add latency to a path optimized for speed.

**Interface Contract:**

- **Exposes to BB-02:** `materialize(group_name, df)` for materialization write (receives a full offline DataFrame, extracts latest internally), `get(group_name, entity_key_name, entity_key_value, select) → dict | None` for serving read. The `entity_key_name` and `entity_key_value` are extracted from the user-facing unified `where` parameter by BB-02 before calling BB-07 — BB-07 receives resolved values, not the raw `where` dict.
- **Depends on:** BB-09 (Provider Layer) — all SQLite/DynamoDB I/O is delegated.

**Architectural Decisions:**

---

**KTD-12: One Table Per Feature Group in the Online Store**

- **Context:** How should the online store be organized? Multiple feature groups need to coexist in the same online store. The organization affects materialization (write) and serving (read) behavior.
- **Options considered:**
  - (A) *Single shared table with a `feature_group_name` column:* All groups share one table. Queries filter by group name. Full-overwrite during materialization requires deleting only rows for the target group — more complex, and a bad delete could affect other groups.
  - (B) *One table per feature group:* Each group has its own table (SQLite) or DynamoDB table. Natural isolation — full overwrite is a table-level operation with no cross-group risk.
- **Decision:** (B) One table per feature group.
- **Rationale:** AP-7 (simpler overwrite — clear table/delete all + insert, no risk of cross-group data corruption), FR-MAT-001 (full overwrite per group). Natural isolation: materialization of one group cannot affect another.
- **Consequences:** The number of tables scales with the number of feature groups. At the expected scale (tens of groups, not thousands), this is not a concern. SQLite handles hundreds of tables efficiently. DynamoDB table creation is straightforward (one-time during first materialization). Schema per table matches the feature group's declared schema.
- **Revisit if:** The number of feature groups grows to hundreds or thousands. DynamoDB has account-level table limits (default 2500). At that point, a shared table design with hash-range keys would be more appropriate.

---

**Error Scenarios:**

| Scenario | Error Type | Details |
| --- | --- | --- |
| Online store table does not exist (serving read before first materialization) | `MaterializationError` | If the table for the requested feature group does not exist in the online store (i.e., `materialize()` has never been run for this group), BB-07 returns a clear error: "No online data for {name}. Run `kitefs materialize` first." This distinguishes "never materialized" from "materialized but entity key not found" (which returns `None`). |
| Online store not yet created (first materialization) | Handled internally | BB-09 creates the table lazily on first write. Not an error. |
| Entity key not found during serving read | Returns `None` | Not an error. Table exists but entity key is not present. Callers check for `None`. |
| Materialization for an OFFLINE-only group | `MaterializationError` | Caught by BB-02 during param validation (before BB-07 is called). See [docs-03-01 §4.7](docs-03-01-architecture-overview.md). |
| Provider write failure (SQLite locked, DynamoDB throttle) | `ProviderError` | Propagated from BB-09. Transaction rollback on failure (SQLite). |
| Empty offline data during materialization | Skipped with warning | BB-02 skips the group and reports a warning. No error raised. FR-MAT-001. |

---

### 2.8 Join Engine (BB-08)

**Responsibility:**

Performs point-in-time correct joins between DataFrames. This is a pure computational module — stateless, no I/O, no module dependencies. It receives DataFrames and join metadata as function arguments and returns a merged DataFrame.

The Join Engine does NOT read data — it receives pre-loaded DataFrames from BB-02. It does NOT validate data — BB-05 handles validation before the join. It does NOT manage storage layout or know about providers.

**Internal Structure:**

A single module with one primary function: the point-in-time join. No internal components requiring a table — the module is intentionally minimal.

**Behavioral Rules:**

- **The join is always point-in-time correct (AP-6).** For each base row, the engine finds the most recent joined row where `joined.event_timestamp ≤ base.event_timestamp` AND the join key matches. This is the only join behavior — there is no option for a simple equi-join or a non-temporal join.
- **Unmatched base rows are preserved with null-filled joined columns (FR-OFF-005).** The join is a left join — every base row appears in the output. If no matching joined row exists, the joined feature columns are set to `None`/`NaN`.
- **Timestamp tie is inclusive (≤, not <).** If a joined row has exactly the same `event_timestamp` as the base row, it is considered a valid match. This matches the convention that the `event_timestamp` represents when the data became available.
- **Join key field names are guaranteed to match by BB-04 validation (Item B).** BB-08 uses the join key field name directly as the `by` parameter in `pd.merge_asof`. No column renaming is performed. If a mismatched name somehow reaches BB-08, `merge_asof` will raise a `KeyError` — but this should never happen because BB-04 enforces name matching at `apply()` time.

**Interface Contract:**

- **Exposes to BB-02:** `pit_join(base_df, joined_df, base_join_field, joined_entity_key, left_timestamp, right_timestamp, joined_group_name) → DataFrame`. The caller provides both DataFrames, the field names for joining and temporal matching, and the joined group's name (used for column conflict resolution — see FR-OFF-010).
- **Depends on:** Nothing. BB-08 is a stateless leaf module. It receives everything it needs as function arguments.

**Architectural Decisions:**

---

**KTD-13: Point-in-Time Join via `pd.merge_asof`**

- **Context:** The PIT join is the most architecturally significant algorithm in KiteFS. Getting it wrong causes data leakage — future data leaking into training features — which silently corrupts model accuracy without visible errors. The implementation must be correct, tested, and understandable.
- **Options considered:**
  - (A) *`pd.merge_asof`:* Built-in Pandas function designed specifically for as-of joins. Requires both DataFrames sorted by the merge timestamp. The `by` parameter handles key matching. `direction='backward'` enforces the `≤` temporal condition. Well-tested, documented, and widely used in financial data applications.
  - (B) *Manual window join:* Sort, group by join key, iterate through rows, find matches. Full control but significantly more code and more room for correctness bugs.
  - (C) *SQL-based approach:* Convert DataFrames to DuckDB or an in-memory SQLite database, use window functions (`ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ... DESC)`). Correct but adds an external dependency (DuckDB) or conversion overhead (SQLite).
- **Decision:** (A) `pd.merge_asof`.
- **Rationale:** AP-7 (use the existing Pandas dependency — no additional library), AP-6 (proven correctness — `merge_asof` with `direction='backward'` is semantically identical to PIT join requirements). The function exists precisely for this use case. Writing custom join logic would be more error-prone and harder to verify.
- **Consequences:** Both DataFrames must be sorted by `event_timestamp` before calling `merge_asof`. The `by` parameter specifies the join key columns. The `left_on`/`right_on` parameters specify the timestamp columns. The function returns a left-joined DataFrame with null-filled joined columns for unmatched rows.
- **Revisit if:** Performance is insufficient for large DataFrames. Polars `join_asof` offers similar semantics with better performance on large datasets, but adds a dependency. At the reference use case scale (~2M listings, ~72 market records), Pandas `merge_asof` is more than sufficient.

---

**Complex Algorithm: Point-in-Time Correct Join**

**What it does:** Given a base DataFrame and a joined DataFrame, produces a merged DataFrame where each base row is matched with the most recent joined row whose `event_timestamp` is ≤ the base row's `event_timestamp`, joined on a key relationship.

**Algorithm (step by step):**

1. **Receive inputs:** Base DataFrame (e.g., `listing_features`), joined DataFrame (e.g., `town_market_features`), join key mapping (e.g., base `town_id` → joined entity key `town_id`), timestamp column names, joined group name (e.g., `"town_market_features"`).
2. **Sort both DataFrames** by `event_timestamp` ascending. This is a requirement of `pd.merge_asof`.
3. **Call `pd.merge_asof`:**
   - `left` = base DataFrame
   - `right` = joined DataFrame
   - `left_on` = base `event_timestamp` column
   - `right_on` = joined `event_timestamp` column
   - `by` = join key mapping (base field → joined entity key)
   - `direction='backward'` — for each left row, find the most recent right row where `right.event_timestamp ≤ left.event_timestamp`
   - `suffixes=('', '_joined__')` — temporary suffixes to disambiguate overlapping column names; the base side gets no suffix, the joined side gets a temporary marker
4. **Handle unmatched rows:** `merge_asof` automatically fills unmatched joined columns with `NaN` (Pandas convention for missing values). This satisfies FR-OFF-005.
5. **Resolve column name conflicts (FR-OFF-010):** Identify any joined-side columns whose original names (before the merge) conflict with base-side column names. Rename each conflicting joined column by prefixing it with `{joined_group_name}_` (e.g., the joined `event_timestamp` becomes `town_market_features_event_timestamp`). Remove the temporary suffix applied in step 3 and apply the final prefixed name. Non-conflicting joined columns retain their original names.
6. **Return** the merged DataFrame.

**Boundary conditions (with concrete examples from the reference use case):**

- **No matching joined rows:** Listing 1010 (town_id=3, event_timestamp=2024-01-20). The earliest `town_market_features` for town 3 has event_timestamp=2024-02-01. Since 2024-02-01 > 2024-01-20, no match exists. Result: `avg_price_per_sqm = NaN`. The listing is preserved in the output. ([docs-00-01 §7.3](docs-00-01-reference-use-case.md) boundary condition.)
- **Multiple matching joined rows, most recent wins:** Listing 1002 (town_id=1, event_timestamp=2024-04-05). Candidates: town_id=1 with event_timestamps 2024-02-01, 2024-03-01, 2024-04-01. All three are ≤ 2024-04-05. `merge_asof` with `direction='backward'` selects the most recent: 2024-04-01 → `avg_price_per_sqm = 25400.00`.
- **Exact timestamp tie:** If a joined row has `event_timestamp` exactly equal to the base row's `event_timestamp`, it is included (≤ condition). This is correct: the event timestamp represents when the data became available, so data available at the exact moment of the base event is a valid match.
- **Empty base DataFrame:** `merge_asof` on an empty left DataFrame returns an empty DataFrame with the correct column schema. Not an error.
- **Empty joined DataFrame:** `merge_asof` returns the base DataFrame with all joined columns filled with `NaN`. Every base row is preserved.

**Performance characteristics at reference use case scale:**

- Base DataFrame: ~2M rows (listing_features, all sold listings)
- Joined DataFrame: ~72 rows (town_market_features, 12 months × 6 towns)
- Sort: O(n log n) on ~2M rows — sub-second with Pandas on modern hardware
- `merge_asof`: O(n + m) after sorting — essentially a single pass through both sorted arrays
- Expected total time: seconds, not minutes. Well within acceptable bounds for a batch training data generation operation.

**Error Scenarios:**

| Scenario | Behavior |
| --- | --- |
| Join key column missing from either DataFrame | Pandas raises `KeyError`. BB-02 should validate column presence before calling BB-08. In practice, BB-04 validates select/join params before any data is read. |
| Timestamp column not sorted (precondition violation) | `merge_asof` requires sorted input. BB-08 sorts both DataFrames before the call — the precondition is enforced internally, not relied upon from callers. |
| Data type mismatch on join key columns | Pandas `merge_asof` raises `MergeError`. BB-04 validates type compatibility at `apply()` time; BB-05 validates column types at retrieval time. A type mismatch reaching BB-08 indicates a bug in upstream validation. |

---

### 2.9 Provider Layer (BB-09)

**Responsibility:**

Defines the abstract interface for all storage I/O (offline store read/write, online store read/write, registry read/write) and provides two concrete implementations: `LocalProvider` (filesystem + SQLite) and `AWSProvider` (S3 + DynamoDB). This is the architectural seam that separates core logic ("what to do") from storage mechanics ("how to store").

The Provider Layer does NOT contain domain logic. It does not know about partitioning strategies, validation, or feature semantics. It implements primitive storage operations: read bytes/DataFrames from a location, write bytes/DataFrames to a location. The calling module (BB-04, BB-06, or BB-07) decides what to read/write and where.

**Internal Structure:**

| Component | Responsibility | Notes |
| --- | --- | --- |
| `StorageProvider` (ABC) | Abstract base class defining the provider interface. All storage operations are declared here as abstract methods. | KTD-14. Concrete providers must implement all methods. |
| `LocalProvider` | Implements the provider interface using local filesystem (Parquet via PyArrow), SQLite (via `sqlite3` stdlib), and local file I/O (registry JSON). | Zero external infrastructure required (AP-1, FR-PROV-003) |
| `AWSProvider` | Implements the provider interface using S3 (Parquet via PyArrow + boto3), DynamoDB (via boto3), and S3 (registry JSON). | Requires AWS credentials via standard credential chain (FR-PROV-004) |

**Provider Interface Methods:**

The interface is grouped by storage concern. Each method is a single, primitive storage action. Core modules compose these into higher-level operations.

| Category | Method | Purpose |
| --- | --- | --- |
| **Offline** | `write_offline(group_name, partition_path, file_name, df)` | Write a single Parquet file to a specific partition |
| | `read_offline(group_name, partition_paths) → DataFrame` | Read Parquet files from specified partitions, return combined DataFrame |
| | `list_partitions(group_name) → list[str]` | List available partition paths for a feature group |
| **Online** | `write_online(group_name, df)` | Atomic full-overwrite: delete all existing data for the group and write the provided DataFrame as a single atomic operation |
| | `read_online(group_name, entity_key_name, entity_key_value) → dict \| None` | Look up a single entity key, return record as dict or None |
| **Registry** | `write_registry(data: str)` | Write the registry JSON string to the configured location |
| | `read_registry() → str` | Read the registry JSON string from the configured location |

**Behavioral Rules:**

- **Both providers must produce identical logical results for the same inputs.** If `LocalProvider.read_offline("listing_features", ["year=2024/month=03/"])` returns a DataFrame with columns X, Y, Z and 1000 rows, then `AWSProvider.read_offline(...)` for the same data must return an equivalent DataFrame. Physical transport differs; logical behavior is identical. This invariant is enforced by testing both providers against the same test suite.
- **Provider is instantiated once at SDK startup and injected into core modules.** BB-02 reads the configured provider name from BB-10, instantiates the appropriate provider class, and passes it to BB-04, BB-06, and BB-07 at construction time (constructor injection).
- **Lazy resource creation.** Directories (local), S3 prefixes, SQLite database files, and DynamoDB tables are created on first write, not eagerly at initialization. `kitefs init` creates the top-level directory structure; the provider creates storage-level resources lazily (AP-7).
- **Atomic writes are guaranteed by the provider contract.** SQLite writes use transactions (commit on success, rollback on failure). Local Parquet writes use write-to-temp-then-rename for atomicity. S3 `put_object` is atomic per object. DynamoDB materialization uses `TransactWriteItems` (up to 100 actions per transaction) to atomically delete existing items and insert new ones — fully atomic (all-or-nothing). The 100-action limit constrains materialization to ~50 entity keys per feature group (deletes + puts share the budget); this is sufficient for the MVP reference use case (6 entities). See §4 Limitation 9 for details.

**Interface Contract:**

- **Exposes:** The `StorageProvider` abstract base class and the two concrete implementations. Core modules depend only on `StorageProvider` — they never import `LocalProvider` or `AWSProvider` directly.
- **Depends on:** BB-10 (Configuration Manager) — for storage root path, S3 bucket/prefix, DynamoDB table prefix, and other provider-specific configuration.

**LocalProvider Implementation Details:**

| Operation | Technology | Implementation Notes |
| --- | --- | --- |
| Offline read/write | PyArrow `read_table` / `write_table` | Parquet files on local filesystem. `read_table` on a directory reads all `.parquet` files. |
| Online read/write | `sqlite3` (Python stdlib) | Single `online.db` file at `{storage_root}/data/online_store/online.db`. One table per feature group. |
| Registry read/write | Standard file I/O (`open`, `read`, `write`) | `registry.json` at `{storage_root}/registry.json` |
| Lazy creation | `os.makedirs(exist_ok=True)` | Directories created on first write. SQLite database file created on first connection. |

**AWSProvider Implementation Details:**

| Operation | Technology | Implementation Notes |
| --- | --- | --- |
| Offline read/write | PyArrow + `boto3` S3 client | Same Parquet layout as local, just on S3. `s3://bucket/prefix/data/offline_store/...` |
| Online read/write | `boto3` DynamoDB resource | One DynamoDB table per feature group: `{prefix}_{group_name}`. Partition key = entity key field. Materialization uses `TransactWriteItems` for atomic full-overwrite (delete + put in a single transaction). |
| Registry read/write | `boto3` S3 client | `registry.json` at `s3://bucket/prefix/registry.json` |
| Lazy creation | DynamoDB `create_table` on first write | S3 prefixes don't need explicit creation. DynamoDB tables are created with the correct key schema on first materialization. |

**Architectural Decisions:**

---

**KTD-14: Provider Interface as ABC (Not Protocol)**

- **Context:** How should the provider contract be defined in Python? The contract is critical — every storage operation in the system flows through it. Two implementations exist (local, AWS), and more may be added in the future (GCP, Azure).
- **Options considered:**
  - (A) *`abc.ABC` with `@abstractmethod`:* Explicit inheritance. IDE support for unimplemented methods. Clear error at instantiation time if a method is missing. Requires `class LocalProvider(StorageProvider)`.
  - (B) *`typing.Protocol`:* Structural typing — no inheritance needed. A class that implements the right methods automatically satisfies the protocol. More "Pythonic" in some styles. Used when you want to accept third-party classes that happen to have the right shape.
  - (C) *No formal contract (duck typing):* Rely on runtime method calls to discover missing implementations. Maximum flexibility; minimum safety.
- **Decision:** (A) ABC.
- **Rationale:** AP-3 (provider abstraction must be explicit and verifiable), AP-7 (clear guardrails, not clever typing tricks). For a project with exactly two implementations where correctness is critical, explicit inheritance provides the best safety. ABCs produce an immediate `TypeError` at instantiation if any abstract method is not implemented — the developer knows at import time, not when the method is first called. Protocol's structural typing is better suited for large ecosystems with unknown implementers; KiteFS has a known, small set of providers.
- **Consequences:** Every provider must subclass `StorageProvider` and implement all abstract methods. Adding a new provider is straightforward: subclass, implement methods, test against the shared test suite. The type checker (mypy) enforces completeness at analysis time; the runtime enforces it at instantiation time.
- **Revisit if:** A third-party library needs to act as a provider without adopting the KiteFS base class. At that point, an adapter pattern or a Protocol could complement the ABC.

---

**KTD-15: Provider Method Granularity**

- **Context:** How many methods should the provider interface expose? Too few forces core modules to re-implement storage logic; too many creates a burdensome contract for new providers.
- **Options considered:**
  - (A) *Fine-grained: one method per primitive operation* (as shown in the method table above). ~8 methods covering offline, online, and registry operations.
  - (B) *Coarse-grained: one method per store type* (e.g., `offline_store()` returns a sub-interface). Reduces the main interface surface but adds indirection.
  - (C) *Single read/write with operation type parameter:* `provider.write(target="offline", ...)`. Extremely generic, but loses type safety and IDE support.
- **Decision:** (A) Fine-grained, grouped by storage concern.
- **Rationale:** AP-7 (each method is simple and testable in isolation), AP-3 (core modules call exactly the storage operation they need — no parameter interpretation). ~8 methods is a manageable contract for new provider implementations. Each method has clear input/output types.
- **Consequences:** Adding a new storage concern (e.g., a metadata store separate from the registry) requires adding methods to the interface and all implementations. At the expected scale (two providers, one offline/online/registry each), this is not burdensome.
- **Revisit if:** The interface grows past ~15 methods. At that point, sub-interfaces (offline, online, registry) might improve organization.

---

**Error Scenarios:**

| Scenario | Error Type | Details |
| --- | --- | --- |
| Storage not accessible (disk full, S3 403) | `ProviderError` | Wraps the underlying exception (OSError, botocore ClientError) with context: which operation, which path. |
| Resource doesn't exist on read | Returns empty/None/raises | `read_offline` returns empty DataFrame if no partitions exist. `read_online` returns `None` if entity key not found. `read_online` raises `ProviderError` (table not found) if the online store table for the requested group does not exist — BB-07 translates this into a `MaterializationError` with a materialization hint (FR-ONL-002). `read_registry` raises `ProviderError` if registry file doesn't exist (should not happen after `init`). |
| DynamoDB throttling | `ProviderError` | AWSProvider should implement basic retry with exponential backoff for DynamoDB throttle errors. If retries are exhausted, raise `ProviderError`. |
| SQLite corruption | `ProviderError` | Wraps `sqlite3.DatabaseError`. Recovery: delete `online.db` and re-materialize. |
| AWS credentials not configured | `ProviderError` | Wraps `botocore.exceptions.NoCredentialsError` with a clear message directing the user to configure AWS credentials. |

---

### 2.10 Configuration Manager (BB-10)

**Responsibility:**

Loads, validates, and exposes `kitefs.yaml` settings: the active provider, storage root path, and provider-specific configuration (AWS bucket, prefix, DynamoDB table prefix). Supports environment variable overrides for CI/CD environments.

**Behavioral Rules:**

- **Missing `kitefs.yaml` → immediate error (FR-CFG-004).** The error message directs the user to run `kitefs init`. The system does not assume defaults or create the file automatically — data systems must fail loudly on misconfiguration.
- **Invalid `kitefs.yaml` → specific validation error (FR-CFG-003, FR-CFG-004).** Missing required fields, malformed YAML, unsupported provider value, AWS fields missing when `provider: aws` — each produces a specific error identifying the issue. Silent defaults are intentionally avoided ([docs-03-01 §5.2](docs-03-01-architecture-overview.md)).
- **Environment variable overrides (FR-CFG-005).** Environment variables take precedence over `kitefs.yaml` values. Convention:
  - `KITEFS_PROVIDER` → overrides `provider`
  - `KITEFS_STORAGE_ROOT` → overrides `storage_root`
  - `KITEFS_AWS_S3_BUCKET` → overrides `aws.s3_bucket`
  - `KITEFS_AWS_S3_PREFIX` → overrides `aws.s3_prefix`
  - `KITEFS_AWS_DYNAMODB_TABLE_PREFIX` → overrides `aws.dynamodb_table_prefix`
- **Configuration is loaded once at SDK startup** (BB-02 `__init__`). The validated configuration is exposed as a typed object (not a raw dict) for IDE autocompletion and type safety.
- **`storage_root` is set during `kitefs init` and treated as immutable for the lifetime of the project.** Changing it after data has been ingested is unsupported — the system does not detect or migrate data across storage roots. The new path will be empty and the old data remains at the original location, orphaned.
- **Validation is exhaustive.** All possible errors are checked and collected before reporting — same principle as KTD-9 (all-or-nothing with collected errors). A single invalid configuration file should surface all its issues in one message.

**Error Scenarios:**

| Scenario | Error Type | Details |
| --- | --- | --- |
| `kitefs.yaml` not found | `ConfigurationError` | "No configuration file found at {path}. Run `kitefs init` to create a project." |
| YAML syntax error (malformed file) | `ConfigurationError` | Wraps PyYAML parse error with file path context. |
| Missing required field (`provider` or `storage_root`) | `ConfigurationError` | "Missing required field: {field} in kitefs.yaml" |
| Unsupported provider value | `ConfigurationError` | "Unsupported provider: {value}. Supported: local, aws" |
| AWS fields missing when `provider: aws` | `ConfigurationError` | Lists all missing AWS fields together. |
| Environment variable with invalid value | `ConfigurationError` | Names the variable and the invalid value. |

---

## 3. Data Architecture

> _Describes how data is physically stored, structured, and accessed.
> These are the shared contracts that multiple building blocks depend
> on. Documenting them here prevents repetition and inconsistency
> across building block descriptions._

### 3.1 Feature Registry (`registry.json`)

**What it stores:** All registered feature group definitions in a deterministic, Git-versionable JSON format.

**Location:**
- Local provider: `{storage_root}/registry.json` (e.g., `./feature_store/registry.json`)
- AWS provider: `s3://{bucket}/{prefix}/registry.json`

**Format:** JSON with `sort_keys=True`, `indent=2` (FR-REG-001). Produces meaningful Git diffs when feature groups are added, modified, or removed.

**Schema:**

```json
{
  "version": "1.0",
  "feature_groups": {
    "<group_name>": {
      "name": "<string>",
      "storage_target": "OFFLINE | OFFLINE_AND_ONLINE",
      "entity_key": {
        "name": "<string>",
        "dtype": "STRING | INTEGER | FLOAT | DATETIME",
        "description": "<string | null>"
      },
      "event_timestamp": {
        "name": "<string>",
        "dtype": "DATETIME",
        "description": "<string | null>"
      },
      "features": [
        {
          "name": "<string>",
          "dtype": "STRING | INTEGER | FLOAT | DATETIME",
          "description": "<string | null>",
          "expect": [
            { "<constraint_type>": "<value>" }
          ]
        }
      ],
      "join_keys": [
        {
          "field_name": "<string>",
          "referenced_group": "<string>"
        }
      ],
      "ingestion_validation": "ERROR | FILTER | NONE",
      "offline_retrieval_validation": "ERROR | FILTER | NONE",
      "metadata": {
        "description": "<string | null>",
        "owner": "<string | null>",
        "tags": { "<key>": "<value>" }
      },
      "applied_at": "<ISO 8601 timestamp>",
      "last_materialized_at": "<ISO 8601 timestamp | null>"
    }
  }
}
```

**Concrete example using the reference use case:**

```json
{
  "version": "1.0",
  "feature_groups": {
    "listing_features": {
      "name": "listing_features",
      "storage_target": "OFFLINE",
      "entity_key": {
        "name": "listing_id",
        "dtype": "INTEGER",
        "description": "Unique identifier for each listing"
      },
      "event_timestamp": {
        "name": "event_timestamp",
        "dtype": "DATETIME",
        "description": "When the listing was sold"
      },
      "features": [
        {
          "name": "build_year",
          "dtype": "INTEGER",
          "description": "Year the building was constructed",
          "expect": [
            { "not_null": true },
            { "gte": 1900 },
            { "lte": 2030 }
          ]
        },
        {
          "name": "net_area",
          "dtype": "INTEGER",
          "description": "Usable area in sqm",
          "expect": [
            { "not_null": true },
            { "gt": 0 }
          ]
        },
        {
          "name": "number_of_rooms",
          "dtype": "INTEGER",
          "description": "Number of rooms",
          "expect": [
            { "not_null": true },
            { "gt": 0 }
          ]
        },
        {
          "name": "sold_price",
          "dtype": "FLOAT",
          "description": "Sold price in TL (training label)",
          "expect": [
            { "not_null": true },
            { "gt": 0 }
          ]
        },
        {
          "name": "town_id",
          "dtype": "INTEGER",
          "description": "Join key to town_market_features",
          "expect": null
        }
      ],
      "join_keys": [
        {
          "field_name": "town_id",
          "referenced_group": "town_market_features"
        }
      ],
      "ingestion_validation": "ERROR",
      "offline_retrieval_validation": "NONE",
      "metadata": {
        "description": "Historical sold listing attributes and prices",
        "owner": "data-science-team",
        "tags": {
          "cadence": "monthly",
          "domain": "real-estate"
        }
      },
      "applied_at": "2025-01-01T00:00:00",
      "last_materialized_at": null
    },
    "town_market_features": {
      "name": "town_market_features",
      "storage_target": "OFFLINE_AND_ONLINE",
      "entity_key": {
        "name": "town_id",
        "dtype": "INTEGER",
        "description": "Unique town identifier"
      },
      "event_timestamp": {
        "name": "event_timestamp",
        "dtype": "DATETIME",
        "description": "When this value became available"
      },
      "features": [
        {
          "name": "avg_price_per_sqm",
          "dtype": "FLOAT",
          "description": "Average sold price per sqm in this town last month",
          "expect": [
            { "not_null": true },
            { "gt": 0 }
          ]
        }
      ],
      "join_keys": [],
      "ingestion_validation": "ERROR",
      "offline_retrieval_validation": "NONE",
      "metadata": {
        "description": "Monthly town-level market aggregate",
        "owner": "data-science-team",
        "tags": {
          "cadence": "monthly",
          "domain": "real-estate"
        }
      },
      "applied_at": "2025-01-01T00:00:00",
      "last_materialized_at": "2025-01-01T00:05:00"
    }
  }
}
```

**Note:** `entity_key` and `event_timestamp` are top-level objects (no ordering concern). Features within the `features` list are sorted alphabetically by `name` for deterministic output. The top-level JSON keys are ordered alphabetically by `sort_keys=True`.

**`applied_at` field:** Records the timestamp of the last `apply()` execution. This value resets on every `apply()` — it does not track when the feature group was originally created. It is intended for debugging (e.g., confirming the registry is up to date). Full audit fields (`created_at`, `updated_at`, version history) are out of scope for the MVP.

**`last_materialized_at` field:** Records the timestamp of the last successful `materialize()` execution for this feature group. Set to `null` initially (never materialized) and updated by BB-02 after each successful materialization write. This field is preserved across `apply()` runs — `apply()` reads the existing value from the current registry and carries it forward into the regenerated registry. Only `materialize()` updates this field. It enables users to check when a group was last materialized (via `describe`) and supports future incremental materialization (FR-MAT-006).

**Read access patterns:**
- BB-04 (Registry Manager) reads the registry at SDK startup (via BB-09) and caches it in memory. Subsequent lookups (`get_group`, `list_groups`) read from the in-memory cache.
- The registry is read as a single JSON string, parsed in Python. No partial reads or streaming.

**Write access patterns:**
- BB-04 writes the registry via BB-09 on every `apply()`. Full overwrite — the entire file is replaced (KTD-3 in [docs-03-01](docs-03-01-architecture-overview.md)).
- `kitefs init` seeds an empty registry: `{ "version": "1.0", "feature_groups": {} }`.

**Lifecycle:**
- Created by `kitefs init` (empty).
- Regenerated by `apply()` (full rebuild from definitions).
- Synced/pulled for remote sharing (Should Have — `registry-sync`, `registry-pull`).
- Never manually edited by users.

**Invariants:**
- **Deterministic:** The same set of definitions always produces byte-for-byte identical JSON output.
- **Consistent with definitions:** After `apply()`, the registry reflects exactly the definitions in `definitions/`. No more, no less.
- **Valid JSON:** Always parseable. A corrupt registry indicates a bug — re-running `apply()` regenerates it from definitions.

---

### 3.2 Offline Store (Parquet Files)

**What it stores:** Historical feature data — all records ever ingested, organized by feature group and partitioned by time.

**Location:**
- Local provider: `{storage_root}/data/offline_store/{group_name}/year=YYYY/month=MM/{file_name}.parquet`
- AWS provider: `s3://{bucket}/{prefix}/data/offline_store/{group_name}/year=YYYY/month=MM/{file_name}.parquet`

**Format:** Apache Parquet, written and read via PyArrow.

**File naming:** `{source}_{YYYYMMDDTHHMMSS}_{short_id}.parquet` (FR-ING-007). Examples:
- `ing_20240201T000000_a1b2c3d4.parquet` (ingestion)
- `mock_20240201T000000_e5f6g7h8.parquet` (mock data generation)

**Schema:**

Each feature group's Parquet files contain: the entity key column, the `event_timestamp` column, and all declared feature columns. The column types follow this mapping:

**Type Mapping:**

| FeatureType | PyArrow Type | Pandas dtype | Python Type | SQLite Type | DynamoDB Type |
| --- | --- | --- | --- | --- | --- |
| `STRING` | `pa.string()` | `object` (str) | `str` | `TEXT` | `S` |
| `INTEGER` | `pa.int64()` | `int64` | `int` | `INTEGER` | `N` |
| `FLOAT` | `pa.float64()` | `float64` | `float` | `REAL` | `N` |
| `DATETIME` | `pa.timestamp('us')` | `datetime64[us]` | `datetime` | `TEXT` (ISO 8601) | `S` (ISO 8601) |

This mapping is a shared contract referenced by BB-05 (type validation), BB-06 (Parquet writes), BB-07 (online store writes), and BB-09 (both providers).

**Concrete schema examples from the reference use case:**

**`listing_features` Parquet schema:**

| Column | PyArrow Type | Description |
| --- | --- | --- |
| `listing_id` | `int64` | Entity key |
| `event_timestamp` | `timestamp[us]` | When the listing was sold |
| `town_id` | `int64` | Join key to town_market_features |
| `net_area` | `int64` | Usable area in sqm |
| `number_of_rooms` | `int64` | Number of rooms |
| `build_year` | `int64` | Construction year |
| `sold_price` | `float64` | Sold price in TL |

**Sample data (partition `year=2024/month=03/`):**

| listing_id | event_timestamp | town_id | net_area | number_of_rooms | build_year | sold_price |
| --- | --- | --- | --- | --- | --- | --- |
| 1001 | 2024-03-15 11:00:00 | 2 | 75 | 2 | 2020 | 2250000.00 |
| 1003 | 2024-03-18 14:30:00 | 6 | 85 | 2 | 2002 | 1050000.00 |

**`town_market_features` Parquet schema:**

| Column | PyArrow Type | Description |
| --- | --- | --- |
| `town_id` | `int64` | Entity key |
| `event_timestamp` | `timestamp[us]` | When this value became available (first of next month) |
| `avg_price_per_sqm` | `float64` | Average sold price per sqm |

**Sample data (partition `year=2024/month=02/`):**

| town_id | event_timestamp | avg_price_per_sqm |
| --- | --- | --- |
| 1 | 2024-02-01 00:00:00 | 24500.00 |
| 2 | 2024-02-01 00:00:00 | 28200.00 |
| 3 | 2024-02-01 00:00:00 | 14100.00 |
| 4 | 2024-02-01 00:00:00 | 18500.00 |
| 5 | 2024-02-01 00:00:00 | 14200.00 |
| 6 | 2024-02-01 00:00:00 | 11800.00 |

**Read access patterns:**
- BB-06 (Offline Store Manager) reads via BB-09. Uses partition pruning: given a `where` clause with a time range, only partitions within that range are read. For joined group reads, pruning uses the base group's maximum `event_timestamp` as the upper bound.
- PyArrow `read_table` on a partition directory reads all `.parquet` files and combines them into a single table.
- BB-06 applies row-level where filters after the partition-level read (partition granularity is month; where filters are timestamp-precise).

**Write access patterns:**
- BB-06 (Offline Store Manager) writes via BB-09 during `ingest()`. Each ingestion creates one new file per partition. Append-only — existing files are never modified (FR-ING-004).
- Partition path is derived from `event_timestamp`: a record with `event_timestamp = 2024-03-15` goes to `year=2024/month=03/`.

**Lifecycle:**
- Created on first `ingest()` call for a feature group. Empty before that — `kitefs init` creates the `data/offline_store/` directory but no group subdirectories.
- Grows with each ingestion. No deletion or compaction in the MVP (see §4, Limitation 6).
- Data can be regenerated from source systems by re-running the user's ingestion pipeline.

**Invariants:**
- **Append-only.** Files are immutable after creation. No updates, no deletes by the system.
- **Partition path deterministic from `event_timestamp`.** Given an `event_timestamp`, the partition path is always `year=YYYY/month=MM/` derived from that timestamp. No ambiguity.
- **Schema consistent within a feature group.** All Parquet files for a given feature group have the same column set and types. Schema changes require re-ingestion (see §4, Limitation 5).

---

### 3.3 Online Store

**What it stores:** The latest feature values per entity key for each `OFFLINE_AND_ONLINE` feature group. This is the serving layer — optimized for single-key lookups at prediction time.

#### 3.3.1 SQLite (Local Provider)

**Location:** `{storage_root}/data/online_store/online.db`

**Schema:** One table per feature group (KTD-12). Table name = feature group name. Entity key column is `PRIMARY KEY`.

**Concrete example — `town_market_features` table:**

```sql
CREATE TABLE town_market_features (
    town_id     INTEGER PRIMARY KEY,
    event_timestamp TEXT,
    avg_price_per_sqm REAL
);
```

**Sample data:**

| town_id | event_timestamp | avg_price_per_sqm |
| --- | --- | --- |
| 1 | 2025-01-01T00:00:00 | 27200.00 |
| 2 | 2025-01-01T00:00:00 | 31500.00 |
| 3 | 2025-01-01T00:00:00 | 15800.00 |
| 4 | 2025-01-01T00:00:00 | 19200.00 |
| 5 | 2025-01-01T00:00:00 | 14800.00 |
| 6 | 2025-01-01T00:00:00 | 12100.00 |

**Read access pattern:** `SELECT * FROM {group_name} WHERE {entity_key} = ?` — single-row lookup by primary key. BB-07 invokes via BB-09.

**Write access pattern (materialization):**
1. `BEGIN TRANSACTION`
2. `DELETE FROM {group_name}` — remove all existing rows for the group
3. `INSERT INTO {group_name} ...` — insert the latest-per-entity rows
4. `COMMIT`

If the table does not exist (first materialization), it is created with the appropriate schema before inserting. The full sequence is atomic within a single SQLite transaction — either all rows are replaced or none are.

**SQLite type mapping:** Uses the type mapping from §3.2. `DATETIME` values are stored as ISO 8601 `TEXT` strings.

#### 3.3.2 DynamoDB (AWS Provider)

**Table naming:** `{dynamodb_table_prefix}{group_name}` (e.g., `kitefs_town_market_features`)

**Schema:** Partition key = entity key field name. Each item (row) represents one entity's latest feature values.

**Concrete example — table `kitefs_town_market_features`:**

- Partition key: `town_id` (Number)

**Sample item:**

```json
{
  "town_id": { "N": "1" },
  "event_timestamp": { "S": "2025-01-01T00:00:00" },
  "avg_price_per_sqm": { "N": "27200.00" }
}
```

**Read access pattern:** `GetItem` with key `{entity_key: value}` — single-item lookup by partition key. BB-07 invokes via BB-09.

**Write access pattern (materialization):**
1. Scan existing items to collect their keys
2. Build a single `TransactWriteItems` request containing `Delete` actions for all existing items and `Put` actions for all new latest-per-entity rows
3. Execute the transaction — fully atomic (all-or-nothing)

`TransactWriteItems` supports up to 100 actions per call. With deletes and puts sharing the budget, this supports ~50 entity keys per feature group. The MVP reference use case (6 entities) is well within this limit. See §4 Limitation 9 for the scaling constraint.

**DynamoDB type mapping:** Uses the type mapping from §3.2. `INTEGER` and `FLOAT` are stored as DynamoDB `N` (Number). `STRING` and `DATETIME` are stored as `S` (String).

---

### 3.4 Cross-Provider Consistency

**Identical across providers (the consistency contract):**

| Aspect | Guarantee |
| --- | --- |
| Logical data model | Same columns, same types, same feature group granularity. A DataFrame written via `LocalProvider` and read back has the same schema and values as one written via `AWSProvider`. |
| Offline store layout | Same Hive-style partitioning (`year=YYYY/month=MM/`), same file naming convention, same Parquet format. |
| Registry JSON schema | Byte-for-byte identical output given the same definitions (deterministic serialization). |
| SDK method behavior | All public SDK methods return the same types and follow the same semantics regardless of provider. |
| Validation behavior | The Validation Engine (BB-05) is provider-agnostic. Same schema, same expectations, same mode → same validation result. |

**Differs across providers:**

| Aspect | Local Provider | AWS Provider |
| --- | --- | --- |
| Offline store transport | Local filesystem (PyArrow ↔ disk) | S3 (PyArrow ↔ boto3 ↔ S3) |
| Online store technology | SQLite (single `online.db` file) | DynamoDB (one table per group, managed service) |
| Registry storage | Local file | S3 object |
| Credential requirements | None | AWS IAM credentials (standard credential chain) |
| Latency characteristics | Disk I/O (milliseconds) | Network I/O (tens of milliseconds) |
| Concurrency model | Single-process (SQLite write lock) | Multi-process safe (DynamoDB handles concurrency) |

**How consistency is enforced:**

1. **Architectural enforcement (AP-3, KTD-2 in [docs-03-01](docs-03-01-architecture-overview.md)):** Core modules (BB-04, BB-05, BB-06, BB-07, BB-08) never import provider-specific libraries. All I/O goes through the `StorageProvider` interface. A core module cannot accidentally behave differently per provider because it has no access to provider-specific APIs.
2. **Shared type mapping (§3.2):** The type mapping table is the single source of truth for how `FeatureType` values map to concrete storage types across all technologies.
3. **Shared test suite:** Both providers are tested against the same integration tests. A test that passes for `LocalProvider` and fails for `AWSProvider` (or vice versa) indicates a consistency violation.

---

### 3.5 Data Integrity Guarantees

| Guarantee | How Enforced | Reference |
| --- | --- | --- |
| **No partial writes on ingestion failure** | Parquet files are written atomically (write-to-temp-then-rename on local; `put_object` on S3). If a write fails, no partial file is left behind. | NFR-REL-001, FR-ING-004 |
| **Append-only offline store** | BB-06 never calls delete or overwrite on existing Parquet files. New ingestions always create new files. | FR-ING-004, KTD-11 |
| **Point-in-time correctness** | BB-08 (Join Engine) uses `pd.merge_asof` with `direction='backward'` — enforcing `joined.event_timestamp ≤ base.event_timestamp`. No configuration can disable this. | FR-OFF-003, AP-6, KTD-13 |
| **Registry determinism** | Full rebuild on every `apply()` with `json.dumps(sort_keys=True, indent=2)`. Same definitions → same bytes. | FR-REG-001, KTD-3 |
| **Online store: single row per entity** | Entity key is PRIMARY KEY (SQLite) or partition key (DynamoDB). Full overwrite on materialization replaces all rows. | FR-MAT-001, KTD-12 |
| **No partial writes on materialization failure** | SQLite uses a transaction (rollback on failure). DynamoDB uses `TransactWriteItems` (all-or-nothing). The provider interface contract requires `write_online` to be atomic. | NFR-REL-002, KTD-12 |
| **Materialization idempotency** | Full-read-then-full-overwrite means running materialization twice with the same offline data produces the same online store state. | FR-MAT-003 |
| **Materialization tracking** | After each successful materialization, BB-02 writes a `last_materialized_at` ISO 8601 timestamp to the feature group's registry entry. This provides traceability (when was data last synced to the online store?) and supports future incremental materialization. The field is preserved across `apply()` runs. | FR-MAT-001 |
| **Schema enforcement at every gate** | BB-05 (Validation Engine) runs at ingestion gate and offline retrieval gate. Schema validation is always-on (missing columns → error, extra columns → silently dropped); data validation follows the configured mode. | AP-5, FR-VAL-001 through FR-VAL-009 |

---

## 4. Known Limitations & Future Considerations

These are architectural limitations — constraints that would require structural changes to the system to address. Feature gaps that can be added within the current architecture belong in the requirements backlog, not here.

---

**Limitation 1: No Streaming Ingestion**

The architecture supports batch ingestion only. Data is loaded as DataFrames or files in discrete operations. Integrating streaming sources (Kafka, Kinesis) would require a new ingestion path: a consumer process that reads from a stream and writes to the offline store continuously. The append-only Parquet design supports this future path — new data always creates new files — but the consumer process itself does not exist. (Traces to: NG-2)

---

**Limitation 2: No Concurrent Write Safety**

Multiple processes ingesting data simultaneously to the same feature group could create interleaving issues. The unique file naming pattern (KTD-11) prevents file overwrites, but there is no locking mechanism to guarantee ordering or atomicity across concurrent ingestions. For the MVP, the assumption is single-process, single-user operation (AP-7). Adding multi-writer safety would require a coordination mechanism (file locks, distributed locks for S3, DynamoDB conditional writes).

---

**Limitation 3: No Incremental Materialization**

Materialization reads the entire offline store for a feature group, extracts the latest per entity, and fully overwrites the online store. For feature groups with large offline stores, this becomes slow as data grows. The architecture supports a future incremental mode (only materialize records since the last materialization timestamp, per FR-MAT-006), but tracking "last materialized timestamp" and implementing incremental merge-into-online-store are not built.

---

**Limitation 4: Single Join Only**

`get_historical_features()` in the MVP supports joining the base group with one other group. **This is enforced at runtime:** BB-02 validates `len(join) ≤ 1` during parameter validation and rejects calls with more than one joined group (FR-OFF-009). The check is isolated in a single validation step, making it straightforward to relax when multi-join is implemented. Multi-join — joining the base with multiple feature groups simultaneously — would require chaining PIT joins, managing column namespace conflicts across multiple groups, and extending the `select` dictionary to handle more than two groups. The architecture does not prevent this, but the implementation is not built.

---

**Limitation 5: No Feature Versioning or Schema Evolution**

Changing a feature group's schema (adding/removing features, changing types) after data has been ingested requires re-ingesting all data. There is no migration path — old Parquet files have the old schema, and the system does not perform schema reconciliation on read. The registry tracks the current schema; historical data may not match after a schema change. Adding schema evolution would require either: (a) read-time schema reconciliation (fill missing columns with nulls, drop removed columns), or (b) a migration tool that rewrites existing Parquet files.

---

**Limitation 6: No Offline Store Compaction**

The append-only offline store grows indefinitely. Over time, partitions accumulate many small Parquet files (one per ingestion per partition). This affects read performance — though PyArrow handles multi-file reads efficiently, the overhead of opening many files is non-zero. A compaction operation (merge small files into larger ones within a partition, preserving all records) would improve read performance. The append-only invariant makes compaction safe — the compacted file contains the same data as the originals.

---

**Limitation 7: No Online Store TTL or Eviction**

Materialized data persists in the online store until the next materialization overwrites it. There is no time-to-live (TTL) or automatic eviction of stale data. If materialization is not run for an extended period, the online store serves increasingly outdated feature values without any warning. Adding a staleness check (comparing `event_timestamp` to current time) would require a serving-time validation step — currently no validation runs on the online serving path by design.

---

**Limitation 8: No Entity Key Filtering in Historical Retrieval**

The `where` parameter in `get_historical_features()` uses the unified where format (`{field: {operator: value}}` — see FR-OFF-007), which structurally supports arbitrary field names. However, the MVP restricts `get_historical_features()` to accept only `event_timestamp` as a field name. Entity key filtering (e.g., retrieving training data for specific towns or specific listings only) is not supported at the query level. Users can filter the returned DataFrame in Python after retrieval. Adding entity key filtering requires only relaxing the per-method validation rule to accept additional field names and passing the predicates through to the partition reader — no API signature or format change needed.

---

**Limitation 9: DynamoDB Materialization Entity Key Limit**

The AWS provider uses DynamoDB `TransactWriteItems` for atomic materialization writes (NFR-REL-002). `TransactWriteItems` supports a maximum of 100 actions per transaction. Because materialization requires both `Delete` actions (for existing items) and `Put` actions (for new items), the effective limit is ~50 entity keys per feature group (100 actions ÷ 2 actions per entity). The MVP reference use case (6 entities per feature group) is well within this limit. For feature groups exceeding ~50 entity keys, a future version could implement chunked `TransactWriteItems` calls (each chunk atomic, but the overall operation would not be atomic across chunks) or fall back to `BatchWriteItem` with retry logic — at the cost of relaxing the per-operation atomicity guarantee.

---

**Limitation 10: Null Structural Column Checks Are Ingestion-Only**

Null checks for `entity_key` and `event_timestamp` run at ingestion (Phase 1, BB-05) and are mode-independent — they always abort if null values are found. However, these checks do not run again at retrieval (`get_historical_features`). The retrieval path trusts that the offline store is structurally valid, because `ingest()` is the only supported write path and its Phase 1 check is always-on. Data written to the offline store by bypassing `ingest()` — such as manually placed Parquet files or future direct-write tooling — would not be subject to this check and could introduce null structural column values that surface as runtime errors during partition derivation or point-in-time joins. A future version could add a defensive null check at the start of the retrieval path, but this is not implemented in the MVP.

---

## Appendix A: Traceability — Components to Stories

> _Maps building block internal components to requirements. More
> granular than the building-block-to-epic mapping in
> [docs-03-01 Appendix B](docs-03-01-architecture-overview.md)._

| Building Block | Internal Component | Requirements | Story |
| --- | --- | --- | --- |
| BB-01: CLI | Click command group + project root resolver | FR-CLI-001, FR-CLI-002 | TBD |
| BB-01: CLI | `init` scaffold creation | FR-CLI-002 | TBD |
| BB-01: CLI | Per-command delegation to SDK | FR-CLI-003 through FR-CLI-010 | TBD |
| BB-02: SDK | `FeatureStore.__init__` (config + provider wiring) | FR-CFG-001, FR-PROV-001 | TBD |
| BB-02: SDK | `apply()` orchestration | FR-REG-002 | TBD |
| BB-02: SDK | `ingest()` orchestration | FR-ING-001, FR-ING-002, FR-ING-003 | TBD |
| BB-02: SDK | `get_historical_features()` orchestration | FR-OFF-002, FR-OFF-003, FR-OFF-006 | TBD |
| BB-02: SDK | `get_online_features()` orchestration | FR-ONL-002 | TBD |
| BB-02: SDK | `materialize()` orchestration | FR-MAT-001 | TBD |
| BB-03: Definition Module | `FeatureGroup` frozen dataclass | FR-DEF-001, FR-DEF-003, FR-DEF-006, FR-DEF-007 | TBD |
| BB-03: Definition Module | `EntityKey` + `EventTimestamp` | FR-DEF-001, FR-DEF-007 | TBD |
| BB-03: Definition Module | `Feature` + `FeatureType` | FR-DEF-001, FR-DEF-002 | TBD |
| BB-03: Definition Module | `Expect` fluent builder | FR-DEF-004 | TBD |
| BB-03: Definition Module | `ValidationMode` defaults | FR-DEF-005, FR-VAL-009 | TBD |
| BB-03: Definition Module | `JoinKey` | FR-OFF-004 | TBD |
| BB-04: Registry Manager | Definition discovery (importlib) | FR-REG-002, FR-REG-003 | TBD |
| BB-04: Registry Manager | Definition validator (structural) | FR-DEF-004, FR-DEF-007, FR-REG-004 | TBD |
| BB-04: Registry Manager | Registry serializer (deterministic JSON) | FR-REG-001 | TBD |
| BB-04: Registry Manager | Lookup methods | FR-REG-005, FR-REG-006 | TBD |
| BB-04: Registry Manager | Query param validation | FR-OFF-002, FR-OFF-008, FR-ONL-002 | TBD |
| BB-05: Validation Engine | Schema validator | FR-ING-002 | TBD |
| BB-05: Validation Engine | Data validator (type + expectations) | FR-VAL-001, FR-VAL-002 | TBD |
| BB-05: Validation Engine | Mode handler (ERROR/FILTER/NONE) | FR-VAL-003, FR-VAL-004, FR-VAL-005, FR-VAL-006 | TBD |
| BB-05: Validation Engine | Validation report builder | FR-VAL-007 | TBD |
| BB-05: Validation Engine | Expectation evaluators | FR-VAL-008 | TBD |
| BB-06: Offline Store Manager | Partition manager (year/month derivation) | FR-ING-006 | TBD |
| BB-06: Offline Store Manager | File namer | FR-ING-007 | TBD |
| BB-06: Offline Store Manager | Write orchestrator (append-only) | FR-ING-004 | TBD |
| BB-06: Offline Store Manager | Read orchestrator + partition pruner | FR-OFF-001, FR-OFF-002 | TBD |
| BB-06: Offline Store Manager | Where filter | FR-OFF-007 | TBD |
| BB-07: Online Store Manager | Latest-per-entity extractor | FR-MAT-001 | TBD |
| BB-07: Online Store Manager | Write orchestrator (full overwrite) | FR-MAT-001, FR-MAT-003 | TBD |
| BB-07: Online Store Manager | Read orchestrator (key lookup) | FR-ONL-001, FR-ONL-002 | TBD |
| BB-08: Join Engine | PIT join via `pd.merge_asof` | FR-OFF-003, FR-OFF-005, FR-OFF-008 | TBD |
| BB-09: Provider Layer | `StorageProvider` ABC | FR-PROV-001, FR-PROV-005 | TBD |
| BB-09: Provider Layer | `LocalProvider` | FR-PROV-002, FR-PROV-003 | TBD |
| BB-09: Provider Layer | `AWSProvider` | FR-PROV-002, FR-PROV-004 | TBD |
| BB-10: Configuration Manager | YAML loader + validator | FR-CFG-001, FR-CFG-003, FR-CFG-004, FR-CFG-006 | TBD |
| BB-10: Configuration Manager | Environment variable overrides | FR-CFG-005 | TBD |

---

## Changelog

| Date | Author | Changes |
| --- | --- | --- |
| 2026-03-31 | Fedai Paça | Initial draft |
