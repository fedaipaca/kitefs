---
description: "Use when creating or modifying feature group definitions, Feature, EntityKey, EventTimestamp, Expect, or related definition types."
applyTo: "**/definitions/**,**/definitions.py"
---
# Feature Group Definitions — Module-Specific Additions

Follows all rules in `copilot-instructions.md`.

## Structural Columns

`entity_key` and `event_timestamp` are **required constructor parameters** on `FeatureGroup`, not part of the `features` list. The type system enforces exactly-one of each. The `features` list contains only homogeneous `Feature` instances.

## Field Name Uniqueness

All field names within a `FeatureGroup` must be unique across: entity key name, event timestamp name, and all feature names. Duplicates are caught at `apply()` time by the registry manager.

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
