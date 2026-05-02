"""Tests for WriteResult frozen dataclass."""

from __future__ import annotations

import pytest

from kitefs.offline_store import WriteResult


class TestWriteResult:
    """WriteResult is a frozen dataclass with the expected fields."""

    def test_fields_accessible(self) -> None:
        """WriteResult fields are accessible by name."""
        result = WriteResult(rows_written=10, partitions_affected=("year=2024/month=03",))

        assert result.rows_written == 10
        assert result.partitions_affected == ("year=2024/month=03",)

    def test_frozen_rows_written(self) -> None:
        """WriteResult.rows_written cannot be reassigned."""
        result = WriteResult(rows_written=10, partitions_affected=())

        with pytest.raises(AttributeError):
            result.rows_written = 20  # type: ignore[misc]

    def test_frozen_partitions_affected(self) -> None:
        """WriteResult.partitions_affected cannot be reassigned."""
        result = WriteResult(rows_written=0, partitions_affected=())

        with pytest.raises(AttributeError):
            result.partitions_affected = ("year=2024/month=01",)  # type: ignore[misc]

    def test_importable_from_kitefs_offline_store(self) -> None:
        """WriteResult is importable from kitefs.offline_store (internal, not top-level)."""
        from kitefs.offline_store import WriteResult as Internal

        assert Internal is WriteResult

    def test_equality(self) -> None:
        """Two WriteResults with the same values are equal."""
        a = WriteResult(rows_written=5, partitions_affected=("year=2024/month=01",))
        b = WriteResult(rows_written=5, partitions_affected=("year=2024/month=01",))

        assert a == b

    def test_inequality(self) -> None:
        """Two WriteResults with different values are not equal."""
        a = WriteResult(rows_written=5, partitions_affected=("year=2024/month=01",))
        b = WriteResult(rows_written=3, partitions_affected=("year=2024/month=01",))

        assert a != b
