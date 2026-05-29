# Feature 8: Local offline store historical retrieval without joins

## Goal

Let users read historical feature rows from one registered group as a Pandas DataFrame, with event-timestamp filtering, so they can build training datasets from a single feature group.

## Description

`FeatureStore.get_historical_features()` (no-join path) validates the request, applies a base event-timestamp filter to a partition-pruned read from the local offline store, runs offline retrieval validation, and returns a Pandas DataFrame with the requested feature columns plus base structural columns.

## Scope

- IN: SDK `get_historical_features` without `join`, `select` as list or `["*"]` for all, event-timestamp `where` with `gt`/`gte`/`lt`/`lte`, partition pruning, retrieval validation, local `OfflineStore.read()` via `pyarrow.dataset`.
- NOT IN: Point-in-time joins (Feature 9), AWS reads, online retrieval, any storage write.

## Expected output

A user can call `store.get_historical_features(from_="listing_features", select=["net_area", "number_of_rooms", "build_year", "sold_price"], where={"sold_at": {"gte": ..., "lte": ...}})` and get a Pandas DataFrame containing `listing_id`, `sold_at`, `town_id`, plus the four selected features, filtered to the requested time range.

## Implements

`FeatureStore.get_historical_features` (no-join path), local `OfflineStore.read`, `TimestampFilter`, `RetrievalParameterError`, `OfflineStoreReadError` — as declared in `contracts.py`.

## Dependencies

Feature 6, Feature 7.

## Behavior

1. Require `select`; raise `RetrievalParameterError` when missing.
2. Resolve `from_` from the registry; raise `FeatureGroupNotFoundError` if absent.
3. Reject dict-shaped `select` in the no-join path; accept `list[str]` or `["*"]` to select all features. Lists such as `["*", "net_area"]` are invalid.
4. Validate every name in a list `select` is a declared feature field of the base group.
5. Accept `where=None` (no filter) and `where={event_timestamp_name: {op: datetime}}` with operators in `{gt, gte, lt, lte}` and datetime values; reject any other field or operator with `RetrievalParameterError` before reading.
6. Build a `TimestampFilter` from `where`.
7. Call local `OfflineStore.read()` with the group name, event timestamp column, expected PyArrow schema, and the filter; the read uses `pyarrow.dataset` with Hive partitioning and pushes the filter down to partition pruning where possible.
8. If no rows exist, return an empty DataFrame whose columns are the expected base structural columns plus the resolved `select` columns.
9. Always include base structural columns: entity key, event timestamp, and any declared join key columns.
10. Resolve `["*"]` to all declared feature fields of the base group.
11. Run the validation engine on the result using the group's `offline_retrieval_validation` mode.
12. Return a Pandas DataFrame containing the structural columns plus the selected feature columns, all unprefixed.

## Error Handling

| Error                       | When                                                                                                                                                                                                | Behavior              |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| `RetrievalParameterError`   | `select` missing, list contains non-feature, raw string `"*"`, list contains `"*"` plus other fields, `where` field is not the event timestamp, unsupported operator, or dict `select` without join | Raise before any read |
| `FeatureGroupNotFoundError` | Base group not in registry                                                                                                                                                                          | Raise before any read |
| `OfflineStoreReadError`     | Provider cannot read offline data                                                                                                                                                                   | Raise                 |
| `ValidationError`           | Retrieval validation rejects rows in `ERROR`                                                                                                                                                        | Raise                 |

## Example

Input: After ingesting the Turkish real estate `listing_features`, call

```python
store.get_historical_features(
    from_="listing_features",
    select=["net_area", "sold_price"],
    where={"sold_at": {"gte": datetime(2024, 2, 1, tzinfo=timezone.utc),
                       "lte": datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)}},
)
```

Output: a Pandas DataFrame with columns `listing_id`, `sold_at`, `town_id`, `net_area`, `sold_price` and rows whose `sold_at` falls in February–December 2024.

## BDD Scenarios

```gherkin
Scenario: Retrieve selected listing features for training
  Given valid "listing_features" rows have been ingested
  When the user calls get_historical_features from "listing_features" with select ["net_area", "sold_price"]
  Then no exception is raised
  And the result columns are ["listing_id", "sold_at", "town_id", "net_area", "sold_price"]

Scenario: Retrieve all listing feature fields
  Given valid "listing_features" rows have been ingested
  When the user calls get_historical_features from "listing_features" with select ["*"]
  Then no exception is raised
  And the result includes columns "listing_id", "sold_at", "town_id", "net_area", "number_of_rooms", "build_year", and "sold_price"

Scenario: Filter listing rows by sold_at range
  Given valid "listing_features" rows have been ingested
  When the user retrieves listing features where sold_at is between 2024-04-01T00:00:00Z and 2024-04-30T23:59:59Z
  Then no exception is raised
  And every returned row has sold_at in April 2024

Scenario: Empty time range returns expected columns
  Given "listing_features" is registered
  And no listing rows exist for December 2030
  When the user retrieves "net_area" and "sold_price" for December 2030
  Then no exception is raised
  And the result has zero rows

Scenario: Unknown selected feature is rejected
  Given "listing_features" is registered
  When the user calls get_historical_features from "listing_features" with select ["city_name"]
  Then RetrievalParameterError is raised
  And the error message contains "city_name"
  And the error message contains "feature"

Scenario: Filter on a non-timestamp column is rejected
  Given "listing_features" is registered
  When the user filters on "town_id" with gte 1
  Then RetrievalParameterError is raised
  And the error message contains "town_id"
```
