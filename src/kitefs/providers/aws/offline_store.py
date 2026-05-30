"""AWS S3-backed offline store implementation.

Writes Hive-partitioned Parquet objects to:
    s3://{bucket}/{s3_prefix}/data/offline_store/{group}/year=YYYY/month=MM/

Each write is atomic at the object level: the Parquet payload is serialized
in memory and uploaded with a single PutObject call.  Partial objects are
never visible (S3 PUT is atomic at the object level).

File naming:
    {source_prefix}_{YYYYMMDDTHHMMSS}_{short_id}.parquet

where YYYYMMDDTHHMMSS is the UTC wall-clock time of the write (second
precision) and short_id is uuid4().hex[:6] for collision resistance.

Reads list objects with boto3, prune partitions via key-path analysis,
download Parquet bytes with get_object, and apply row-level timestamp
filtering after concatenation.  This approach is compatible with the
moto in-process mock used in the test suite and requires no additional
AWS SDK beyond boto3.
"""

from __future__ import annotations

import io
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, PartialCredentialsError

from kitefs.errors import OfflineStoreReadError, OfflineStoreWriteError, ProviderError, format_actionable
from kitefs.providers.base import OfflineStore, TimestampFilter

# Matches year=YYYY/month=MM in an S3 object key.
_PARTITION_RE = re.compile(r"year=(\d+)/month=(\d+)/")

# ClientError codes that indicate missing or invalid AWS credentials.
_CREDENTIAL_CLIENT_ERROR_CODES = frozenset(
    {
        "403",
        "AccessDenied",
        "InvalidAccessKeyId",
        "SignatureDoesNotMatch",
        "ExpiredTokenException",
    }
)


def _is_credential_error(exc: Exception) -> bool:
    """Return True when *exc* indicates missing or invalid AWS credentials.

    Covers both botocore credential exceptions (NoCredentialsError,
    PartialCredentialsError) and ClientError codes associated with auth
    failure.  Used to decide whether to raise ProviderError instead of a
    store-level error.
    """
    if isinstance(exc, (NoCredentialsError, PartialCredentialsError)):
        return True
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code", "") in _CREDENTIAL_CLIENT_ERROR_CODES
    return False


def _naive(dt: datetime) -> datetime:
    """Strip timezone; both naive (UTC) and UTC-aware are treated as UTC."""
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def _key_matches_partition_bounds(key: str, ts_filter: TimestampFilter) -> bool:
    """Return False when the partition encoded in an S3 key is outside the filter bounds.

    Parses year/month from key path segments (e.g. ``year=2024/month=02/``) and
    checks whether the partition could contain rows that satisfy all supplied
    bounds.  Applies each bound independently so that combined bounds (both gte
    and gt, or both lte and lt) are ANDed correctly, matching the local
    provider's partition-pruning semantics.

    Returns True conservatively when the partition cannot be parsed.
    """
    m = _PARTITION_RE.search(key)
    if not m:
        return True
    year, month = int(m.group(1)), int(m.group(2))

    if ts_filter.gte is not None:
        y, mo = _naive(ts_filter.gte).year, _naive(ts_filter.gte).month
        if not ((year > y) or (year == y and month >= mo)):
            return False

    if ts_filter.gt is not None:
        y, mo = _naive(ts_filter.gt).year, _naive(ts_filter.gt).month
        if not ((year > y) or (year == y and month >= mo)):
            return False

    if ts_filter.lte is not None:
        y, mo = _naive(ts_filter.lte).year, _naive(ts_filter.lte).month
        if not ((year < y) or (year == y and month <= mo)):
            return False

    if ts_filter.lt is not None:
        y, mo = _naive(ts_filter.lt).year, _naive(ts_filter.lt).month
        if not ((year < y) or (year == y and month <= mo)):
            return False

    return True


def _apply_row_filter(
    table: pa.Table,
    event_timestamp_column: str,
    ts_filter: TimestampFilter,
) -> pa.Table:
    """Apply row-level timestamp predicates to a PyArrow Table.

    Uses the same bound semantics as the local provider's _build_filter_expr
    but operates purely on the row-level timestamp column (S3 reads use
    key-path pruning for partition-level filtering instead of pyarrow.dataset
    Hive partition predicates).
    """
    ts_col = pc.field(event_timestamp_column)
    parts: list[Any] = []

    if ts_filter.gte is not None:
        parts.append(ts_col >= pa.scalar(_naive(ts_filter.gte), pa.timestamp("us")))
    if ts_filter.gt is not None:
        parts.append(ts_col > pa.scalar(_naive(ts_filter.gt), pa.timestamp("us")))
    if ts_filter.lte is not None:
        parts.append(ts_col <= pa.scalar(_naive(ts_filter.lte), pa.timestamp("us")))
    if ts_filter.lt is not None:
        parts.append(ts_col < pa.scalar(_naive(ts_filter.lt), pa.timestamp("us")))

    if not parts:
        return table

    expr = parts[0]
    for part in parts[1:]:
        expr = expr & part  # type: ignore[operator]
    return table.filter(expr)


