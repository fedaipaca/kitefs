"""Unit tests for AWSOfflineStore write and read operations."""

from __future__ import annotations

import datetime
from typing import Any

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from kitefs.errors import OfflineStoreReadError, OfflineStoreWriteError
from kitefs.providers.aws.offline_store import AWSOfflineStore
from kitefs.providers.base import TimestampFilter
from tests.helpers.aws import create_s3_bucket

_BUCKET = "test-bucket"
_REGION = "eu-central-1"
_PREFIX = "kitefs"
_GROUP = "town_market_features"
_UTC = datetime.UTC


@pytest.fixture(autouse=True)
def _use_mocked_aws(mocked_aws: None) -> None:
    """Use moto-backed AWS clients for all tests in this module."""


@pytest.fixture
def s3_client() -> Any:
    """Pre-built boto3 S3 client pointed at eu-central-1."""
    client = boto3.client("s3", region_name=_REGION)
    create_s3_bucket(client, bucket=_BUCKET, region=_REGION)
    return client


@pytest.fixture
def store(s3_client: Any) -> AWSOfflineStore:
    """AWSOfflineStore wired to the moto bucket."""
    return AWSOfflineStore(s3_client, bucket=_BUCKET, s3_prefix=_PREFIX)


def _ts(year: int, month: int, day: int) -> datetime.datetime:
    return datetime.datetime(year, month, day, tzinfo=_UTC)


def _table(rows: list[tuple[int, datetime.datetime, float]]) -> pa.Table:
    """Build a minimal table with town_id, event_timestamp, avg_price_per_sqm."""
    town_ids, timestamps, prices = zip(*rows, strict=False) if rows else ([], [], [])
    return pa.table(
        {
            "town_id": pa.array(list(town_ids), type=pa.int64()),
            "event_timestamp": pa.array(
                [t.replace(tzinfo=None) for t in timestamps],
                type=pa.timestamp("us"),
            ),
            "avg_price_per_sqm": pa.array(list(prices), type=pa.float64()),
        }
    )


def _schema() -> pa.Schema:
    return pa.schema(
        [
            ("town_id", pa.int64()),
            ("event_timestamp", pa.timestamp("us")),
            ("avg_price_per_sqm", pa.float64()),
        ]
    )


class TestWrite:
    """AWSOfflineStore.write uploads Hive-partitioned Parquet objects to S3."""

    def test_single_partition_writes_one_s3_object(self, store: AWSOfflineStore, s3_client: Any) -> None:
        """A single-month batch produces exactly one S3 object."""
        table = _table([(1, _ts(2024, 2, 1), 20000.0), (2, _ts(2024, 2, 15), 22000.0)])

        store.write(_GROUP, table, event_timestamp_column="event_timestamp", source_prefix="ing")

        response = s3_client.list_objects_v2(Bucket=_BUCKET)
        assert response["KeyCount"] == 1

    def test_returned_uris_start_with_s3_scheme(self, store: AWSOfflineStore) -> None:
        """Each returned URI starts with 's3://'."""
        table = _table([(1, _ts(2024, 2, 1), 20000.0)])

        uris = store.write(_GROUP, table, event_timestamp_column="event_timestamp", source_prefix="ing")

        assert len(uris) == 1
        assert uris[0].startswith("s3://")

    def test_object_key_contains_group_partition_and_file_prefix(self, store: AWSOfflineStore) -> None:
        """S3 URI embeds the group name, year/month Hive partition, and source prefix."""
        table = _table([(1, _ts(2024, 2, 1), 20000.0)])

        uris = store.write(_GROUP, table, event_timestamp_column="event_timestamp", source_prefix="ing")

        expected_fragment = f"data/offline_store/{_GROUP}/year=2024/month=02/ing_"
        assert expected_fragment in uris[0]

    def test_two_month_batch_writes_two_objects(self, store: AWSOfflineStore, s3_client: Any) -> None:
        """Rows spanning two calendar months produce two distinct S3 objects."""
        table = _table([(1, _ts(2024, 2, 1), 20000.0), (1, _ts(2024, 3, 1), 23000.0)])

        uris = store.write(_GROUP, table, event_timestamp_column="event_timestamp", source_prefix="ing")

        assert len(uris) == 2
        response = s3_client.list_objects_v2(Bucket=_BUCKET)
        assert response["KeyCount"] == 2

    def test_second_write_appends_without_deleting_first(self, store: AWSOfflineStore, s3_client: Any) -> None:
        """A second write adds a new object; the first S3 object is not deleted."""
        table1 = _table([(1, _ts(2024, 2, 1), 20000.0)])
        table2 = _table([(2, _ts(2024, 2, 5), 21000.0)])

        store.write(_GROUP, table1, event_timestamp_column="event_timestamp", source_prefix="ing")
        store.write(_GROUP, table2, event_timestamp_column="event_timestamp", source_prefix="ing")

        response = s3_client.list_objects_v2(Bucket=_BUCKET)
        assert response["KeyCount"] == 2

    def test_parquet_payload_is_readable(self, store: AWSOfflineStore, s3_client: Any) -> None:
        """The uploaded S3 object contains valid Parquet bytes with the expected row count."""
        table = _table([(1, _ts(2024, 2, 1), 20000.0)])

        uris = store.write(_GROUP, table, event_timestamp_column="event_timestamp", source_prefix="ing")

        key = uris[0][len(f"s3://{_BUCKET}/") :]
        body = s3_client.get_object(Bucket=_BUCKET, Key=key)["Body"].read()
        result = pq.read_table(pa.BufferReader(body))
        assert len(result) == 1

    def test_write_to_nonexistent_bucket_raises_write_error(self, s3_client: Any) -> None:
        """OfflineStoreWriteError is raised when the target bucket does not exist."""
        bad_store = AWSOfflineStore(s3_client, bucket="no-such-bucket", s3_prefix=_PREFIX)
        table = _table([(1, _ts(2024, 2, 1), 20000.0)])

        with pytest.raises(OfflineStoreWriteError):
            bad_store.write(_GROUP, table, event_timestamp_column="event_timestamp", source_prefix="ing")


