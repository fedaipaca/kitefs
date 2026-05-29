# Feature 15: Remote offline store ingestion and historical retrieval (S3)

## Goal

Make `FeatureStore.ingest` and `FeatureStore.get_historical_features` work against S3 in the same way they work locally, so users can produce and consume training datasets on AWS through the same SDK calls.

## Description

Implements `OfflineStore.write` and `OfflineStore.read` for AWS using the same Hive partition layout as local. Writes Parquet objects to `s3://{bucket}/{s3_prefix}/data/offline_store/{group}/year=YYYY/month=MM/{file}.parquet`. Reads use a PyArrow dataset over the S3 path, applying timestamp filters where possible.

## Scope

- IN: AWS `OfflineStore.write` (one full `PutObject` per Parquet file with `ing_` prefix), AWS `OfflineStore.read` (PyArrow dataset over S3 with Hive partitioning and timestamp filter push-down where possible), append-only behavior, `IngestResult.written_files` carrying `s3://` URIs.
- NOT IN: DynamoDB materialization (Feature 16), registry (Feature 14), streaming, MVP-out-of-scope huge-file handling.

## Expected output

With `runtime.target: remote` and a configured offline bucket, `store.ingest("listing_features", df)` writes Parquet objects to S3 under the partition layout above and `store.get_historical_features(...)` reads them back with the same shape and column names as the local provider. Join behavior is identical because the join engine is provider-agnostic.

## Implements

AWS `OfflineStore.write`, AWS `OfflineStore.read`, AWS-side wiring of `FeatureStore.ingest` and `FeatureStore.get_historical_features` — as declared in `specs/interfaces.py`.

## Dependencies

Feature 7, Feature 8, Feature 9, Feature 13.

## Behavior

1. Construct AWS S3 paths using `bucket` and `s3_prefix` from configuration. Object keys follow `{s3_prefix}/data/offline_store/{group}/year=YYYY/month=MM/ing_{YYYYMMDDTHHMMSS}_{short_id}.parquet`.
2. On `ingest`, partition rows by event timestamp year and month exactly as local does.
3. For each partition, build a Parquet payload in memory and write it as one full S3 `PutObject` (atomic per object — partial objects are never visible).
4. Set `IngestResult.written_files` to the list of `s3://...` URIs written by this call.
5. Existing S3 objects under the group's prefix are never modified or deleted (append-only).
6. On `get_historical_features`, read all Parquet objects under `s3://{bucket}/{s3_prefix}/data/offline_store/{group}/` using a PyArrow dataset configured for S3.
7. Apply the `TimestampFilter` through PyArrow dataset filtering and (where supported) Hive partition pruning by `year`/`month`.
8. Return an empty table with the expected schema when no objects exist under the group's prefix.
9. Keep SDK-visible behavior — shape checks, validation, join semantics, output column order, prefixed joined columns — identical to the local provider.
10. Do not import `boto3` or `botocore` outside `src/kitefs/providers/aws/`.

## Error Handling

| Error                    | When                                                          | Behavior                                                             |
| ------------------------ | ------------------------------------------------------------- | -------------------------------------------------------------------- |
| `ConfigurationError`     | `remote.offline_store` missing for an operation that needs it | Raise before any S3 call                                             |
| `OfflineStoreWriteError` | S3 `PutObject` fails                                          | Raise; per-object atomicity prevents partial final object            |
| `OfflineStoreReadError`  | S3 list/get fails or Parquet payload cannot be parsed         | Raise with actionable message                                        |
| `ProviderError`          | AWS credentials missing or invalid                            | Raise without leaking secrets                                        |
| Oversized payload        | Single-PUT payload too large for the MVP assumption           | `[DECISION NEEDED]: reject before write, or rely on provider error?` |

## Example

Input: remote `store.ingest("town_market_features", df)` with 6 valid rows for `event_timestamp=2024-02-01`, with `KITEFS_REMOTE_OFFLINE_S3_BUCKET=company-ml`.
Output: one Parquet object at `s3://company-ml/kitefs/data/offline_store/town_market_features/year=2024/month=02/ing_<...>.parquet`; `IngestResult.written_files` is a 1-element list of that `s3://` URI.

Input: remote `store.get_historical_features(from_="listing_features", join=["town_market_features"], select={...}, where={"sold_at": {"gte": ..., "lte": ...}})` against the same bucket holding both groups' data.
Output: a Pandas DataFrame structurally identical to the local-provider output for equivalent data.

## BDD Scenarios

```gherkin
Scenario: Remote ingest writes partitioned S3 Parquet
  Given runtime.target resolves to "remote"
  And the remote registry contains "town_market_features"
  And the remote offline store is configured at "s3://company-ml/kitefs"
  And the input DataFrame contains 6 valid rows with event_timestamp 2024-02-01T00:00:00Z
  When the user calls store.ingest("town_market_features", df)
  Then no exception is raised
  And result.accepted_rows is 6
  And result.written_files contains exactly 1 S3 URI
  And the S3 URI starts with "s3://company-ml/kitefs/data/offline_store/town_market_features/year=2024/month=02/"

Scenario: Remote historical retrieval returns the same columns as local retrieval
  Given equivalent local and remote offline data exists for "listing_features"
  When the user retrieves "net_area" and "sold_price" from "listing_features" using the remote runtime
  Then no exception is raised
  And the returned columns match the local result columns

Scenario: Remote joined historical retrieval preserves point-in-time behavior
  Given equivalent local and remote offline data exists for "listing_features" and "town_market_features"
  When the user retrieves "listing_features" joined to "town_market_features" using the remote runtime
  Then no exception is raised
  And listing_id 1002 has town_market_features_event_timestamp 2024-04-01T00:00:00Z
  And listing_id 1002 has town_market_features_avg_price_per_sqm 25400.0

Scenario: Remote retrieval returns an empty DataFrame when no S3 objects exist
  Given runtime.target resolves to "remote"
  And "listing_features" is registered
  And no S3 objects exist under the offline prefix for "listing_features"
  When the user retrieves "net_area" and "sold_price" from "listing_features"
  Then no exception is raised
  And the result has zero rows

Scenario: Missing remote offline configuration fails clearly
  Given runtime.target resolves to "remote"
  And remote.offline_store.bucket is empty
  When the user calls store.ingest("town_market_features", df)
  Then ConfigurationError is raised
  And the error message contains "remote offline"
  And the error message contains "bucket"
```
