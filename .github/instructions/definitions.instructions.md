---
description: "Use when creating or modifying feature group definitions, Feature, EntityKey, EventTimestamp, Expect, or related definition types."
applyTo: "**/definitions/**,**/definitions.py"
---
# Feature Group Definitions

## Immutability (KTD-6)

All definition types are frozen dataclasses — immutable after creation:

```python
@dataclass(frozen=True)
class Feature:
    name: str
    dtype: FeatureType
    description: str | None = None
    expect: Expect | None = None
```

This applies to: `FeatureGroup`, `Feature`, `EntityKey`, `EventTimestamp`, `JoinKey`, `Metadata`, `Expect`.

## Structural Columns (KTD-16)

`entity_key` and `event_timestamp` are **required constructor parameters** on `FeatureGroup`, not part of the `features` list. The type system enforces exactly-one of each. The `features` list contains only homogeneous `Feature` instances.

See `docs/docs-03-03-api-contracts.md` for the full `FeatureGroup` constructor signature and all optional parameters.

## Field Name Uniqueness

All field names within a `FeatureGroup` must be unique across: entity key name, event timestamp name, and all feature names. Duplicates are caught at `apply()` time by BB-04.

## Expect Builder

`Expect` uses a fluent builder pattern. Each method returns a **new instance** (immutable):

```python
Expect().not_null().gt(0).lte(100)
Expect().one_of(["apartment", "house", "land"])
```

Available constraints: `not_null()`, `gt(v)`, `gte(v)`, `lt(v)`, `lte(v)`, `one_of(values)`.

## Enums

| Enum | Values | Notes |
|------|--------|-------|
| `FeatureType` | `STRING`, `INTEGER`, `FLOAT`, `DATETIME` | `DATETIME` is required for `EventTimestamp` |
| `StorageTarget` | `OFFLINE`, `OFFLINE_AND_ONLINE` | Controls materialization eligibility |
| `ValidationMode` | `ERROR`, `FILTER`, `NONE` | Ingestion default: `ERROR`; retrieval default: `NONE` |

## Discovery (KTD-8)

`apply()` discovers `FeatureGroup` instances via `importlib` — it imports definition modules and finds all module-level attributes that are `isinstance(obj, FeatureGroup)`. No decorators or registration calls needed.
