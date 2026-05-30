# Feature 5: Local registry list and describe

## Goal

Let users discover which feature groups are registered and inspect a single group in detail through both the SDK and the CLI.

## Description

`FeatureStore.list_feature_groups()` returns one `FeatureGroupSummary` per registered group. `FeatureStore.describe_feature_group(name)` returns the full `FeatureGroupDescription` for a single name. The CLI `list` and `describe` commands wrap these and support text and JSON output, plus writing the rendered output to a file.

## Scope

- IN: SDK `list_feature_groups`, SDK `describe_feature_group`, CLI `kitefs list` and `kitefs describe` with `--format text|json` and `--output PATH`, conversion of registry datetime strings to `datetime.datetime`.
- NOT IN: Remote registry reads, mutating the registry, validation, storage I/O beyond reading the registry.

## Expected output

After `apply`, `store.list_feature_groups()` returns summaries for `listing_features` and `town_market_features`. `store.describe_feature_group("town_market_features")` returns the full description including its single feature `avg_price_per_sqm` and its expectations. `kitefs list --format json` prints the JSON array; `kitefs describe town_market_features` prints a human-readable text rendering.

## Implements

`FeatureStore.list_feature_groups`, `FeatureStore.describe_feature_group`, `FeatureGroupSummary`, `FeatureGroupDescription`, `FieldSpec`, `JoinKeySpec`, `MetadataSpec`, `RegistryStore.read` (local), CLI `list`/`describe` subcommands, `FeatureGroupNotFoundError`, `RegistryReadError` — as declared in `contracts.py`.

## Dependencies

Feature 4.

## Behavior

1. `list_feature_groups`: read the active registry through `RegistryStore.read()`. Return an empty list when `feature_groups` is empty.
2. For each registered group, build a `FeatureGroupSummary` with name, owner, description, entity key name, storage target, and feature count.
3. Return summaries sorted alphabetically by name.
4. `describe_feature_group(name)`: read the registry; if `name` is not present, raise `FeatureGroupNotFoundError` and include the set of valid names in the message.
5. Build `FeatureGroupDescription` from the registry entry, including `FieldSpec` for entity key, event timestamp, and each feature; `JoinKeySpec` for each join key; `MetadataSpec` for metadata; and parse `applied_at`/`last_materialized_at` strings into `datetime.datetime`.
6. CLI `list` renders text (a tabular human-readable summary) by default and JSON when `--format json`.
7. CLI `describe` renders text by default and JSON when `--format json`. JSON output mirrors the registry entry shape.
8. CLI `--output PATH` writes the rendered output to the file path instead of stdout.

## Error Handling

| Error                       | When                                   | Behavior                                          |
| --------------------------- | -------------------------------------- | ------------------------------------------------- |
| `RegistryReadError`         | Registry file missing or undecodable   | Message suggests `kitefs init` and `kitefs apply` |
| `FeatureGroupNotFoundError` | `describe` target name not in registry | Message names the group and lists the valid names |
| Invalid CLI flag            | `--format` not `text` or `json`        | Click rejects before SDK work                     |

## Example

Input: `kitefs list --format json` after applying the reference use case definitions.
Output (excerpt):

```json
[
  {
    "name": "listing_features",
    "owner": "data-science-team",
    "entity_key": "listing_id",
    "storage_target": "OFFLINE",
    "feature_count": 4
  },
  {
    "name": "town_market_features",
    "owner": "data-science-team",
    "entity_key": "town_id",
    "storage_target": "OFFLINE_AND_ONLINE",
    "feature_count": 1
  }
]
```

Input: `kitefs describe town_market_features --format json`.
Output: a JSON object whose `entity_key.name` is `"town_id"`, `features[0].name` is `"avg_price_per_sqm"`, and `storage_target` is `"OFFLINE_AND_ONLINE"`.

## BDD Scenarios

```gherkin
Scenario: List registered reference feature groups
  Given "listing_features" and "town_market_features" have been applied
  When the user runs "kitefs list"
  Then the command exits 0
  And stdout contains "listing_features"
  And stdout contains "town_market_features"

Scenario: List returns an empty result for an empty registry
  Given the registry contains no feature groups
  When the user calls FeatureStore().list_feature_groups()
  Then the result is an empty list

Scenario: Describe a registered feature group as JSON
  Given "town_market_features" has been applied
  When the user runs "kitefs describe town_market_features --format json"
  Then the command exits 0
  And stdout is a JSON object
  And the JSON output has entity_key.name "town_id"
  And the JSON output has storage_target "OFFLINE_AND_ONLINE"
  And the JSON output contains feature "avg_price_per_sqm"
  And the JSON output has metadata owner "data-science-team"
  And the JSON output has feature "avg_price_per_sqm" with expect constraints

Scenario: Describe an unknown feature group
  Given the registry contains only "listing_features" and "town_market_features"
  When the user runs "kitefs describe neighborhood_features"
  Then the command exits non-zero
  And stderr contains "neighborhood_features"
  And stderr contains "listing_features"
  And stderr contains "town_market_features"
```