class AWSOfflineStore(OfflineStore):
    """S3-backed offline store.

    Writes Hive-partitioned Parquet objects to S3 (one PutObject per partition,
    atomic at the object level).  Reads list objects with boto3, prune
    partitions via key-path analysis, download each object, and apply row-level
    timestamp filtering after concatenation.

    All AWS I/O uses the supplied boto3 S3 client; boto3 and botocore are never
    imported in packages outside providers/aws/.
    """

    def __init__(self, client: Any, *, bucket: str, s3_prefix: str) -> None:
        self._client = client
        self._bucket = bucket
        self._s3_prefix = s3_prefix

    def write(
        self,
        feature_group: str,
        data: pa.Table,
        *,
        event_timestamp_column: str,
        source_prefix: str,
    ) -> list[str]:
        """Partition data by event timestamp (year, month) and upload as Parquet objects.

        Each partition is serialized in memory and uploaded in one PutObject call,
        which is atomic at the S3 object level.  Existing objects are never
        modified or deleted (append-only).

        Args:
            feature_group: Registry name of the target group.
            data: PyArrow Table; must contain the event timestamp column as
                ``pa.timestamp('us')``.
            event_timestamp_column: Column name of the event timestamp field.
            source_prefix: File name prefix (e.g. ``'ing'``).

        Returns:
            List of ``s3://`` URIs written (one per partition), sorted by
            (year, month).

        Raises:
            OfflineStoreWriteError: Parquet serialization failed, or PutObject
                failed for a reason other than missing credentials.
            ProviderError: PutObject returned HTTP 403 / AccessDenied —
                credentials are missing or lack S3 write permission.
        """
        ts_col = data.column(event_timestamp_column)
        ts_array = ts_col.combine_chunks() if isinstance(ts_col, pa.ChunkedArray) else ts_col

        timestamps = ts_array.to_pylist()
        partition_indices: dict[tuple[int, int], list[int]] = {}
        for i, val in enumerate(timestamps):
            if val is None:
                continue
            if isinstance(val, datetime):
                y, m = int(val.year), int(val.month)
            else:
                import pandas as pd

                dt = pd.Timestamp(val).to_pydatetime()
                y, m = int(dt.year), int(dt.month)
            partition_indices.setdefault((y, m), []).append(i)

        write_ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        written: list[str] = []
        for (year, month), row_indices in sorted(partition_indices.items()):
            partition_table = data.take(row_indices)
            short_id = uuid4().hex[:6]
            file_name = f"{source_prefix}_{write_ts}_{short_id}.parquet"
            key = f"{self._s3_prefix}/data/offline_store/{feature_group}/year={year}/month={month:02d}/{file_name}"

            buf = io.BytesIO()
            try:
                pq.write_table(partition_table, buf)
            except Exception as exc:
                raise OfflineStoreWriteError(
                    format_actionable(
                        group=feature_group,
                        problem=f"failed to serialize Parquet payload for s3://{self._bucket}/{key}: {exc}",
                        next_step="check that the data types match the feature group schema",
                    )
                ) from exc

            try:
                self._client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=buf.getvalue(),
                )
            except (NoCredentialsError, PartialCredentialsError) as exc:
                raise ProviderError(
                    format_actionable(
                        problem="AWS credentials are missing or invalid for S3 write",
                        next_step="check your AWS credentials and S3 write permissions",
                    )
                ) from exc
            except ClientError as exc:
                if _is_credential_error(exc):
                    raise ProviderError(
                        format_actionable(
                            problem="AWS credentials are missing or invalid for S3 write",
                            next_step="check your AWS credentials and S3 write permissions",
                        )
                    ) from exc
                raise OfflineStoreWriteError(
                    format_actionable(
                        group=feature_group,
                        problem=f"failed to write s3://{self._bucket}/{key}: {exc}",
                        next_step="check bucket name, region, credentials, and S3 write permissions",
                    )
                ) from exc
            except BotoCoreError as exc:
                raise OfflineStoreWriteError(
                    format_actionable(
                        group=feature_group,
                        problem=f"failed to write s3://{self._bucket}/{key}: {exc}",
                        next_step="check region, credentials, and S3 connectivity",
                    )
                ) from exc

            written.append(f"s3://{self._bucket}/{key}")

        return written

    def read(
        self,
        feature_group: str,
        *,
        event_timestamp_column: str,
        schema: pa.Schema,
        timestamp_filter: TimestampFilter | None = None,
    ) -> pa.Table:
        """Read historical feature rows from the S3 offline store.

        Lists all Parquet objects under the group's S3 prefix with boto3, prunes
        partitions using key-path analysis when a timestamp filter is provided,
        downloads each remaining object in deterministic (LastModified, Key)
        order, and applies row-level filtering after concatenation.

        WARNING: S3 LastModified has second precision and is only a best-effort
        ingest-order proxy for the MVP. Same-second correction ingests for the
        same entity and event timestamp can tie-break differently from local.

        Args:
            feature_group: Registry name of the feature group to read.
            event_timestamp_column: Column name of the event timestamp field.
            schema: Expected PyArrow schema; defines the output columns and
                constructs the empty return value when no data is found.
            timestamp_filter: Optional bounds for the event timestamp.

        Returns:
            A PyArrow Table with columns matching ``schema.names``.  Returns an
            empty table with the provided schema when no objects exist or no rows
            satisfy the filter.

        Raises:
            OfflineStoreReadError: S3 list, get_object, or Parquet parse failed.
            ProviderError: S3 list or get_object returned HTTP 403 / AccessDenied.
        """
        prefix = f"{self._s3_prefix}/data/offline_store/{feature_group}/"

        try:
            objects = self._list_parquet_objects(prefix)
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise ProviderError(
                format_actionable(
                    problem="AWS credentials are missing or invalid for S3 read",
                    next_step="check your AWS credentials and S3 read permissions",
                )
            ) from exc
        except ClientError as exc:
            if _is_credential_error(exc):
                raise ProviderError(
                    format_actionable(
                        problem="AWS credentials are missing or invalid for S3 read",
                        next_step="check your AWS credentials and S3 read permissions",
                    )
                ) from exc
            raise OfflineStoreReadError(
                format_actionable(
                    group=feature_group,
                    problem=f"failed to list offline store objects at s3://{self._bucket}/{prefix}: {exc}",
                    next_step="check bucket name, region, credentials, and S3 read permissions",
                )
            ) from exc
        except BotoCoreError as exc:
            raise OfflineStoreReadError(
                format_actionable(
                    group=feature_group,
                    problem=f"failed to list offline store objects at s3://{self._bucket}/{prefix}: {exc}",
                    next_step="check region, credentials, and S3 connectivity",
                )
            ) from exc

        if not objects:
            return schema.empty_table()

        # Partition-level pruning via key-path analysis — avoids downloading objects
        # outside the filter window entirely.
        if timestamp_filter is not None:
            objects = [o for o in objects if _key_matches_partition_bounds(o["Key"], timestamp_filter)]

        if not objects:
            return schema.empty_table()

        # WARNING: This is a deterministic MVP ordering, not a strict append log.
        # S3 LastModified is second-precision, so same-second equal-timestamp
        # corrections are documented as a post-MVP limitation.
        objects.sort(key=lambda o: (o["LastModified"], o["Key"]))

        tables: list[pa.Table] = []
        for obj in objects:
            key = obj["Key"]
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=key)
                body = response["Body"].read()
                table = pq.read_table(pa.BufferReader(body), columns=schema.names)
                tables.append(table)
            except (NoCredentialsError, PartialCredentialsError) as exc:
                raise ProviderError(
                    format_actionable(
                        problem="AWS credentials are missing or invalid for S3 read",
                        next_step="check your AWS credentials and S3 read permissions",
                    )
                ) from exc
            except ClientError as exc:
                if _is_credential_error(exc):
                    raise ProviderError(
                        format_actionable(
                            problem="AWS credentials are missing or invalid for S3 read",
                            next_step="check your AWS credentials and S3 read permissions",
                        )
                    ) from exc
                raise OfflineStoreReadError(
                    format_actionable(
                        group=feature_group,
                        problem=f"failed to download s3://{self._bucket}/{key}: {exc}",
                        next_step="check bucket name, region, credentials, and S3 read permissions",
                    )
                ) from exc
            except BotoCoreError as exc:
                raise OfflineStoreReadError(
                    format_actionable(
                        group=feature_group,
                        problem=f"failed to download s3://{self._bucket}/{key}: {exc}",
                        next_step="check region, credentials, and S3 connectivity",
                    )
                ) from exc
            except Exception as exc:
                raise OfflineStoreReadError(
                    format_actionable(
                        group=feature_group,
                        problem=f"failed to parse Parquet from s3://{self._bucket}/{key}: {exc}",
                        next_step="check that Parquet files are not corrupted and have the expected columns",
                    )
                ) from exc

        if not tables:
            return schema.empty_table()

        result = pa.concat_tables(tables)
        if timestamp_filter is not None:
            result = _apply_row_filter(result, event_timestamp_column, timestamp_filter)

        return result

    def _list_parquet_objects(self, prefix: str) -> list[dict[str, Any]]:
        """List all Parquet objects under *prefix* using paginated list_objects_v2.

        Returns a list of dicts with ``'Key'`` (str) and ``'LastModified'``
        (datetime) for every object whose key ends with ``.parquet``.

        Raises ``ClientError`` or ``BotoCoreError`` — callers wrap those into
        the appropriate domain errors.
        """
        objects: list[dict[str, Any]] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".parquet"):
                    objects.append({"Key": obj["Key"], "LastModified": obj["LastModified"]})
        return objects


__all__ = ["AWSOfflineStore"]
