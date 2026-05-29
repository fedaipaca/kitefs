# Feature 4: Local registry apply

## Goal

Compile the user's Python feature definitions into a deterministic local registry so every later operation (list, describe, ingest, retrieve, materialize, serve) has one canonical source of truth.

## Description

`FeatureStore.apply()` discovers `FeatureGroup` objects in `./feature_store/definitions/*.py`, validates the full set as a single unit, preserves runtime-managed metadata for groups already in the registry, and atomically writes the local registry JSON.

## Scope

- IN: Definition discovery (import each `.py` and collect module-level `FeatureGroup` instances), cross-definition validation, preservation of `last_materialized_at`, `applied_at` update, deterministic JSON serialization, `FeatureStore.apply(publish=False)`.
- NOT IN: `--publish` remote write, CLI confirmation prompt, list/describe, any data store I/O.

## Expected output

After dropping `listing_features.py` and `town_market_features.py` from the reference use case into `./feature_store/definitions/`, calling `FeatureStore().apply()` writes a `./feature_store/registry.json` containing both groups with `applied_at` set, and returns an `ApplyResult` listing both group names alphabetically.

## Implements

`FeatureStore.apply` (local path), `ApplyResult`, `DefinitionDiscoveryError`, `DefinitionValidationError`, `RegistryWriteError` (as declared in `contracts.py`). Internal Registry Manager (discovery + cross-validation + artifact builder).

## Dependencies

Feature 1, Feature 3.

## Behavior

1. Scan `./feature_store/definitions/*.py` only (no recursion below that directory).
2. Import each Python file as a module; collect every module-level object that is an instance of `FeatureGroup`.
3. If zero `FeatureGroup` instances are discovered, raise `DefinitionDiscoveryError` with a message that suggests declaring a group.
4. Run cross-definition validation on the full discovered set. Aggregate every failure into a single `DefinitionValidationError`:
   - Duplicate group names.
   - Field names that collide with reserved partition columns `year` and `month`.
   - A `JoinKey.referenced_group` that does not exist in the discovered set.
   - `JoinKey.dtype` does not match the referenced group's `EntityKey.dtype`.
5. Read the existing local registry (if present) and preserve `last_materialized_at` for every group whose name still exists in the new set.
6. Set `applied_at` to the current UTC time for every group in the new set.
7. Sort each group's `features` and `join_keys` lists alphabetically by `name` before serialization.
8. Serialize with `json.dumps(sort_keys=True, indent=2, ensure_ascii=False)` plus trailing `\n`.
9. Write atomically via temp file + `os.replace()` through `RegistryStore.write()`.
10. Return `ApplyResult(registered_groups=<sorted list>, published=False)`.

## Error Handling

| Error                       | When                                        | Behavior                                                                                                   |
| --------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `DefinitionDiscoveryError`  | No `FeatureGroup` instances found           | Raise; registry unchanged; message suggests creating a definition                                          |
| `DefinitionValidationError` | Any cross-definition check fails            | Raise with all errors aggregated; registry unchanged                                                       |
| Import failure              | A definition `.py` cannot be imported       | Surface import failures as `DefinitionDiscoveryError` with the file path and the underlying error message. |
| `RegistryWriteError`        | Registry file cannot be replaced atomically | Raise; prior registry file preserved                                                                       |

## Example

Input: `./feature_store/definitions/` contains `listing_features.py` and `town_market_features.py` from the reference use case; the local registry is empty.
Output:

- `ApplyResult(registered_groups=["listing_features", "town_market_features"], published=False)`.
- `./feature_store/registry.json` contains both groups with `applied_at` set, `last_materialized_at` set to `null`, and `listing_features.join_keys[0].referenced_group == "town_market_features"`.

## BDD Scenarios

```gherkin
Scenario: Apply the reference feature definitions
  Given "listing_features.py" and "town_market_features.py" exist in "feature_store/definitions/"
  When the user calls FeatureStore().apply()
  Then no exception is raised
  And result.registered_groups equals ["listing_features", "town_market_features"]
  And result.published is False
  And "feature_store/registry.json" contains "listing_features"
  And "feature_store/registry.json" contains "town_market_features"

Scenario: Apply fails when no feature groups are discovered
  Given "feature_store/definitions/" contains no FeatureGroup definitions
  And the registry already contains "town_market_features"
  When the user calls FeatureStore().apply()
  Then DefinitionDiscoveryError is raised
  And the error message contains "FeatureGroup"
  And the error message contains "declare"
  And the registry still contains "town_market_features"

Scenario: Apply reports duplicate group names
  Given two definition files both declare a FeatureGroup named "town_market_features"
  And the registry already contains an empty registry
  When the user calls FeatureStore().apply()
  Then DefinitionValidationError is raised
  And the error message contains "town_market_features"
  And the error message contains "duplicate"
  And the registry remains an empty registry

Scenario: Apply rejects a missing join target
  Given "listing_features.py" references "town_market_features"
  And "town_market_features.py" is missing
  When the user calls FeatureStore().apply()
  Then DefinitionValidationError is raised
  And the error message contains "town_market_features"
  And the error message contains "referenced"
```
