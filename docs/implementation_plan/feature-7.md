# Feature 7: Local offline store ingestion

## Goal

Let users append prepared feature rows from a Pandas DataFrame, CSV, or Parquet file into the local offline store, so later operations have historical data to read, join, and materialize.

## Description

`FeatureStore.ingest()` accepts a registered group name plus a DataFrame or a `.csv`/`.parquet` file path. It runs the shape check and validation engine using the group's `ingestion_validation` mode, then writes the accepted rows to Hive-partitioned Parquet files under `./feature_store/data/offline_store/{group}/year=YYYY/month=MM/`.

## Scope

- IN: SDK `FeatureStore.ingest`, DataFrame/file normalization, shape check, ingestion-time validation, offline store manager, local `OfflineStore.write` (PyArrow, partitioned, atomic per file).
- NOT IN: Historical retrieval, joins, materialization, AWS S3, CLI command (that wraps this in Feature 12).

## Expected output

A user can call `store.ingest("town_market_features", df)` with valid rows from the Turkish real estate use case and find new Parquet files under `feature_store/data/offline_store/town_market_features/year=YYYY/month=MM/`. The returned `IngestResult` reports accepted/rejected row counts and the list of written file paths.

## Implements

`FeatureStore.ingest`, `IngestResult`, `OfflineStore.write` (local), Offline Store Manager — as declared in `contracts.py`. Uses `IngestionShapeError`, `ValidationError`, `OfflineStoreWriteError`, `FeatureGroupNotFoundError`.

## Dependencies

Feature 4, Feature 6.

## Behavior

1. Resolve the target group from the registry; raise `FeatureGroupNotFoundError` if missing.
2. Normalize `data`: accept a Pandas DataFrame directly; accept a `.csv` path (load via Pandas) or `.parquet` path (load via PyArrow). Reject other extensions with `IngestionShapeError`.
3. Run the validation engine using the group's `ingestion_validation` mode (Feature 6 covers structural always-on plus mode-driven feature checks).
4. If validation accepts zero rows, return an `IngestResult` with `accepted_rows=0`, `rejected_rows=<n>`, `written_files=[]`, and the validation report; do not write any files.
5. Drop any input columns that are not declared structural or feature fields.
6. Convert datetime columns to UTC microsecond Parquet per `specs/05-data-and-storage-contracts.md`.
7. Derive partition columns `year` and `month` from each row's event timestamp.
8. Group rows by `(year, month)` and write one Parquet file per partition.
9. Each Parquet file is written to a temp path in the same directory and then `os.replace()`-d to its final name `ing_{YYYYMMDDTHHMMSS}_{short_id}.parquet` under `year=YYYY/month=MM/`.
10. Existing offline files are never modified or deleted (append-only).
11. Return `IngestResult(feature_group, accepted_rows, rejected_rows, written_files=[absolute paths], validation_report)`. `validation_report` is `None` when `ingestion_validation` is `NONE`.

## Error Handling

| Error                       | When                                                  | Behavior                                                     |
| --------------------------- | ----------------------------------------------------- | ------------------------------------------------------------ |
| `FeatureGroupNotFoundError` | Target group not in registry                          | Raise; write nothing                                         |
| `IngestionShapeError`       | Required column missing or unsupported file extension | Raise; write nothing                                         |
| `ValidationError`           | Structural failure or feature failure in `ERROR`      | Raise; write nothing                                         |
| `OfflineStoreWriteError`    | Provider cannot write the final Parquet file          | Raise; per-file atomicity ensures no partial file is visible |

## Example

Input: a DataFrame for the Turkish real estate use case with 6 rows for January 2024 market values (`town_id` ∈ {1..6}, `avg_price_per_sqm`, `event_timestamp=2024-02-01T00:00:00Z`), `town_market_features` already registered.
Output: `IngestResult(feature_group="town_market_features", accepted_rows=6, rejected_rows=0, written_files=["/.../feature_store/data/offline_store/town_market_features/year=2024/month=02/ing_<...>.parquet"], validation_report=ValidationReport(pass_count=6, fail_count=0, failures=[]))`.

## BDD Scenarios

```gherkin
Scenario: Ingest a month of town market rows
  Given "town_market_features" is registered
  And the input DataFrame contains 6 valid rows with event_timestamp 2024-02-01T00:00:00Z
  When the user calls store.ingest("town_market_features", df)
  Then no exception is raised
  And result.feature_group is "town_market_features"
  And result.accepted_rows is 6
  And result.rejected_rows is 0
  And result.written_files contains exactly 1 path
  And the written file is under "feature_store/data/offline_store/town_market_features/year=2024/month=02/"

Scenario: Ingest accepts a CSV file path
  Given "town_market_features" is registered
  And "data/town_market_2024_02.csv" contains 6 valid town market rows
  When the user calls store.ingest("town_market_features", "data/town_market_2024_02.csv")
  Then no exception is raised
  And result.accepted_rows is 6
  And result.written_files contains exactly 1 path

Scenario: Ingest rejects an unknown feature group
  Given the registry contains only "town_market_features"
  And the input DataFrame contains valid town market rows
  When the user calls store.ingest("neighborhood_features", df)
  Then FeatureGroupNotFoundError is raised
  And the error message contains "neighborhood_features"
  And no offline file is written

Scenario: Ingest rejects an unsupported file extension
  Given "town_market_features" is registered
  When the user calls store.ingest("town_market_features", "data/town_market.xlsx")
  Then IngestionShapeError is raised
  And the error message contains ".csv"
  And the error message contains ".parquet"
  And no offline file is written

Scenario: Missing required column raises a shape error
  Given "town_market_features" is registered
  And the input DataFrame contains "town_id" and "event_timestamp" but not "avg_price_per_sqm"
  When the user calls store.ingest("town_market_features", df)
  Then IngestionShapeError is raised
  And the error message contains "avg_price_per_sqm"
  And no offline file is written

Scenario: FILTER mode with no accepted rows writes nothing
  Given "town_market_features" is registered with ingestion_validation FILTER
  And the input DataFrame contains 2 rows whose avg_price_per_sqm values are -10.0 and -20.0
  When the user calls store.ingest("town_market_features", df)
  Then no exception is raised
  And result.accepted_rows is 0
  And result.rejected_rows is 2
  And result.written_files is empty
```
