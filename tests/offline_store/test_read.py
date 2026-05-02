"""Tests for OfflineStoreManager.read() — partition pruning, row filtering, edge cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from helpers import make_local_config

from kitefs.exceptions import RetrievalError
from kitefs.offline_store import OfflineStoreManager
from kitefs.providers.local import LocalProvider


def _make_manager(tmp_path: Path) -> tuple[OfflineStoreManager, LocalProvider, Path]:
    """Create an OfflineStoreManager backed by a LocalProvider in tmp_path."""
    config = make_local_config(tmp_path)
    config.storage_root.mkdir(parents=True, exist_ok=True)
    provider = LocalProvider(config)
    manager = OfflineStoreManager(provider)
    return manager, provider, config.storage_root


def _seed_data(manager: OfflineStoreManager, group: str = "test_group") -> None:
    """Write test data spanning Jan-Apr 2024 into the offline store."""
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5, 6],
            "event_timestamp": pd.to_datetime(
                [
                    "2024-01-10",
                    "2024-01-25",
                    "2024-02-15",
                    "2024-03-05",
                    "2024-03-20",
                    "2024-04-10",
                ]
            ),
            "value": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
        }
    )
    manager.write(group, df, "event_timestamp")


class TestReadNoFilter:
    """Read all data without any filtering."""

    def test_returns_all_rows(self, tmp_path: Path) -> None:
        """Reading without filters returns every ingested row."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read("test_group", "event_timestamp")

        assert len(result) == 6

    def test_returns_correct_columns(self, tmp_path: Path) -> None:
        """Returned DataFrame has the original columns."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read("test_group", "event_timestamp")

        assert set(result.columns) == {"id", "event_timestamp", "value"}


class TestReadWithTimeFilter:
    """Read with time_filter operators for row-level filtering."""

    def test_gte_filter(self, tmp_path: Path) -> None:
        """gte filter includes records at and after the boundary."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={"gte": datetime(2024, 3, 1, tzinfo=UTC)},
        )

        # Should include 2024-03-05, 2024-03-20, 2024-04-10
        assert len(result) == 3
        assert all(result["event_timestamp"] >= pd.Timestamp("2024-03-01"))

    def test_lte_filter(self, tmp_path: Path) -> None:
        """lte filter includes records at and before the boundary."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={"lte": datetime(2024, 2, 15, tzinfo=UTC)},
        )

        # Should include 2024-01-10, 2024-01-25, 2024-02-15
        assert len(result) == 3
        assert all(result["event_timestamp"] <= pd.Timestamp("2024-02-15"))

    def test_gt_filter_exclusive(self, tmp_path: Path) -> None:
        """gt filter excludes the exact boundary value."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={"gt": datetime(2024, 3, 5, tzinfo=UTC)},
        )

        # Excludes 2024-03-05 exactly; includes 2024-03-20 and 2024-04-10
        assert len(result) == 2
        assert all(result["event_timestamp"] > pd.Timestamp("2024-03-05"))

    def test_lt_filter_exclusive(self, tmp_path: Path) -> None:
        """lt filter excludes the exact boundary value."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={"lt": datetime(2024, 2, 15, tzinfo=UTC)},
        )

        # Excludes 2024-02-15 exactly; includes 2024-01-10, 2024-01-25
        assert len(result) == 2
        assert all(result["event_timestamp"] < pd.Timestamp("2024-02-15"))

    def test_combined_gte_lte_range(self, tmp_path: Path) -> None:
        """Combined gte+lte creates a closed time range."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={
                "gte": datetime(2024, 2, 1, tzinfo=UTC),
                "lte": datetime(2024, 3, 10, tzinfo=UTC),
            },
        )

        # Should include 2024-02-15, 2024-03-05
        assert len(result) == 2

    def test_filter_returns_empty_when_no_match(self, tmp_path: Path) -> None:
        """Time filter that matches no records returns empty DataFrame."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={"gte": datetime(2025, 1, 1, tzinfo=UTC)},
        )

        assert result.empty


class TestReadWithUpperBound:
    """Read with upper_bound for partition pruning (used for joined group reads)."""

    def test_upper_bound_prunes_future_partitions(self, tmp_path: Path) -> None:
        """upper_bound limits partitions to those at or before the given month."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read(
            "test_group",
            "event_timestamp",
            upper_bound=datetime(2024, 2, 28, tzinfo=UTC),
        )

        # Partitions year=2024/month=01 and year=2024/month=02 are included.
        # Partitions year=2024/month=03 and year=2024/month=04 are pruned.
        assert len(result) == 3
        assert all(result["event_timestamp"] <= pd.Timestamp("2024-02-28"))

    def test_upper_bound_mid_month_includes_full_month(self, tmp_path: Path) -> None:
        """upper_bound in the middle of a month still includes that full month's partition."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        # Upper bound is 2024-03-10: month=03 partition starts 2024-03-01 <= upper_bound.
        result = manager.read(
            "test_group",
            "event_timestamp",
            upper_bound=datetime(2024, 3, 10, tzinfo=UTC),
        )

        # Partitions 01, 02, 03 included. But no row-level filter — all rows in those partitions.
        assert len(result) == 5  # Rows in Jan(2), Feb(1), Mar(2)


class TestReadCombinedFilters:
    """Read with both time_filter and upper_bound."""

    def test_combined_time_filter_and_upper_bound(self, tmp_path: Path) -> None:
        """Both time_filter and upper_bound constrain the result."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={"gte": datetime(2024, 2, 1, tzinfo=UTC)},
            upper_bound=datetime(2024, 3, 10, tzinfo=UTC),
        )

        # upper_bound prunes month=04. time_filter gte 2024-02-01 prunes month=01.
        # Remaining: month=02 (2024-02-15), month=03 (2024-03-05, 2024-03-20).
        # Row filter: gte 2024-02-01 keeps all three.
        assert len(result) == 3


