"""Offline store manager — partition derivation, file naming, append-only writes, partition-pruned reads.

Orchestrates all offline store operations between the SDK (BB-02) and the provider (BB-09).
Does NOT validate data (BB-05's job), perform joins (BB-08's job), or interact with the
online store (BB-07's domain). Does NOT depend on the definition module — receives
column names as parameters from the caller.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

# All event timestamp values and filter values must be timezone-naive and interpreted
# as UTC. KiteFS does not perform timezone conversion — see API Contracts §6.2.
import pandas as pd
from pandas import DataFrame

from kitefs.exceptions import IngestionError, RetrievalError
from kitefs.providers.base import StorageProvider

_VALID_TIME_OPS = frozenset({"gt", "gte", "lt", "lte"})

_PARTITION_PATTERN = re.compile(r"^year=(\d{4})/month=(\d{2})$")


@dataclass(frozen=True)
class WriteResult:
    """Result of an offline store write operation."""

    rows_written: int
    partitions_affected: tuple[str, ...]


class OfflineStoreManager:
    """Orchestrates offline store reads and writes through the provider layer.

    Handles partition column derivation from event timestamps, unique Parquet file
    naming, write orchestration (grouping by partition), and read orchestration
    with partition pruning and row-level time filtering.
    """

    def __init__(self, provider: StorageProvider) -> None:
        """Initialise with a storage provider for all I/O delegation."""
        self._provider = provider

    def write(
        self,
        group_name: str,
        df: DataFrame,
        event_timestamp_col: str,
        source_prefix: str = "ing",
    ) -> WriteResult:
        """Write a DataFrame to the offline store, partitioned by event timestamp.

        Derives ``year=YYYY/month=MM`` partitions from *event_timestamp_col*,
        generates a unique file name per partition, and delegates per-partition
        Parquet writes to the provider. Append-only — never modifies existing files.

        Parameters
        ----------
        group_name:
            Name of the feature group (determines the directory).
        df:
            Data to write. Must contain *event_timestamp_col*.
        event_timestamp_col:
            Column name holding the event timestamp (passed by the caller,
            typically ``definition.event_timestamp.name``).
        source_prefix:
            Prefix for file naming (``ing`` for ingestion, ``mock`` for mock data).
        """
        if df.empty:
            return WriteResult(rows_written=0, partitions_affected=())

        ts_col = pd.to_datetime(df[event_timestamp_col])

        if ts_col.isna().any():
            null_count = int(ts_col.isna().sum())
            raise IngestionError(
                f"Cannot partition data: {null_count} record(s) have null "
                f"'{event_timestamp_col}' values. All records must have a valid "
                f"event timestamp for Hive-style partitioning."
            )

        # Build partition map from numpy arrays to avoid any DataFrame mutation.
        years = ts_col.dt.year.values
        months = ts_col.dt.month.values
        partition_groups: dict[str, list[int]] = {}
        for i in range(len(df)):
            key = _derive_partition_path(int(years[i]), int(months[i]))
            partition_groups.setdefault(key, []).append(i)

        file_name = _generate_file_name(source_prefix)
        affected: list[str] = []

        # Writes are not transactional across partitions. If this loop fails partway
        # through, earlier partitions are already on disk. Re-running the ingest will
        # write the missing partitions; the successfully written partitions will gain
        # an additional file (duplicate records — consistent with KTD-11 append-only
        # semantics). Batch-level rollback is not supported; see docs-03-02 §4.
        for partition_path in sorted(partition_groups):
            row_indices = partition_groups[partition_path]
            sub_df = df.iloc[row_indices].reset_index(drop=True)
            self._provider.write_offline(
                group_name=group_name,
                partition_path=partition_path,
                file_name=file_name,
                df=sub_df,
            )
            affected.append(partition_path)

        return WriteResult(
            rows_written=len(df),
            partitions_affected=tuple(affected),
        )

    def read(
        self,
        group_name: str,
        event_timestamp_col: str,
        time_filter: dict[str, Any] | None = None,
        upper_bound: datetime | None = None,
    ) -> DataFrame:
        """Read data from the offline store with optional partition pruning and row filtering.

        Lists all partitions, prunes based on *time_filter* and/or *upper_bound*,
        reads the surviving partitions via the provider, then applies precise row-level
        time filtering on *event_timestamp_col*.

        Parameters
        ----------
        group_name:
            Name of the feature group to read.
        event_timestamp_col:
            Column name holding the event timestamp (passed by the caller).
        time_filter:
            Flat operator→value dict (e.g., ``{"gte": datetime(...), "lte": datetime(...)}``).
            Supports ``gt``, ``gte``, ``lt``, ``lte``.
        upper_bound:
            Upper time bound for partition pruning (used for joined group reads).
        """
        all_partitions = self._provider.list_partitions(group_name)
        if not all_partitions:
            return DataFrame()

        pruned = _prune_partitions(all_partitions, time_filter, upper_bound)
        if not pruned:
            return DataFrame()

        df = self._provider.read_offline(group_name, pruned)
        if df.empty:
            return df

        df[event_timestamp_col] = pd.to_datetime(df[event_timestamp_col])

        if time_filter:
            df = _apply_row_filter(df, event_timestamp_col, time_filter)

        return df


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _generate_file_name(source_prefix: str) -> str:
    """Generate a unique Parquet file name: ``{source}_{YYYYMMDDTHHMMSS}_{short_id}.parquet``."""
    now = datetime.now(UTC)
    timestamp = now.strftime("%Y%m%dT%H%M%S")
    short_id = secrets.token_hex(4)
    return f"{source_prefix}_{timestamp}_{short_id}.parquet"


def _derive_partition_path(year: int, month: int) -> str:
    """Return the Hive-style partition path for a given year and month."""
    return f"year={year}/month={month:02d}"


def _parse_partition(partition_path: str) -> tuple[int, int]:
    """Extract ``(year, month)`` from a ``year=YYYY/month=MM`` string."""
    match = _PARTITION_PATTERN.match(partition_path)
    if not match:
        return (0, 0)
    return int(match.group(1)), int(match.group(2))


def _partition_month_start(year: int, month: int) -> datetime:
    """Return the first instant of a month as a timezone-naive datetime."""
    return datetime(year, month, 1)


def _partition_month_end(year: int, month: int) -> datetime:
    """Return the first instant of the next month (exclusive upper bound), timezone-naive."""
    if month == 12:
        return datetime(year + 1, 1, 1)
    return datetime(year, month + 1, 1)


def _prune_partitions(
    partitions: list[str],
    time_filter: dict[str, Any] | None,
    upper_bound: datetime | None,
) -> list[str]:
    """Return only partitions that could contain matching records.

    A partition ``year=Y/month=M`` represents the half-open interval
    ``[Y-M-01, Y-(M+1)-01)``. Pruning includes a partition if its interval
    overlaps with the constraints from *time_filter* and/or *upper_bound*.
    """
    if time_filter is None and upper_bound is None:
        return partitions

    result: list[str] = []
    for partition in partitions:
        year, month = _parse_partition(partition)
        if year == 0:
            # Unrecognised partition format — include it to be safe.
            result.append(partition)
            continue

        p_start = _partition_month_start(year, month)
        p_end = _partition_month_end(year, month)

        if not _partition_matches_filter(p_start, p_end, time_filter):
            continue
        if not _partition_matches_upper_bound(p_start, upper_bound):
            continue

        result.append(partition)

    return result


def _partition_matches_filter(
    p_start: datetime,
    p_end: datetime,
    time_filter: dict[str, Any] | None,
) -> bool:
    """Check if a partition interval overlaps the time_filter constraints."""
    if time_filter is None:
        return True

    for op, value in time_filter.items():
        if op not in _VALID_TIME_OPS:
            raise RetrievalError(
                f"Unsupported time filter operator '{op}'. Supported operators: {', '.join(sorted(_VALID_TIME_OPS))}."
            )
        ts = _to_naive_datetime(value)
        if op == "gt":
            # Records must be > ts. Partition has records in [p_start, p_end).
            # Partition is useful if p_end > ts (some records could be > ts).
            if p_end <= ts:
                return False
        elif op == "gte":
            # Records must be >= ts. Partition useful if p_end > ts.
            if p_end <= ts:
                return False
        elif op == "lt":
            # Records must be < ts. Partition useful if p_start < ts.
            if p_start >= ts:
                return False
        elif op == "lte" and p_start > ts:
            # Records must be <= ts. Partition useful if p_start <= ts.
            return False

    return True


def _partition_matches_upper_bound(p_start: datetime, upper_bound: datetime | None) -> bool:
    """Check if a partition starts at or before the upper bound's month."""
    if upper_bound is None:
        return True
    ub = _to_naive_datetime(upper_bound)
    # Include partitions whose start is <= upper_bound.
    return p_start <= ub


