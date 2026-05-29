# Feature 10: Local materialization

## Goal

Build the local SQLite online store from offline data so online-capable feature groups can be served with low-latency point lookups, with exactly one latest row per entity key.

## Description

`FeatureStore.materialize()` reads offline data for one named online-capable group or all online-capable groups, extracts the latest row per entity key by event timestamp, and atomically replaces the group's SQLite table contents. Per-group success updates `last_materialized_at` in the local working registry.

## Scope

- IN: BB-07 Online Store Manager (read offline + extract latest), local `OnlineStore.materialize` (SQLite per-group table replacement inside one transaction), `last_materialized_at` update, `MaterializeResult`/`SkippedGroup`/`FailedGroup`, all-groups and named-group runs.
- NOT IN: Online reads (Feature 11), DynamoDB (Feature 16), CLI command (covered in Feature 12), automatic/scheduled materialization.

## Expected output

After ingesting offline rows for `town_market_features`, calling `store.materialize("town_market_features")` populates the SQLite online store with exactly one row per `town_id`, each carrying the latest `event_timestamp` for that town. The returned `MaterializeResult.succeeded` contains `"town_market_features"`, and `last_materialized_at` is updated in the local registry.

## Implements

`FeatureStore.materialize`, `MaterializeResult`, `SkippedGroup`, `FailedGroup`, local `OnlineStore.materialize`, local `OfflineStore.read` (full-group read), `FeatureGroupNotMaterializableError`, `OnlineStoreWriteError`, BB-07 Online Store Manager — as declared in `specs/interfaces.py`.

## Dependencies

Feature 7 (offline data must exist), Feature 4 (registry).

## Behavior

1. Load configuration and the registry.
2. Resolve target groups:
   - Named: if group is not registered, raise `FeatureGroupNotFoundError` before processing; if registered but `OFFLINE`-only, raise `FeatureGroupNotMaterializableError` before processing.
   - All: every registered group whose `storage_target` is `OFFLINE_AND_ONLINE`. Offline-only groups are excluded from the target set and do not appear in the result.
3. For each target group:
   1. Read all offline rows for the group (no timestamp filter).
   2. If there are no rows, add a `SkippedGroup(name, "no offline data")`, preserve any existing online state, and continue.
   3. Extract the latest row per entity key by event timestamp. When two rows share the same entity key and the same event timestamp, the later-ingested row wins (determined by Parquet file write order in the partition).
   4. Open a SQLite connection on `./feature_store/data/online_store/online.db`. Create the per-group table if missing. Enable WAL mode on the connection.
   5. Inside one transaction per group: `DELETE FROM <group_name>`, `INSERT` the latest rows, `COMMIT`. On any error, rollback so the prior committed contents remain.
   6. On a successful commit, update `last_materialized_at` for that group in the local working registry to the current UTC time and persist the registry; add the group name to `MaterializeResult.succeeded`.
   7. On any failure, add a `FailedGroup(name, error_message)`, leave `last_materialized_at` unchanged, and continue with remaining targets.
4. Return `MaterializeResult(succeeded, skipped, failed)`. An all-groups run with no eligible groups returns an empty result.

## Error Handling

| Error                                | When                                 | Behavior                                                 |
| ------------------------------------ | ------------------------------------ | -------------------------------------------------------- |
| `FeatureGroupNotFoundError`          | Named group not in registry          | Raise before processing; nothing materialized            |
| `FeatureGroupNotMaterializableError` | Named group is `OFFLINE`-only        | Raise before processing; nothing materialized            |
| `OfflineStoreReadError`              | Offline data cannot be read          | Raise (offline read precedes per-group failure tracking) |
| Per-group SQLite write failure       | Transaction fails on a group         | Add `FailedGroup`; prior online state preserved          |
| No offline rows                      | A target group has zero offline rows | Add `SkippedGroup`; existing online state preserved      |

## Example

Input: `store.materialize("town_market_features")` after a year of monthly market rows for towns 1–6 have been ingested (72 offline rows: 12 months × 6 towns).
Output: `MaterializeResult(succeeded=["town_market_features"], skipped=[], failed=[])`. The SQLite table `town_market_features` has exactly 6 rows, one per `town_id`, each containing the December 2024 `avg_price_per_sqm` with `event_timestamp = 2025-01-01T00:00:00Z`. `last_materialized_at` in the local registry is updated to the current UTC time.

## BDD Scenarios

```gherkin
Scenario: Materialize the latest market row per town
  Given "town_market_features" has 72 offline rows for 12 months and 6 towns
  When the user calls store.materialize("town_market_features")
  Then no exception is raised
  And result.succeeded contains "town_market_features"
  And result.skipped is empty
  And result.failed is empty
  And SQLite table town_market_features has exactly 6 rows
  And the registry entry for "town_market_features" has last_materialized_at set

Scenario: Named materialization rejects an unknown group
  Given the registry contains only "town_market_features"
  When the user calls store.materialize("neighborhood_features")
  Then FeatureGroupNotFoundError is raised
  And the error message contains "neighborhood_features"

Scenario: Named materialization rejects an offline-only group
  Given "listing_features" is registered with storage_target OFFLINE
  When the user calls store.materialize("listing_features")
  Then FeatureGroupNotMaterializableError is raised
  And the error message contains "listing_features"
  And the error message contains "OFFLINE"

Scenario: Materialization skips a group with no offline data
  Given "town_market_features" is registered with storage_target OFFLINE_AND_ONLINE
  And "town_market_features" has no offline rows
  When the user calls store.materialize("town_market_features")
  Then no exception is raised
  And result.skipped contains a group named "town_market_features" with reason "no offline data"
  And result.succeeded is empty
  And result.failed is empty
```
