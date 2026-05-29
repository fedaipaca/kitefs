# Feature 11: Local online store retrieval

## Goal

Serve the latest stored feature values for a single entity key from the local online store so backend applications can power real-time predictions with millisecond lookups.

## Description

`FeatureStore.get_online_features()` validates a single-entity-key request, looks the entity up in the SQLite online store, and returns a dict of structural plus selected feature fields on hit, or an empty dict on miss (not an error). No row-level validation runs on the serving path.

## Scope

- IN: SDK `get_online_features`, request shape validation (entity key field, `eq` operator, type compatibility, registered `select`), local `OnlineStore.get` (SQLite point lookup), empty-dict miss semantics.
- NOT IN: Batch online retrieval (post-MVP), row-level validation, DynamoDB.

## Expected output

After `town_market_features` is materialized, calling

```python
store.get_online_features(from_="town_market_features", select=["avg_price_per_sqm"], where={"town_id": {"eq": 1}})
```

returns a dict with `town_id`, `event_timestamp`, and `avg_price_per_sqm`. A lookup for a `town_id` that does not exist returns `{}`.

## Implements

`FeatureStore.get_online_features`, local `OnlineStore.get`, `OnlineStoreReadError`, `RetrievalParameterError` — as declared in `specs/interfaces.py`.

## Dependencies

Feature 10.

## Behavior

1. Resolve the target group from the registry; raise `FeatureGroupNotFoundError` if missing.
2. Reject groups whose `storage_target` is `OFFLINE` with `FeatureGroupNotMaterializableError`.
3. Require `select`. Accept `list[str]` or `["*"]`. Reject mixed wildcard selections like `['*', 'feature_name']`.
4. Validate every name in a list `select` is a declared feature field of the group.
5. Require `where` to contain exactly one entry whose field name equals the group's registered entity key.
6. Require the only operator to be `eq` and the value to be a single literal that is type-compatible with the entity key dtype.
7. Resolve `["*"]` to all structural plus all declared feature fields.
8. Extract the entity key value and perform a SQLite primary-key lookup on the group's table.
9. On miss, return `{}`. If the group's table does not exist (group never materialized), also return `{}`.
10. On hit, return a dict containing the entity key, event timestamp, the join key (if declared), and the selected feature fields, with values converted to standard Python types.
11. Do not run the validation engine; serving must stay fast.

## Error Handling

| Error                                | When                                                                                                       | Behavior                            |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| `FeatureGroupNotFoundError`          | Group not in registry                                                                                      | Raise                               |
| `FeatureGroupNotMaterializableError` | Group is `OFFLINE`-only                                                                                    | Raise                               |
| `RetrievalParameterError`            | `where` field is not entity key, operator is not `eq`, value type mismatch, or `select` missing or invalid | Raise                               |
| `OnlineStoreReadError`               | SQLite lookup fails (corrupt database, etc.)                                                               | Raise wrapping the underlying error |
| Miss                                 | Entity key value has no row                                                                                | Return `{}`                         |

## Example

Input (Turkish real estate): backend serves a recommendation for a new listing in Kadıköy (`town_id = 1`) on 2025-06-05:

```python
store.get_online_features(from_="town_market_features", select=["avg_price_per_sqm"], where={"town_id": {"eq": 1}})
```

Output: `{"town_id": 1, "event_timestamp": datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc), "avg_price_per_sqm": 27800.0}`.

Input: same call with `where={"town_id": {"eq": 999}}` (no such town).
Output: `{}`.

## BDD Scenarios

```gherkin
Scenario: Retrieve market feature for prediction
  Given "town_market_features" has been materialized with a row for town_id 1
  When the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 1
  Then no exception is raised
  And the result contains town_id 1
  And the result contains "event_timestamp"
  And the result contains "avg_price_per_sqm"

Scenario: Online miss returns an empty dict
  Given "town_market_features" has been materialized without a row for town_id 999
  When the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 999
  Then no exception is raised
  And the result is {}

Scenario: Never-materialized table returns an empty dict
  Given "town_market_features" is registered with storage_target OFFLINE_AND_ONLINE
  And "town_market_features" has not been materialized
  When the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 1
  Then no exception is raised
  And the result is {}

Scenario: Offline-only group is rejected for online retrieval
  Given "listing_features" is registered with storage_target OFFLINE
  When the user calls get_online_features from "listing_features" with select ["net_area"] where listing_id equals 1002
  Then FeatureGroupNotMaterializableError is raised
  And the error message contains "listing_features"
  And the error message contains "OFFLINE"

Scenario: Filter on a non-entity-key field is rejected
  Given "town_market_features" is registered with entity key "town_id"
  When the user calls get_online_features with where avg_price_per_sqm equals 24500.0
  Then RetrievalParameterError is raised
  And the error message contains "avg_price_per_sqm"
  And the error message contains "town_id"
```
