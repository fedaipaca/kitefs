"""Helpers for building pandas/PyArrow DataFrames and Tables used in tests.

Includes point-in-time dataset builders with controllable timestamps.
"""

from __future__ import annotations

import datetime
from typing import Any

import pandas as pd


def make_frame(columns: dict[str, list[Any]]) -> pd.DataFrame:
    """Build a DataFrame from a {column_name: values} mapping."""
    return pd.DataFrame(columns)


def town_market_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a DataFrame in the town_market_features schema.

    Expected keys: "town_id", "avg_price_per_sqm", "event_timestamp".
    """
    return pd.DataFrame(rows)


def utc_ts(dt_str: str) -> datetime.datetime:
    """Parse an ISO datetime string and return a UTC-aware datetime."""
    return datetime.datetime.fromisoformat(dt_str).replace(tzinfo=datetime.UTC)


def listing_features_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a DataFrame in the listing_features schema.

    Expected keys: "listing_id", "sold_at", "town_id",
    "net_area", "number_of_rooms", "build_year", "sold_price".
    """
    return pd.DataFrame(rows)