class TestReadPartitionPruning:
    """Verify partition pruning reduces the partition list passed to the provider."""

    def test_pruning_reduces_partitions_read(self, tmp_path: Path) -> None:
        """Only pruned partitions are passed to provider.read_offline()."""
        manager, provider, _ = _make_manager(tmp_path)
        _seed_data(manager)

        with patch.object(provider, "read_offline", wraps=provider.read_offline) as mock_read:
            manager.read(
                "test_group",
                "event_timestamp",
                time_filter={"gte": datetime(2024, 3, 1, tzinfo=UTC)},
            )

            mock_read.assert_called_once()
            partitions_arg = mock_read.call_args[1].get("partition_paths") or mock_read.call_args[0][1]
            # Only month=03 and month=04 should be read.
            assert set(partitions_arg) == {"year=2024/month=03", "year=2024/month=04"}


class TestReadEmptyCases:
    """Edge cases: no partitions, non-existent group."""

    def test_no_partitions_returns_empty_df(self, tmp_path: Path) -> None:
        """Reading a group with no data returns an empty DataFrame."""
        manager, _, _ = _make_manager(tmp_path)

        result = manager.read("nonexistent_group", "event_timestamp")

        assert result.empty

    def test_filter_pruning_removes_all_returns_empty(self, tmp_path: Path) -> None:
        """If pruning removes all partitions, returns empty DataFrame without I/O."""
        manager, provider, _ = _make_manager(tmp_path)
        _seed_data(manager)

        with patch.object(provider, "read_offline", wraps=provider.read_offline) as mock_read:
            result = manager.read(
                "test_group",
                "event_timestamp",
                time_filter={"gte": datetime(2025, 6, 1, tzinfo=UTC)},
            )

            assert result.empty
            mock_read.assert_not_called()


