# Feature 16: Remote materialization and online store retrieval (DynamoDB)

## Goal

Make `materialize` and `get_online_features` work against DynamoDB so production serving applications can read the latest feature values from AWS through the same SDK calls used locally.

## Description

Implements `OnlineStore.materialize` and `OnlineStore.get` for AWS: one DynamoDB table per online-capable feature group named `{dynamodb_table_prefix}{group_name}`. Materialization lazily creates the table, writes in batches of up to 25 items with one retry on `UnprocessedItems`, and updates `last_materialized_at` on full success. Reads use `GetItem` and return `{}` on miss or missing table.

## Scope

- IN: DynamoDB table lifecycle (`DescribeTable`/`CreateTable` with `PAY_PER_REQUEST`, wait for `ACTIVE`, partition-key validation), `BatchWriteItem` materialization with single retry, `GetItem` reads, DynamoDB type mapping (`S`/`N`) and datetime serialization, provider-level failure reporting through `MaterializeResult`.
- NOT IN: Batch online retrieval (post-MVP), provisioned billing settings, table deletion, custom retry/backoff strategies.

## Expected output

With `runtime.target: remote`, `store.materialize("town_market_features")` writes one DynamoDB item per `town_id` to the table `{dynamodb_table_prefix}town_market_features`. `store.get_online_features(from_="town_market_features", select=["avg_price_per_sqm"], where={"town_id": {"eq": 5}})` returns a dict containing the latest values, or `{}` on miss / missing table.

## Implements

AWS `OnlineStore.materialize`, AWS `OnlineStore.get`, AWS-side wiring of `FeatureStore.materialize` and `FeatureStore.get_online_features` — as declared in `specs/interfaces.py`.

## Dependencies

Feature 10, Feature 11, Feature 13, Feature 15.

## Behavior

1. Use one DynamoDB table per online-capable feature group, named `{dynamodb_table_prefix}{group_name}` (default prefix `kitefs_`).
2. Use the group's entity key as the partition key; no sort key.
3. Before writing, call `DescribeTable`. If the table does not exist, call `CreateTable` with the partition-key schema derived from the entity key dtype and billing mode `PAY_PER_REQUEST`, then wait for `ACTIVE`.
4. If the table exists, validate its partition-key name and type match the registered entity key and there is no sort key; mismatches fail with an actionable error.
5. Map `INTEGER` and `FLOAT` to DynamoDB `N`; `STRING` and `DATETIME` to `S`. Datetimes serialize as `YYYY-MM-DDTHH:MM:SS.ffffffZ`. Omit absent attributes (DynamoDB null representation).
6. Compute the latest row per entity key from the offline data (reusing the BB-07 manager logic from Feature 10).
7. Split the latest rows into chunks of at most 25 items and call `BatchWriteItem` with `PutRequest` entries per chunk.
8. If `BatchWriteItem` returns `UnprocessedItems`, retry those items once after a short delay; if items are still unprocessed, mark the group as failed.
9. On full success across all chunks, let the caller update `last_materialized_at` in the local working registry.
10. On failure, add a `FailedGroup` to `MaterializeResult` with the underlying error message; partial items written before the failure may remain visible. Re-running materialization overwrites them.
11. `OnlineStore.get` issues a single `GetItem` keyed by entity key value. On hit, return a dict containing entity key, event timestamp, join key (if declared), and the selected feature attributes.
12. If the table does not exist or the item is absent, return `{}`. Do not raise on miss.
13. User-facing request validation (Feature 11 rules) runs before the DynamoDB call; unknown groups, offline-only groups, and unknown feature fields raise before any AWS call.
14. The AWS provider requires IAM permissions for `dynamodb:DescribeTable`, `dynamodb:CreateTable`, `dynamodb:BatchWriteItem`, `dynamodb:PutItem`, and `dynamodb:GetItem` on tables matching the configured prefix.

## Error Handling

