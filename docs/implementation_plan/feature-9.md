# Feature 9: Point-in-time historical retrieval with joins

## Goal

Let users build training datasets that combine two feature groups without leaking future data, by attaching to each base row the latest joined row whose event timestamp is at or before the base row's event timestamp.

## Description

Extends `get_historical_features` with a `join` parameter and a dict-keyed `select`. Reads base and joined data through the offline store, validates each side independently using its own retrieval validation mode, and runs the BB-08 Join Engine (stateless, in-memory) to produce one row per base row with prefixed joined columns.

## Scope

- IN: Join request validation, dict `select` shape, stateless point-in-time join, prefixed joined columns (`{joined_group}_{column}`), null joined columns when no match exists, deterministic row order.
- NOT IN: More than one joined group, AWS reads, online serving.

## Expected output

Calling `get_historical_features(from_="listing_features", join=["town_market_features"], select={...}, where={"sold_at": {...}})` returns a DataFrame where each listing row carries the `town_market_features_avg_price_per_sqm` from the latest market row for that town whose `event_timestamp` is ≤ the listing's `sold_at`. Base rows without an eligible match keep null joined columns.

## Implements

`FeatureStore.get_historical_features` (join path), Join Engine, `JoinError` — as declared in `contracts.py`.

## Dependencies

Feature 8.

## Behavior

1. Accept `join` as `None` or a list with at most one feature group name; reject more than one with `JoinError`.
2. Require dict `select` when `join` is provided; reject list `select` with `RetrievalParameterError`.
3. Require `select` to contain one key per group (base and joined). Each value must be a list of feature field names or ["*"] for that group. Raw string "\*" is invalid.
4. Validate every selected field is a declared feature of its group.
5. Validate that the base group declares a `JoinKey` whose `referenced_group` equals the joined group; otherwise raise `JoinError`.
6. Validate the joined group exists in the registry; otherwise raise `FeatureGroupNotFoundError`.
7. Read base offline data with the base `where` timestamp filter applied.
8. Read joined offline data without applying the base `where` filter (all joined rows are needed to find the latest eligible match).
9. Run retrieval validation on each side independently, using each group's own `offline_retrieval_validation` mode.
10. For each base row, find joined rows where the joined group's entity key equals the base row's join key value.
11. Among those, keep joined rows whose joined `event_timestamp` is `<=` the base row's `event_timestamp`. Select the row with the latest such joined `event_timestamp`.
12. Resolve equal-timestamp ties deterministically using ingestion order when available (later-ingested wins, mirroring materialization).
13. If no eligible joined row exists, keep the base row and set every joined column to null.
14. Prefix joined structural columns and selected joined feature columns with `{joined_group_name}_` in the output DataFrame. Base columns stay unprefixed.
15. Return a Pandas DataFrame with stable row order for unchanged data.

## Error Handling

| Error                       | When                                            | Behavior               |
| --------------------------- | ----------------------------------------------- | ---------------------- |
| `JoinError`                 | More than one joined group requested            | Raise; no data is read |
| `JoinError`                 | Base group has no `JoinKey` to the joined group | Raise; no data is read |
| `RetrievalParameterError`   | `select` is not a dict when `join` is provided  | Raise; no data is read |
| `FeatureGroupNotFoundError` | Joined group not in registry                    | Raise; no data is read |
| `ValidationError`           | Either side's retrieval validation rejects rows | Raise                  |

## Example

Input (Turkish real estate):

```python
store.get_historical_features(
    from_="listing_features",
    join=["town_market_features"],
    select={
        "listing_features": ["net_area", "number_of_rooms", "build_year", "sold_price"],
        "town_market_features": ["avg_price_per_sqm"],
    },
    where={"sold_at": {"gte": datetime(2024, 3, 1, tzinfo=timezone.utc),
                       "lte": datetime(2024, 5, 31, 23, 59, 59, tzinfo=timezone.utc)}},
)
```

Output: listing `1002` (sold `2024-04-05 14:00:00 UTC`, `town_id=1`) gets `town_market_features_avg_price_per_sqm` from the town 1 market row dated `2024-04-01T00:00:00Z` (not the `2024-05-01` row, which is in the future relative to the listing). Listing `1010` (sold `2024-01-20`, before the earliest market snapshot) keeps its base columns and `town_market_features_avg_price_per_sqm` is null.

## BDD Scenarios

```gherkin
Scenario: Latest eligible market row is selected for listing 1002
  Given listing_features contains listing 1002 sold on 2024-04-05 14:00:00 in town 1
  And town_market_features has rows for town 1 dated 2024-02-01, 2024-03-01, 2024-04-01, 2024-05-01
  When I retrieve listing features joined to town market features
  Then listing 1002 gets town_market_features_avg_price_per_sqm from the 2024-04-01 row
  And the 2024-05-01 market row is not used

Scenario: Base row with no eligible joined row keeps null joined columns
  Given listing 1010 was sold at 2024-01-20T17:00:00Z in town_id 3
  And the earliest "town_market_features" row is dated 2024-02-01T00:00:00Z
  When the user retrieves "listing_features" joined to "town_market_features"
  Then no exception is raised
  And the row for listing_id 1010 is present
  And town_market_features_avg_price_per_sqm is null for listing_id 1010

Scenario: More than one joined group is rejected
  Given "listing_features" is registered
  When the user calls get_historical_features with join ["town_market_features", "city_market_features"]
  Then JoinError is raised
  And the error message contains "at most one"

Scenario: List select is rejected when join is provided
  Given "listing_features" and "town_market_features" are registered
  When the user calls get_historical_features with join ["town_market_features"] and select ["net_area"]
  Then RetrievalParameterError is raised
  And the error message contains "select"
  And the error message contains "dict"

Scenario: Join without a registered relationship is rejected
  Given "town_market_features" and "city_market_features" are registered
  And "town_market_features" does not declare a join key to "city_market_features"
  When the user retrieves "town_market_features" joined to "city_market_features"
  Then JoinError is raised
  And the error message contains "city_market_features"
  And the error message contains "JoinKey"
```