def _to_naive_datetime(dt: Any) -> datetime:
    """Return *dt* as a timezone-naive datetime, or raise RetrievalError.

    KiteFS requires all timestamps to be timezone-naive (interpreted as UTC).
    Passing a timezone-aware value is an error — KiteFS does not do conversion.
    """
    if dt is pd.NaT:
        raise RetrievalError("Time filter value is NaT. Provide a valid timezone-naive datetime.")
    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            raise RetrievalError(
                f"KiteFS only accepts timezone-naive datetimes (interpreted as UTC). "
                f"Received a timezone-aware value: {dt!r}. "
                f"Strip the timezone info before passing filter values "
                f"(e.g. dt.replace(tzinfo=None))."
            )
        return dt
    # Pandas Timestamp or similar.
    ts = pd.Timestamp(dt)
    if ts is pd.NaT:
        raise RetrievalError("Time filter value is NaT. Provide a valid timezone-naive datetime.")
    if ts.tzinfo is not None:
        raise RetrievalError(
            f"KiteFS only accepts timezone-naive datetimes (interpreted as UTC). "
            f"Received a timezone-aware value: {dt!r}. "
            f"Strip the timezone info before passing filter values "
            f"(e.g. dt.replace(tzinfo=None))."
        )
    return cast(datetime, ts.to_pydatetime())


def _apply_row_filter(
    df: DataFrame,
    event_timestamp_col: str,
    time_filter: dict[str, Any],
) -> DataFrame:
    """Apply precise row-level time filtering on event_timestamp_col.

    All values in *time_filter* must be timezone-naive; _to_naive_datetime
    is called on each one to enforce this and raise RetrievalError otherwise.
    """
    mask = pd.Series(True, index=df.index)
    col = df[event_timestamp_col]

    for op, value in time_filter.items():
        if op not in _VALID_TIME_OPS:
            raise RetrievalError(
                f"Unsupported time filter operator '{op}'. Supported operators: {', '.join(sorted(_VALID_TIME_OPS))}."
            )
        ts = pd.Timestamp(_to_naive_datetime(value))

        if op == "gt":
            mask = mask & (col > ts)
        elif op == "gte":
            mask = mask & (col >= ts)
        elif op == "lt":
            mask = mask & (col < ts)
        elif op == "lte":
            mask = mask & (col <= ts)

    return df.loc[mask].reset_index(drop=True)