| Error                   | When                                                                    | Behavior                                                             |
| ----------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `ConfigurationError`    | `remote.online_store` missing for an operation that needs it            | Raise before any AWS call                                            |
| `OnlineStoreWriteError` | Existing table's partition key does not match the registered entity key | Raise; group is marked failed in `MaterializeResult`                 |
| `OnlineStoreWriteError` | `BatchWriteItem` fails or `UnprocessedItems` persist after one retry    | Wrap underlying error; group marked failed; partial items may remain |
| `OnlineStoreReadError`  | `GetItem` fails for reasons other than missing item                     | Raise with actionable message                                        |
| Miss / missing table    | Item not found or table does not exist                                  | Return `{}`                                                          |
| `ProviderError`         | AWS credentials missing or invalid                                      | Raise without leaking secrets                                        |

## Example

Input: remote `store.materialize("town_market_features")` after offline rows for towns 1–6 across 12 months exist on S3.
Output: DynamoDB table `kitefs_town_market_features` contains 6 items (one per `town_id`), each carrying the latest `event_timestamp` and `avg_price_per_sqm`. `MaterializeResult.succeeded` contains `"town_market_features"`.

Input: subsequent serving call

```python
store.get_online_features(from_="town_market_features", select=["avg_price_per_sqm"], where={"town_id": {"eq": 5}})
```

Output: `{"town_id": 5, "event_timestamp": datetime(2025, 7, 1, 0, 0, 0, tzinfo=timezone.utc), "avg_price_per_sqm": 15200.0}`.

Input: same call with `where={"town_id": {"eq": 999}}` (no item) or against a table that has never been materialized.
Output: `{}`.

## BDD Scenarios

```gherkin
Scenario: Remote materialize makes latest town market rows available online
  Given runtime.target resolves to "remote"
  And remote offline data exists for "town_market_features" with 72 rows for 12 months and 6 towns
  And the remote online store table prefix is "kitefs_"
  When the user calls store.materialize("town_market_features")
  Then no exception is raised
  And result.succeeded contains "town_market_features"
  And a later online lookup for each town returns that town's latest market row

Scenario: Remote online retrieval returns a hit
  Given runtime.target resolves to "remote"
  And the remote online store contains town_id 5 with avg_price_per_sqm 15200.0 and event_timestamp 2025-07-01T00:00:00Z
  When the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 5
  Then no exception is raised
  And the result contains town_id 5
  And the result contains avg_price_per_sqm 15200.0
  And the result contains event_timestamp 2025-07-01T00:00:00Z

Scenario: Remote online miss returns an empty dict
  Given runtime.target resolves to "remote"
  And the remote online store has no item for town_id 999
  When the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 999
  Then no exception is raised
  And the result is {}

Scenario: Remote online retrieval from a never-materialized group returns an empty dict
  Given runtime.target resolves to "remote"
  And "town_market_features" has never been materialized to the remote online store
  When the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 1
  Then no exception is raised
  And the result is {}

Scenario: Existing remote online table with wrong key schema fails materialization for the group
  Given runtime.target resolves to "remote"
  And remote offline data exists for "town_market_features"
  And the remote online table for "town_market_features" has partition key "city_id"
  When the user calls store.materialize("town_market_features")
  Then no exception is raised
  And result.failed contains a group named "town_market_features"
  And the failure message contains "partition key"
  And the failure message contains "town_id"

Scenario: Missing remote online configuration fails clearly
  Given runtime.target resolves to "remote"
  And remote.online_store is absent
  When the user calls store.materialize("town_market_features")
  Then ConfigurationError is raised
  And the error message contains "remote online"

Scenario: Remote online read failures are surfaced
  Given runtime.target resolves to "remote"
  And "town_market_features" is registered as online-capable
  And the remote online read fails with "AccessDenied"
  When the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 1
  Then OnlineStoreReadError is raised
  And the error message contains "AccessDenied"
``ري
```
