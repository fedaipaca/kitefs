"""Unit tests for AWSOnlineStore materialize and get operations."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock

import boto3
import pyarrow as pa
import pytest
from botocore.exceptions import ClientError

from kitefs.constants import DATETIME_FMT
from kitefs.errors import OnlineStoreReadError, OnlineStoreWriteError
from kitefs.providers.aws.online_store import AWSOnlineStore
from tests.helpers.aws import create_dynamodb_table

_REGION = "eu-central-1"
_PREFIX = "kitefs_"
_GROUP = "town_market_features"
_TABLE = f"{_PREFIX}{_GROUP}"
_UTC = datetime.UTC


@pytest.fixture(autouse=True)
def _use_mocked_aws(mocked_aws: None) -> None:
    """Use moto-backed AWS clients for all tests in this module."""


@pytest.fixture
def dynamodb_client() -> Any:
    """Pre-built boto3 DynamoDB client pointed at eu-central-1."""
    return boto3.client("dynamodb", region_name=_REGION)


@pytest.fixture
def store(dynamodb_client: Any) -> AWSOnlineStore:
    """AWSOnlineStore wired to the moto DynamoDB."""
    return AWSOnlineStore(dynamodb_client, table_prefix=_PREFIX)


def _ts(year: int, month: int, day: int) -> datetime.datetime:
    """Build a UTC-aware datetime for test timestamps."""
    return datetime.datetime(year, month, day, tzinfo=_UTC)


def _table(rows: list[tuple[int, datetime.datetime, float | None]]) -> pa.Table:
    """Build a minimal arrow table with town_id, event_timestamp, avg_price_per_sqm."""
    if rows:
        town_ids, timestamps, prices = zip(*rows, strict=False)
    else:
        town_ids, timestamps, prices = [], [], []
    return pa.table(
        {
            "town_id": pa.array(list(town_ids), type=pa.int64()),
            "event_timestamp": pa.array(
                [t.replace(tzinfo=None) if isinstance(t, datetime.datetime) else t for t in timestamps],
                type=pa.timestamp("us"),
            ),
            "avg_price_per_sqm": pa.array(list(prices), type=pa.float64()),
        }
    )


def _make_client_error(code: str) -> ClientError:
    """Build a botocore ClientError with the given error code."""
    return ClientError({"Error": {"Code": code, "Message": code}}, "operation")


class TestMaterialize:
    """AWSOnlineStore.materialize writes items to DynamoDB."""

    def test_creates_table_and_writes_latest_rows(self, store: AWSOnlineStore, dynamodb_client: Any) -> None:
        """Materializing a new group creates the table and all items are retrievable via get."""
        data = _table([(1, _ts(2025, 7, 1), 15200.0), (2, _ts(2025, 6, 1), 9800.0)])
        store.materialize(_GROUP, data, entity_key_column="town_id", event_timestamp_column="event_timestamp")

        result_1 = store.get(_GROUP, 1, entity_key_column="town_id", select=None)
        result_2 = store.get(_GROUP, 2, entity_key_column="town_id", select=None)
        assert result_1["town_id"] == 1
        assert result_2["town_id"] == 2

    def test_omits_null_feature_attributes(self, store: AWSOnlineStore, dynamodb_client: Any) -> None:
        """None feature values are omitted from the DynamoDB item (not stored as NULL)."""
        data = _table([(1, _ts(2025, 7, 1), None)])
        store.materialize(_GROUP, data, entity_key_column="town_id", event_timestamp_column="event_timestamp")

        # Get the raw DynamoDB item directly to check stored attributes.
        resp = dynamodb_client.get_item(TableName=_TABLE, Key={"town_id": {"N": "1"}})
        item = resp.get("Item", {})
        assert "avg_price_per_sqm" not in item

    def test_serializes_datetime_as_iso(self, store: AWSOnlineStore, dynamodb_client: Any) -> None:
        """event_timestamp is stored as an ISO-8601 UTC string matching DATETIME_FMT."""
        ts = _ts(2025, 7, 1)
        data = _table([(5, ts, 15200.0)])
        store.materialize(_GROUP, data, entity_key_column="town_id", event_timestamp_column="event_timestamp")

        result = store.get(_GROUP, 5, entity_key_column="town_id", select=None)
        expected_iso = ts.strftime(DATETIME_FMT)
        assert result["event_timestamp"] == expected_iso

    def test_writes_more_than_25_items_in_batches(self, store: AWSOnlineStore, dynamodb_client: Any) -> None:
        """30 distinct entity keys all land in the table (covers the 25-item BatchWriteItem limit)."""
        rows = [(i, _ts(2025, 1, 1), float(i * 100)) for i in range(1, 31)]
        data = _table(rows)
        store.materialize(_GROUP, data, entity_key_column="town_id", event_timestamp_column="event_timestamp")

        for i in range(1, 31):
            result = store.get(_GROUP, i, entity_key_column="town_id", select=None)
            assert result["town_id"] == i

    def test_existing_table_wrong_partition_key_name_fails(self, store: AWSOnlineStore, dynamodb_client: Any) -> None:
        """OnlineStoreWriteError when existing table partition key name does not match the entity key."""
        # Create a table with the wrong partition key name.
        create_dynamodb_table(dynamodb_client, table_name=_TABLE, hash_key="city_id", key_type="N")

        data = _table([(1, _ts(2025, 7, 1), 15200.0)])
        with pytest.raises(OnlineStoreWriteError) as exc_info:
            store.materialize(_GROUP, data, entity_key_column="town_id", event_timestamp_column="event_timestamp")

        msg = str(exc_info.value)
        assert "partition key" in msg
        assert "town_id" in msg

    def test_existing_table_wrong_partition_key_type_fails(self, store: AWSOnlineStore, dynamodb_client: Any) -> None:
        """OnlineStoreWriteError when existing table partition key type does not match the entity key dtype."""
        # Create a table with town_id as S (string), but we'll materialize with int64 (N).
        create_dynamodb_table(dynamodb_client, table_name=_TABLE, hash_key="town_id", key_type="S")

        data = _table([(1, _ts(2025, 7, 1), 15200.0)])
        with pytest.raises(OnlineStoreWriteError) as exc_info:
            store.materialize(_GROUP, data, entity_key_column="town_id", event_timestamp_column="event_timestamp")

        msg = str(exc_info.value)
        assert "partition key" in msg
        assert "town_id" in msg

    def test_unprocessed_items_retry_then_succeed(
        self, store: AWSOnlineStore, dynamodb_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Materialize succeeds when UnprocessedItems are cleared on the single retry."""
        import kitefs.providers.aws.online_store as ols

        monkeypatch.setattr(ols, "_UNPROCESSED_RETRY_DELAY_SECONDS", 0)

        # Ensure the table exists first (describe -> create path).
        store.materialize(
            _GROUP,
            _table([(1, _ts(2025, 1, 1), 100.0)]),
            entity_key_column="town_id",
            event_timestamp_column="event_timestamp",
        )

        # Now monkeypatch batch_write_item: first call returns UnprocessedItems, second succeeds.
        call_count = [0]

        def fake_batch_write(**kwargs: Any) -> dict[str, Any]:
            call_count[0] += 1
            if call_count[0] == 1:
                # Return all items as unprocessed.
                return {"UnprocessedItems": kwargs["RequestItems"]}
            return {"UnprocessedItems": {}}

        monkeypatch.setattr(dynamodb_client, "batch_write_item", fake_batch_write)

        # Should succeed — second call clears UnprocessedItems.
        store.materialize(
            _GROUP,
            _table([(2, _ts(2025, 2, 1), 200.0)]),
            entity_key_column="town_id",
            event_timestamp_column="event_timestamp",
        )
        assert call_count[0] == 2

    def test_unprocessed_items_retry_exhausted_fails(
        self, store: AWSOnlineStore, dynamodb_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OnlineStoreWriteError when UnprocessedItems persist after the single retry."""
        import kitefs.providers.aws.online_store as ols

        monkeypatch.setattr(ols, "_UNPROCESSED_RETRY_DELAY_SECONDS", 0)

        # Ensure the table exists first.
        store.materialize(
            _GROUP,
            _table([(1, _ts(2025, 1, 1), 100.0)]),
            entity_key_column="town_id",
            event_timestamp_column="event_timestamp",
        )

        # Always return UnprocessedItems.
        def always_unprocessed(**kwargs: Any) -> dict[str, Any]:
            return {"UnprocessedItems": kwargs["RequestItems"]}

        monkeypatch.setattr(dynamodb_client, "batch_write_item", always_unprocessed)

        with pytest.raises(OnlineStoreWriteError) as exc_info:
            store.materialize(
                _GROUP,
                _table([(2, _ts(2025, 2, 1), 200.0)]),
                entity_key_column="town_id",
                event_timestamp_column="event_timestamp",
            )
        assert "unprocessed" in str(exc_info.value).lower()


class TestGet:
    """AWSOnlineStore.get retrieves items from DynamoDB."""

    def test_returns_item_on_hit(self, store: AWSOnlineStore) -> None:
        """get returns a dict with all selected columns on a matching entity key."""
        data = _table([(5, _ts(2025, 7, 1), 15200.0)])
        store.materialize(_GROUP, data, entity_key_column="town_id", event_timestamp_column="event_timestamp")

        result = store.get(
            _GROUP, 5, entity_key_column="town_id", select=["town_id", "event_timestamp", "avg_price_per_sqm"]
        )
        assert result["town_id"] == 5
        assert result["event_timestamp"] == _ts(2025, 7, 1).strftime(DATETIME_FMT)

    def test_returns_empty_on_miss(self, store: AWSOnlineStore) -> None:
        """get returns {} when no item matches the entity key value."""
        data = _table([(1, _ts(2025, 7, 1), 100.0)])
        store.materialize(_GROUP, data, entity_key_column="town_id", event_timestamp_column="event_timestamp")

        result = store.get(_GROUP, 999, entity_key_column="town_id", select=None)
        assert result == {}

    def test_returns_empty_on_missing_table(self, store: AWSOnlineStore) -> None:
        """get returns {} when the group has never been materialized (table does not exist)."""
        result = store.get(_GROUP, 1, entity_key_column="town_id", select=None)
        assert result == {}

    def test_projects_only_selected_columns(self, store: AWSOnlineStore) -> None:
        """get returns only the columns listed in select, in the same order."""
        data = _table([(7, _ts(2025, 7, 1), 15200.0)])
        store.materialize(_GROUP, data, entity_key_column="town_id", event_timestamp_column="event_timestamp")

        result = store.get(_GROUP, 7, entity_key_column="town_id", select=["town_id", "avg_price_per_sqm"])
        assert list(result.keys()) == ["town_id", "avg_price_per_sqm"]
        assert "event_timestamp" not in result

    def test_null_feature_in_select_returns_none(self, store: AWSOnlineStore) -> None:
        """A selected column absent from the stored item (null feature) returns None, not missing key."""
        # Materialize a row with a null feature so the attribute is omitted in DynamoDB.
        data = _table([(3, _ts(2025, 7, 1), None)])
        store.materialize(_GROUP, data, entity_key_column="town_id", event_timestamp_column="event_timestamp")

        result = store.get(
            _GROUP,
            3,
            entity_key_column="town_id",
            select=["town_id", "event_timestamp", "avg_price_per_sqm"],
        )

        assert "avg_price_per_sqm" in result, "null feature should be present in result as None, not absent"
        assert result["avg_price_per_sqm"] is None

    def test_read_failure_raises_read_error(
        self, store: AWSOnlineStore, dynamodb_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OnlineStoreReadError containing the AWS error code when GetItem raises ClientError."""
        # Ensure the table exists so get_item is reached (not ResourceNotFoundException).
        data = _table([(1, _ts(2025, 7, 1), 100.0)])
        store.materialize(_GROUP, data, entity_key_column="town_id", event_timestamp_column="event_timestamp")

        monkeypatch.setattr(
            dynamodb_client,
            "get_item",
            MagicMock(side_effect=_make_client_error("AccessDenied")),
        )

        with pytest.raises(OnlineStoreReadError) as exc_info:
            store.get(_GROUP, 1, entity_key_column="town_id", select=None)
        assert "AccessDenied" in str(exc_info.value)