class TestRead:
    """AWSOfflineStore.read retrieves and filters Parquet objects from S3."""

    def test_empty_prefix_returns_schema_conforming_empty_table(self, store: AWSOfflineStore) -> None:
        """Returns an empty table with expected column names when no objects exist."""
        result = store.read(_GROUP, event_timestamp_column="event_timestamp", schema=_schema())

        assert len(result) == 0
        assert result.schema.names == _schema().names

    def test_returns_rows_after_write(self, store: AWSOfflineStore) -> None:
        """All rows written via write() are returned by a subsequent read()."""
        table = _table([(1, _ts(2024, 2, 1), 20000.0), (2, _ts(2024, 2, 15), 22000.0)])
        store.write(_GROUP, table, event_timestamp_column="event_timestamp", source_prefix="ing")

        result = store.read(_GROUP, event_timestamp_column="event_timestamp", schema=_schema())

        assert len(result) == 2

    def test_timestamp_gte_lte_filter_applied(self, store: AWSOfflineStore) -> None:
        """Only rows within the gte/lte bounds are returned."""
        table = _table(
            [
                (1, _ts(2024, 2, 1), 20000.0),
                (1, _ts(2024, 3, 1), 23000.0),
                (1, _ts(2024, 4, 1), 26000.0),
            ]
        )
        store.write(_GROUP, table, event_timestamp_column="event_timestamp", source_prefix="ing")

        result = store.read(
            _GROUP,
            event_timestamp_column="event_timestamp",
            schema=_schema(),
            timestamp_filter=TimestampFilter(
                gte=datetime.datetime(2024, 3, 1, tzinfo=_UTC),
                lte=datetime.datetime(2024, 3, 31, tzinfo=_UTC),
            ),
        )

        assert len(result) == 1
        assert result.column("avg_price_per_sqm")[0].as_py() == 23000.0

    def test_filter_matching_no_rows_returns_empty_table(self, store: AWSOfflineStore) -> None:
        """Returns an empty table when no rows satisfy the filter."""
        table = _table([(1, _ts(2024, 2, 1), 20000.0)])
        store.write(_GROUP, table, event_timestamp_column="event_timestamp", source_prefix="ing")

        result = store.read(
            _GROUP,
            event_timestamp_column="event_timestamp",
            schema=_schema(),
            timestamp_filter=TimestampFilter(
                gte=datetime.datetime(2030, 1, 1, tzinfo=_UTC),
                lte=datetime.datetime(2030, 12, 31, tzinfo=_UTC),
            ),
        )

        assert len(result) == 0
        assert result.schema.names == _schema().names

    def test_read_from_nonexistent_bucket_raises_read_error(self, s3_client: Any) -> None:
        """OfflineStoreReadError is raised when the target bucket does not exist."""
        bad_store = AWSOfflineStore(s3_client, bucket="no-such-bucket", s3_prefix=_PREFIX)

        with pytest.raises(OfflineStoreReadError):
            bad_store.read(_GROUP, event_timestamp_column="event_timestamp", schema=_schema())
