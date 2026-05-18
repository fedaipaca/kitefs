# Data and Storage Contracts

## Purpose

This file defines what KiteFS data looks like at rest. It owns storage formats, schemas, layouts, type mapping, partition rules, and the storage-level write protocols that make atomicity, retry behavior, repair behavior, and idempotence explicit.

## Owns

- Registry JSON schema and serialization rules.
- Offline store Parquet directory layout, file naming, and partition strategy.
- SQLite online store schema and write protocol.
- DynamoDB online store table design and write protocol.
- Type mapping from `FeatureType` to storage types.
- Datetime serialization format for text-based stores.
- Null representation.
- Storage invariants.

## Does Not Own

- Operation step-by-step behavior. See [03-system-behavior.md](03-system-behavior.md).
- Validation rules for when null or out-of-range values are allowed. See [02-product-requirements.md](02-product-requirements.md) and [03-system-behavior.md](03-system-behavior.md).
- Internal class structure and provider interface signatures. See [04-architecture.md](04-architecture.md) and [06-api-and-cli-contracts.md](06-api-and-cli-contracts.md).
- Public SDK methods and CLI commands. See [06-api-and-cli-contracts.md](06-api-and-cli-contracts.md).

## Conventions

- Paths use `{placeholder}` for values resolved from configuration or the registry.
- `{storage_root}` is the configured local storage root. In the local project scaffold, this root is `./feature_store`.
- `{s3_prefix}` is the configured S3 object-key prefix. It comes from the remote S3 configuration and defaults to `kitefs_`.
- All datetime values stored as text use the [ISO 8601 datetime format](#datetime-serialization-format) defined in this document.
- All datetime values in storage are UTC, per [CON-006](02-product-requirements.md#con-006--utc-only-datetimes).

---

## Storage Contract Summary

| Artifact      | Local Provider                                                                            | AWS Provider                                                                                    | Stores                                                          |
| ------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Registry      | `./feature_store/registry.json`                                                           | `s3://{bucket}/{s3_prefix}/registry.json`                                                          | Registered feature group definitions and runtime metadata.      |
| Offline store | `{storage_root}/data/offline_store/{group_name}/year=YYYY/month=MM/{file_name}.parquet`   | `s3://{bucket}/{s3_prefix}/data/offline_store/{group_name}/year=YYYY/month=MM/{file_name}.parquet` | Historical feature records.                                     |
| Online store  | `{storage_root}/data/online_store/online.db` (SQLite, one table per online-capable group) | One DynamoDB table per online-capable group, named `{dynamodb_table_prefix}{group_name}`          | Active latest feature record per entity key for online-capable groups. |

Local and AWS providers store the same logical columns, types, and successful-state granularity. Differences are limited to the physical layer and provider-specific write failure behavior defined in this document.

---

## Datetime Serialization Format

The MVP normalizes datetime serialization to one format so that text-based stores (registry JSON, SQLite, DynamoDB, file names) sort and compare consistently.

| Context                   | Format                           | Example                       |
| ------------------------- | -------------------------------- | ----------------------------- |
| Registry JSON             | `YYYY-MM-DDTHH:MM:SS.ffffffZ`    | `2025-01-01T00:00:00.000000Z` |
| SQLite `TEXT` datetime    | `YYYY-MM-DDTHH:MM:SS.ffffffZ`    | `2025-01-01T00:00:00.000000Z` |
| DynamoDB `S` datetime     | `YYYY-MM-DDTHH:MM:SS.ffffffZ`    | `2025-01-01T00:00:00.000000Z` |
| Offline file-name segment | `YYYYMMDDTHHMMSS` (seconds, UTC) | `20250101T000000`             |
| Parquet column            | Native `timestamp('us')`         | n/a (binary)                  |

Rules:

- All text-format datetimes are UTC and include the trailing `Z`.
- Microsecond precision is always rendered with six digits, zero-padded, so that lexicographic comparison matches chronological order.
- The offline file-name segment uses second precision and no separators. Collisions are resolved by `short_id`, not by sub-second timestamp precision.
- Parquet stores datetimes natively at microsecond precision and does not use the text format.

---

## Registry JSON

The registry is a single JSON document. It is the derived artifact described in [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact). Its on-disk form is deterministic so it can be inspected, diffed, and reviewed.

### Locations

| Provider | Location                               |
| -------- | -------------------------------------- |
| Local    | `./feature_store/registry.json`        |
| AWS      | `s3://{bucket}/{s3_prefix}/registry.json` |

### Serialization Rules

The registry is serialized with `json.dumps(..., sort_keys=True, indent=2, ensure_ascii=False)` and written with a trailing newline. Concretely:

- Object keys are sorted lexicographically at every level.
- Indentation is two spaces (not tabs).
- Non-ASCII characters in field descriptions, owner names, and tag values are preserved literally rather than escaped.
- The writer sorts the `features` list and `join_keys` list alphabetically by `name` before serialization. `sort_keys=True` only affects object keys, not list order.
- The file ends with a single `\n`.

These rules together guarantee that the same logical registry content produces byte-for-byte identical output across runs and platforms.

### Top-Level Schema

```json
{
  "feature_groups": {
    "<group_name>": {}
  },
  "version": "1.0"
}
```

| Field            | Type   | Description                                                                         |
| ---------------- | ------ | ----------------------------------------------------------------------------------- |
| `version`        | string | Registry schema version. The MVP emits `"1.0"`.                                     |
| `feature_groups` | object | Map from feature group name to its entry. Empty `{}` when no groups are registered. |

### Feature Group Entry Schema

```json
{
  "applied_at": "2025-01-01T00:00:00.000000Z",
  "entity_key": {
    "description": "<string | null>",
    "dtype": "STRING | INTEGER",
    "name": "<string>"
  },
  "event_timestamp": {
    "description": "<string | null>",
    "dtype": "DATETIME",
    "name": "<string>"
  },
  "features": [
    {
      "description": "<string | null>",
      "dtype": "STRING | INTEGER | FLOAT | DATETIME",
      "expect": [{ "type": "not_null" }, { "type": "gt", "value": 0 }],
      "name": "<string>"
    }
  ],
  "ingestion_validation": "ERROR | FILTER | NONE",
  "join_keys": [
    {
      "dtype": "STRING | INTEGER",
      "name": "<string>",
      "referenced_group": "<string>"
    }
  ],
  "last_materialized_at": "<ISO 8601 timestamp | null>",
  "metadata": {
    "description": "<string | null>",
    "owner": "<string | null>",
    "tags": {
      "<key>": "<value>"
    }
  },
  "name": "<string>",
  "offline_retrieval_validation": "ERROR | FILTER | NONE",
  "storage_target": "OFFLINE | OFFLINE_AND_ONLINE"
}
```

Field order in serialized output is lexicographic per `sort_keys=True`; the example above is reformatted for readability.

### Field Notes

| Field                           | Notes                                                                                                                                                                                                                                                                                                                                               |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `applied_at`                    | Set by the registry generation step. Updated on every successful `apply` for this group.                                                                                                                                                                                                                                                            |
| `last_materialized_at`          | Runtime-managed. Updated on successful materialization per [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups). `null` until the group's first successful materialization. Preserved across `apply` runs for groups that still exist.                                                                           |
| `entity_key`, `event_timestamp` | Required structural objects. `event_timestamp.dtype` is always `DATETIME` in the registry, even when the Python definition omits the `dtype` argument.                                                                                                                                                                                               |
| `features`                      | Non-empty list of feature objects, sorted alphabetically by `name`.                                                                                                                                                                                                                                                                                 |
| `features[].expect`             | List of constraint objects, or `null` if the feature has no expectations. Each constraint has a `type` field; operators that carry an argument also have a `value` field. Supported `type` values mirror the operators in [FR-DEF-004](02-product-requirements.md#fr-def-004--feature-expectations). The `is_in` constraint carries a list `value`. |
| `join_keys`                     | List of zero or one join key objects in the MVP, per [FR-DEF-001](02-product-requirements.md#fr-def-001--feature-group-definition-as-code). Empty list when no join key is declared.                                                                                                                                                                |
| `metadata.tags`                 | Map of string-to-string. Empty object `{}` when no tags are declared.                                                                                                                                                                                                                                                                               |
| `storage_target`                | `OFFLINE` for offline-only groups; `OFFLINE_AND_ONLINE` for online-eligible groups.                                                                                                                                                                                                                                                                 |

### Write Protocol

The registry is rewritten as a whole document, never patched in place:

- **Local:** Write to a sibling temp file in the same directory, then call `os.replace()` to atomically rename onto `registry.json`. A crash leaves either the prior file or the new file, never a partial document.
- **AWS:** issue a single `PutObject` call with the full serialized document. S3 PUT is atomic at the object level: readers see either the prior version or the new version.

Manual edits to the registry file are not part of any supported workflow.

---

## Offline Store Parquet Layout

The offline store keeps historical feature records as Apache Parquet files. Local and AWS providers share the same directory layout and file-naming convention so reader logic is provider-agnostic.

### Directory Layout

```text
data/offline_store/
└── {group_name}/
    └── year=YYYY/
        └── month=MM/
            └── {source}_{YYYYMMDDTHHMMSS}_{short_id}.parquet
```

### Full Paths

| Provider | Path                                                                                            |
| -------- | ----------------------------------------------------------------------------------------------- |
| Local    | `{storage_root}/data/offline_store/{group_name}/year=YYYY/month=MM/{file_name}.parquet`         |
| AWS      | `s3://{bucket}/{s3_prefix}/data/offline_store/{group_name}/year=YYYY/month=MM/{file_name}.parquet` |

Per-group offline directories (`{storage_root}/data/offline_store/{group_name}/`) are created lazily on first successful ingestion. Reading a group with no offline files produces an empty result with the expected schema.

### Partition Strategy

Partitions are derived from each record's event timestamp value, not from the write time. This is what makes historical retrieval able to prune partitions by event-timestamp filters without scanning every file.

| Partition Level | Format      | Source                                                                            |
| --------------- | ----------- | --------------------------------------------------------------------------------- |
| Year            | `year=YYYY` | Year component of the record's event timestamp (UTC).                             |
| Month           | `month=MM`  | Month component of the record's event timestamp (UTC), zero-padded to two digits. |

A single ingestion batch can produce multiple Parquet files when its rows span multiple partitions. Each output file contains rows from exactly one partition.

Readers SHOULD use `pyarrow.dataset.dataset(..., partitioning='hive')` and pass PyArrow filter expressions (e.g., `ds.field("col") == value)` to `to_table(filter=...)` or `scanner(filter=...)`; the dataset API evaluates these expressions against partition metadata before opening any files, handling partition pruning automatically.

### File Naming

```text
{source}_{YYYYMMDDTHHMMSS}_{short_id}.parquet
```

| Segment           | Meaning                                                                                                                                                                             |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `source`          | Write-origin prefix. MVP prefixes are `ing` for ingested data, `mock` for mock data, `sample` for sample data. |
| `YYYYMMDDTHHMMSS` | UTC wall-clock time of the write, with second precision and no separators.                                                                                                          |
| `short_id`        | 6-character lowercase alphanumeric string derived from `uuid.uuid4().hex[:6]`. Makes file names collision-resistant within the same second; collision probability is acceptable for MVP scale.                                                      |

The file name carries no semantic meaning beyond observability. Retrieval logic must not parse it; the partition path is the only authoritative time signal for filtering.

### Parquet Schema

Each Parquet file contains the structural columns and declared feature columns from the registry — and nothing else. Input columns not declared in the feature group are dropped during ingestion ([FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion)).

| Column Role     | Column Name                                    | Type Source                                                |
| --------------- | ---------------------------------------------- | ---------------------------------------------------------- |
| Entity key      | `entity_key.name` from registry                | `entity_key.dtype` via [Type Mapping](#type-mapping).      |
| Event timestamp | `event_timestamp.name` from registry           | `DATETIME` via [Type Mapping](#type-mapping).              |
| Join key        | `join_keys[].name` from registry (if declared) | `join_keys[].dtype` via [Type Mapping](#type-mapping).     |
| Feature fields  | Each `features[].name` from registry           | Each `features[].dtype` via [Type Mapping](#type-mapping). |

All Parquet files for one feature group must use the same column set and the same storage types. A registry change that alters a group's schema does not retroactively rewrite previously written files; reader and writer must agree on a consistent set of columns for any single file.

### Write Protocol

Each Parquet file is written using a temp-then-finalize pattern so partial files are never visible:

- **Local:** write to a temp file in the same partition directory, then atomically rename onto the final file name. A crash mid-write leaves the temp file (or nothing), never a half-written Parquet file at the final path. PyArrow's `write_table` writes directly to the target path; the local provider must wrap it by writing to a temp file, then calling `os.replace()` onto the final name.
- **AWS:** Upload the full Parquet payload using a single `PutObject` call. S3 PUT is atomic at the object level; readers see the new object only after the PUT returns. A failed upload leaves no object at the final key. MVP assumes individual offline files are ≤ 5 GB; multipart upload support is post-MVP.

A single ingestion batch may produce many files. Per [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes), per-file atomicity is guaranteed; batch-level rollback is not. Completed files from a partially failed batch may remain.

---

## Type Mapping

This table is the storage type contract for all supported `FeatureType` values. All other storage rules in this document defer to it.

| `FeatureType` | Parquet / PyArrow    | Pandas dtype     | Python Type | SQLite Type       | DynamoDB Type  |
| ------------- | -------------------- | ---------------- | ----------- | ----------------- | -------------- |
| `STRING`      | `pa.string()`        | `object` (str)   | `str`       | `TEXT`            | `S`            |
| `INTEGER`     | `pa.int64()`         | `int64`          | `int`       | `INTEGER`         | `N`            |
| `FLOAT`       | `pa.float64()`       | `float64`        | `float`     | `REAL`            | `N`            |
| `DATETIME`    | `pa.timestamp('us')` | `datetime64[us]` | `datetime`  | `TEXT` (ISO 8601) | `S` (ISO 8601) |

Notes:

- Parquet stores datetimes natively at microsecond precision. SQLite, DynamoDB, the registry, and file-name segments store datetimes as text using the format defined in [Datetime Serialization Format](#datetime-serialization-format).
- DynamoDB `N` is a decimal string with up to 38 digits of precision. `INTEGER` values map directly. `FLOAT` values are serialized through Python's default `Decimal` round-trip via `boto3`, which preserves `float64` precision for typical feature values; callers that need exact decimal semantics should pre-format their values.

---

## SQLite Online Store

The local online store is a single SQLite database file at `{storage_root}/data/online_store/online.db`. The containing directory is created on first write.

Each online-capable feature group (`storage_target = OFFLINE_AND_ONLINE`) gets one table.

| Table Part      | Contract                                                                                                       |
| --------------- | -------------------------------------------------------------------------------------------------------------- |
| Table name      | The feature group name, verbatim.                                                                              |
| Primary key     | The entity key column. Single-column key per [CON-004](02-product-requirements.md#con-004--single-entity-key). |
| Row granularity | Exactly one row per entity key value.                                                                          |
| Columns         | Entity key, event timestamp, join key (when declared), and all declared feature columns.                       |
| Column types    | SQLite types from [Type Mapping](#type-mapping).                                                               |

### Generic Table Shape

```sql
CREATE TABLE "<group_name>" (
    "<entity_key_name>"      <sqlite_type> PRIMARY KEY,
    "<event_timestamp_name>" TEXT NOT NULL,
    "<join_key_name>"        <sqlite_type>,           -- present only when the group declares a join key
    "<feature_name>"         <sqlite_type>
);
```

`DATETIME` columns are declared `TEXT` and store values using the [Datetime Serialization Format](#datetime-serialization-format). Because the format is fixed-width and UTC, lexicographic `TEXT` comparison matches chronological order.

Table and column names come from the registry. [CON-009](02-product-requirements.md#con-009--identifier-naming-rules) restricts all identifier names, ensuring they are safe as SQL identifiers without escaping.

### Write Protocol

Per-group materialization on SQLite is atomic, as required by [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling):

1. Receive the latest row per entity key as computed by the materialize operation.
2. Start a single SQLite transaction for the group.
3. Replace the group's table contents with the new rows inside that transaction.
4. Commit the transaction.

A crash or error before commit rolls back the transaction and leaves the prior committed table contents visible. Readers always observe a complete, consistent table — either the prior successful state or the new one. Partial states are never visible. A failure on a per-group write does not affect other groups in the same materialization run.

The exact replacement statement sequence is provider-internal. For example, an implementation may delete all rows and insert the new rows, or upsert the new rows and delete stale keys, as long as the full replacement occurs inside the single transaction.

MVP implementation: `BEGIN; DELETE FROM <table>; executemany INSERT ...; COMMIT`. This guarantees full replacement within one transaction and is the simplest approach. Alternative upsert strategies are post-MVP.

### Connection Settings

Every SQLite connection enables WAL mode (`PRAGMA journal_mode=WAL`) and sets `PRAGMA busy_timeout=5000`. WAL allows concurrent reads during a write transaction, which matches the materialization-while-serving workload.

---

## DynamoDB Online Store

The AWS online store uses one DynamoDB table per online-capable feature group. Each table stores one item per entity key value. Tables are created and managed by KiteFS; users do not provision them manually.

| Table Part    | Contract                                                                                                         |
| ------------- | ---------------------------------------------------------------------------------------------------------------- |
| Table name    | `{dynamodb_table_prefix}{group_name}`. The prefix comes from the remote online-store configuration; the default is `kitefs_`. |
| Partition key | The entity key column, using its DynamoDB type from [Type Mapping](#type-mapping): `N` for `INTEGER`, `S` for `STRING`. |
| Sort key      | None.                                                                                                            |
| Granularity   | At most one item per entity key value.                                                                           |
| Attributes    | Entity key, event timestamp, join key (when declared), and all declared feature attributes.                      |
| Billing mode  | On-demand (`PAY_PER_REQUEST`). MVP does not configure provisioned capacity.                                      |

### Item Shape

Each item contains only the logical columns. There are no provider-internal attributes.

```json
{
  "<entity_key_name>":      { "N|S": "<value>" },
  "<event_timestamp_name>": { "S": "2025-01-01T00:00:00.000000Z" },
  "<join_key_name>":        { "N|S": "<value>" },
  "<string_feature>":       { "S": "some_text" },
  "<integer_feature>":      { "N": "42" },
  "<float_feature>":        { "N": "27200.0" },
  "<datetime_feature>":     { "S": "2024-12-01T00:00:00.000000Z" }
}
```

`INTEGER` and `FLOAT` values use DynamoDB `N`. `STRING` and `DATETIME` values use DynamoDB `S`, with `DATETIME` values formatted per [Datetime Serialization Format](#datetime-serialization-format).

Entity keys are stored using their native DynamoDB type. Per [FR-DEF-002](02-product-requirements.md#fr-def-002--field-type-definitions), entity keys are restricted to `STRING` or `INTEGER` in the MVP, so the partition key is always `S` or `N` with no serialization ambiguity.

### Table Lifecycle

The AWS provider creates the group's table lazily on first materialization:

1. Before writing, the provider calls `DescribeTable`.
2. If the table does not exist, the provider calls `CreateTable` with the partition-key schema derived from the group's entity key type, billing mode `PAY_PER_REQUEST`, and no sort key. The provider then waits for the table to reach `ACTIVE` status before proceeding with writes.
3. If the table already exists, the provider validates that the partition key name and type match the group's entity key and that no sort key is present. A mismatch fails the operation with an actionable error.

Tables are never deleted by KiteFS. Removing a feature group from definitions and running `apply` does not drop its DynamoDB table; users clean up unused tables manually.

The AWS provider requires IAM permissions for `dynamodb:DescribeTable`, `dynamodb:CreateTable`, `dynamodb:BatchWriteItem`, `dynamodb:PutItem`, and `dynamodb:GetItem` on tables matching the configured prefix.

### Read Protocol

Online reads use a single `GetItem` call against the group's table, keyed by the entity key value:

1. Look up the item by entity key value.
2. If the item does not exist, return an empty result.
3. Return the logical entity key, event timestamp, join key (when declared), and requested feature attributes.

If the group's table does not exist (the group has never been materialized), the provider returns an empty result. Access errors or schema mismatches fail with an actionable error.

User-facing request validation still rejects unknown groups, offline-only groups, and unknown feature fields before the DynamoDB lookup. See [FR-ONL-002](02-product-requirements.md#fr-onl-002--single-entity-online--retrieval) and [get_online_features](03-system-behavior.md#get_online_features).

### Write Protocol

Materialization writes the latest rows in chunked batches, as required by [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling):

1. Compute the latest row per entity key from the group's offline data.
2. Ensure the group's table exists and is `ACTIVE` (see [Table Lifecycle](#table-lifecycle)).
3. Split the latest rows into chunks of at most 25 items (the `BatchWriteItem` API limit).
4. For each chunk, call `BatchWriteItem` with `PutRequest` entries.
5. If the response includes `UnprocessedItems`, retry those items once after a short delay.
6. On success across all chunks, the provider reports success so the caller can update `last_materialized_at`.
7. On any error (provider client error or persistent `UnprocessedItems` after the single retry), the provider fails the group with the underlying error message and recommends re-running materialization. `last_materialized_at` is not updated.

Each `PutRequest` overwrites the existing item for that entity key atomically. Partial state may be visible after a mid-run failure: chunks written before the error remain in the table. Re-running materialization overwrites them with the latest offline rows, which is the supported repair path.

### MVP Limitations

The DynamoDB online store in the MVP is designed for demo and alpha use, not production serving. Accepted limitations:

- Materialization is not group-atomic. A failure may leave a partially refreshed table visible.
- Retry behavior is minimal: one retry for `UnprocessedItems`, no exponential backoff or jitter.
- KiteFS does not delete or clean up DynamoDB tables. Unused tables from removed feature groups must be deleted manually.
- On-demand billing mode is always used. Provisioned capacity configuration is not supported.

---

## Null Representation

This table defines storage representations only. Validation rules for when nulls are allowed live in [02-product-requirements.md](02-product-requirements.md) and [03-system-behavior.md](03-system-behavior.md).

| Context                      | Null Representation                                                               |
| ---------------------------- | --------------------------------------------------------------------------------- |
| Registry JSON                | JSON `null`.                                                                      |
| Offline store Parquet        | Native Parquet null.                                                              |
| SQLite online store          | SQL `NULL`.                                                                       |
| DynamoDB online store        | The attribute is omitted from the item.                                           |
| Pandas DataFrame interchange | `NaN` for numeric columns, `None` for string columns, `NaT` for datetime columns. |

Structural fields (entity key, event timestamp, join key) are never null in any successful write. Storage representations for null apply only to feature columns and to optional metadata fields.

---

## Storage Invariants

These invariants hold at all times for any valid KiteFS storage state and are testable in isolation from operation behavior.

| Invariant                          | Contract                                                                                                                                       |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Registry determinism               | The same logical registry content produces byte-for-byte identical JSON output, including the trailing newline.                                |
| Registry validity                  | The registry is always a valid JSON document with `version` and `feature_groups` top-level fields.                                             |
| Registry atomicity                 | A registry write either fully replaces the prior document or leaves it untouched. Partial documents are never visible to readers.              |
| Offline partition determinism      | A record's event timestamp determines exactly one `year=YYYY/month=MM/` partition.                                                             |
| Offline file immutability          | Existing Parquet files are immutable. New data is always represented by additional files.                                                      |
| Offline file atomicity             | A Parquet file is exposed at its final path only after the full payload is durably written. Partial files are never visible to readers.        |
| Offline schema consistency         | All Parquet files for one feature group share the same columns and storage types.                                                              |
| Online logical granularity         | After a successful materialization, online reads expose at most one active record per entity key per online-capable group.                     |
| SQLite physical granularity        | SQLite holds exactly one row per entity key per online-capable group table.                                                                    |
| SQLite materialization atomicity   | A SQLite per-group materialization either fully replaces the prior committed table contents for that group or leaves them untouched.           |
| DynamoDB item granularity          | DynamoDB holds at most one item per entity key value per online-capable group table.                                                            |
| DynamoDB per-item atomicity        | Each `PutRequest` overwrite is atomic for that entity key. A failed materialization may leave a partially refreshed group table visible.        |
| DynamoDB repairability             | A successful DynamoDB rerun overwrites items with the latest rows from offline storage and repairs a failed partial attempt.                    |
| Datetime sort consistency          | Text-stored datetimes sort lexicographically in chronological order under the [Datetime Serialization Format](#datetime-serialization-format). |
| Cross-provider logical consistency | After successful writes, local and AWS providers store the same logical columns, types, and feature group granularity for the same logical data. |
