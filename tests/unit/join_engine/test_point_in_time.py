"""Unit tests for the point-in-time join engine."""

from __future__ import annotations

import datetime

import pandas as pd

from kitefs.join_engine import point_in_time_join

_JOINED_GROUP = "town_market_features"


def _ts(value: str) -> datetime.datetime:
    """Return a naive UTC datetime matching offline-store read values."""
    return datetime.datetime.fromisoformat(value)


def _join(base_frame: pd.DataFrame, joined_frame: pd.DataFrame) -> pd.DataFrame:
    """Run the join with the Turkish real estate fixture column names."""
    return point_in_time_join(
        base_frame=base_frame,
        joined_frame=joined_frame,
        base_join_key_column="town_id",
        base_event_timestamp_column="sold_at",
        joined_entity_key_column="town_id",
        joined_event_timestamp_column="event_timestamp",
        joined_output_columns=["town_id", "event_timestamp", "avg_price_per_sqm"],
        joined_group_name=_JOINED_GROUP,
    )


class TestPointInTimeJoin:
    """point_in_time_join() attaches the latest eligible joined row."""

    def test_selects_latest_eligible_row(self) -> None:
        """The latest joined row at or before the base timestamp wins."""
        base = pd.DataFrame(
            [
                {"listing_id": 1002, "sold_at": _ts("2024-04-05 14:00:00"), "town_id": 1, "net_area": 95},
            ]
        )
        joined = pd.DataFrame(
            [
                {"town_id": 1, "event_timestamp": _ts("2024-02-01 00:00:00"), "avg_price_per_sqm": 21000.0},
                {"town_id": 1, "event_timestamp": _ts("2024-04-01 00:00:00"), "avg_price_per_sqm": 26000.0},
                {"town_id": 1, "event_timestamp": _ts("2024-05-01 00:00:00"), "avg_price_per_sqm": 30000.0},
            ]
        )

        result = _join(base, joined)

        assert result.loc[0, "town_market_features_avg_price_per_sqm"] == 26000.0
        assert result.loc[0, "town_market_features_event_timestamp"] == _ts("2024-04-01 00:00:00")

    def test_allows_equal_timestamp_match(self) -> None:
        """A joined row with the same timestamp as the base row is eligible."""
        base = pd.DataFrame(
            [
                {"listing_id": 1003, "sold_at": _ts("2024-04-01 00:00:00"), "town_id": 1, "net_area": 80},
            ]
        )
        joined = pd.DataFrame(
            [
                {"town_id": 1, "event_timestamp": _ts("2024-04-01 00:00:00"), "avg_price_per_sqm": 25000.0},
            ]
        )

        result = _join(base, joined)

        assert result.loc[0, "town_market_features_avg_price_per_sqm"] == 25000.0

    def test_keeps_null_joined_columns_without_match(self) -> None:
        """A base row with no eligible joined row remains with null joined values."""
        base = pd.DataFrame(
            [
                {"listing_id": 1010, "sold_at": _ts("2024-01-20 17:00:00"), "town_id": 3, "net_area": 70},
            ]
        )
        joined = pd.DataFrame(
            [
                {"town_id": 3, "event_timestamp": _ts("2024-02-01 00:00:00"), "avg_price_per_sqm": 18000.0},
            ]
        )

        result = _join(base, joined)

        assert result.loc[0, "listing_id"] == 1010
        assert pd.isna(result.loc[0, "town_market_features_avg_price_per_sqm"])
        assert pd.isna(result.loc[0, "town_market_features_event_timestamp"])

    def test_later_joined_row_wins_equal_timestamp_tie(self) -> None:
        """When joined timestamps tie, later joined row order wins."""
        base = pd.DataFrame(
            [
                {"listing_id": 1004, "sold_at": _ts("2024-04-10 00:00:00"), "town_id": 1, "net_area": 100},
            ]
        )
        joined = pd.DataFrame(
            [
                {"town_id": 1, "event_timestamp": _ts("2024-04-01 00:00:00"), "avg_price_per_sqm": 24000.0},
                {"town_id": 1, "event_timestamp": _ts("2024-04-01 00:00:00"), "avg_price_per_sqm": 25500.0},
            ]
        )

        result = _join(base, joined)

        assert result.loc[0, "town_market_features_avg_price_per_sqm"] == 25500.0

    def test_preserves_base_row_order(self) -> None:
        """The final result keeps rows in the same order as the base frame."""
        base = pd.DataFrame(
            [
                {"listing_id": 3, "sold_at": _ts("2024-04-15 00:00:00"), "town_id": 2, "net_area": 60},
                {"listing_id": 1, "sold_at": _ts("2024-02-15 00:00:00"), "town_id": 1, "net_area": 80},
                {"listing_id": 2, "sold_at": _ts("2024-03-15 00:00:00"), "town_id": 1, "net_area": 120},
            ]
        )
        joined = pd.DataFrame(
            [
                {"town_id": 1, "event_timestamp": _ts("2024-02-01 00:00:00"), "avg_price_per_sqm": 20000.0},
                {"town_id": 1, "event_timestamp": _ts("2024-03-01 00:00:00"), "avg_price_per_sqm": 22000.0},
                {"town_id": 2, "event_timestamp": _ts("2024-04-01 00:00:00"), "avg_price_per_sqm": 23000.0},
            ]
        )

        result = _join(base, joined)

        assert result["listing_id"].tolist() == [3, 1, 2]
        assert result["town_market_features_avg_price_per_sqm"].tolist() == [23000.0, 20000.0, 22000.0]

    def test_empty_joined_frame_adds_null_columns(self) -> None:
        """An empty joined side produces prefixed joined columns filled with nulls."""
        base = pd.DataFrame(
            [
                {"listing_id": 1001, "sold_at": _ts("2024-03-15 00:00:00"), "town_id": 1, "net_area": 80},
            ]
        )
        joined = pd.DataFrame(columns=["town_id", "event_timestamp", "avg_price_per_sqm"])

        result = _join(base, joined)

        assert list(result.columns) == [
            "listing_id",
            "sold_at",
            "town_id",
            "net_area",
            "town_market_features_town_id",
            "town_market_features_event_timestamp",
            "town_market_features_avg_price_per_sqm",
        ]
        assert pd.isna(result.loc[0, "town_market_features_avg_price_per_sqm"])