class TestReadRowFilterPrecision:
    """Row-level filter is precise even when partition pruning is coarse."""

    def test_mid_month_filter_precise(self, tmp_path: Path) -> None:
        """Filtering mid-month returns only matching rows, not the full partition."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={
                "gte": datetime(2024, 1, 20, tzinfo=UTC),
                "lte": datetime(2024, 1, 30, tzinfo=UTC),
            },
        )

        # Only 2024-01-25 falls in [Jan 20, Jan 30].
        assert len(result) == 1
        assert result.iloc[0]["id"] == 2


class TestReadTimezoneHandling:
    """Timezone alignment between stored data and filter values."""

    def test_tz_naive_filter_against_tz_naive_data(self, tmp_path: Path) -> None:
        """Tz-naive filter works against tz-naive stored data."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={"gte": datetime(2024, 3, 1, tzinfo=UTC)},
        )

        assert len(result) == 3

    def test_non_utc_timezone_filter(self, tmp_path: Path) -> None:
        """A filter value in a non-UTC timezone is correctly converted to UTC."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        # UTC+5: 2024-03-01T00:00 UTC+5 == 2024-02-29T19:00 UTC
        # So gte with this value should include everything from 2024-02-29 19:00 UTC onward.
        utc_plus_5 = timezone(timedelta(hours=5))
        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={"gte": datetime(2024, 3, 1, tzinfo=utc_plus_5)},
        )

        # 2024-02-29T19:00 UTC is before 2024-03-05, 2024-03-20, 2024-04-10
        # and after 2024-02-15, 2024-01-10, 2024-01-25
        assert len(result) == 3


class TestReadInvalidOperator:
    """Unsupported operators raise RetrievalError."""

    def test_invalid_operator_eq_raises_retrieval_error(self, tmp_path: Path) -> None:
        """Operator 'eq' is not supported in time_filter and raises RetrievalError."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        with pytest.raises(RetrievalError, match="Unsupported time filter operator 'eq'"):
            manager.read(
                "test_group",
                "event_timestamp",
                time_filter={"eq": datetime(2024, 3, 5, tzinfo=UTC)},
            )

    def test_invalid_operator_typo_raises_retrieval_error(self, tmp_path: Path) -> None:
        """A typo like 'get' is caught as an unsupported operator."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        with pytest.raises(RetrievalError, match="Unsupported time filter operator 'get'"):
            manager.read(
                "test_group",
                "event_timestamp",
                time_filter={"get": datetime(2024, 3, 5, tzinfo=UTC)},
            )


class TestReadUnrecognizedPartitionFormat:
    """Partitions with non-standard directory names are handled safely."""

    def test_unrecognized_partition_included_in_unfiltered_read(self, tmp_path: Path) -> None:
        """Non-standard partition directories don't crash reads."""
        manager, _, storage_root = _make_manager(tmp_path)
        _seed_data(manager)

        # Create a non-standard directory under the group's offline store.
        custom_dir = storage_root / "data" / "offline_store" / "test_group" / "custom=foo"
        custom_dir.mkdir(parents=True)

        # Unfiltered read should still return all 6 rows from real partitions.
        result = manager.read("test_group", "event_timestamp")

        assert len(result) == 6


class TestReadNonUtcFilterPrecision:
    """Non-UTC timezone filter values are correctly converted to UTC for row filtering."""

    def test_non_utc_filter_precise_boundary(self, tmp_path: Path) -> None:
        """A non-UTC filter value is converted to UTC before row-level comparison."""
        manager, _, _ = _make_manager(tmp_path)
        # Seed data with a record at 2024-02-29T20:00 (tz-naive, treated as UTC).
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "event_timestamp": pd.to_datetime(["2024-02-29 20:00:00", "2024-03-05 10:00:00"]),
                "value": [10.0, 20.0],
            }
        )
        manager.write("test_group", df, "event_timestamp")

        # UTC+5: 2024-03-01T00:00+05:00 == 2024-02-29T19:00 UTC.
        # Record at 20:00 UTC is AFTER 19:00 UTC, so it should be included.
        utc_plus_5 = timezone(timedelta(hours=5))
        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={"gte": datetime(2024, 3, 1, tzinfo=utc_plus_5)},
        )

        assert len(result) == 2
        assert sorted(result["id"].tolist()) == [1, 2]


class TestReadNaTFilterValue:
    """NaT as a filter value raises RetrievalError."""

    def test_nat_filter_value_raises_retrieval_error(self, tmp_path: Path) -> None:
        """Passing pd.NaT as a time_filter value raises RetrievalError."""
        manager, _, _ = _make_manager(tmp_path)
        _seed_data(manager)

        with pytest.raises(RetrievalError, match="Cannot convert"):
            manager.read(
                "test_group",
                "event_timestamp",
                time_filter={"gte": pd.NaT},
            )
