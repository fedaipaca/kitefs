"""Step definitions for Feature 8: local offline store historical retrieval without joins."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from pytest_bdd import given, scenarios, then, when

from kitefs.errors import RetrievalParameterError
from tests.helpers.dataframes import listing_features_frame
from tests.helpers.tmp_store import make_initialized_project

scenarios("../features/feature_8_historical_retrieval.feature")

_UTC = datetime.UTC
_TS_FEB = datetime.datetime(2024, 2, 15, tzinfo=_UTC)
_TS_MAR = datetime.datetime(2024, 3, 15, tzinfo=_UTC)
_TS_APR = datetime.datetime(2024, 4, 15, tzinfo=_UTC)

# listing_features has a join key referencing town_market_features, so both
# definitions must be present for apply() to pass cross-definition validation.

_TOWN_MARKET_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup, FeatureType,
    Metadata, StorageTarget, ValidationMode,
)

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="event_timestamp"),
    features=[
        Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT),
    ],
    ingestion_validation=ValidationMode.NONE,
    metadata=Metadata(description="Town market", owner="team", tags={}),
)
"""

_LISTING_SRC_TEMPLATE = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup, FeatureType,
    JoinKey, Metadata, StorageTarget, ValidationMode,
)

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[
        Feature(name="build_year", dtype=FeatureType.INTEGER, expect=Expect().not_null().gte(1900).lte(2030)),
        Feature(name="net_area", dtype=FeatureType.INTEGER, expect=Expect().not_null().gt(0)),
        Feature(name="number_of_rooms", dtype=FeatureType.INTEGER, expect=Expect().not_null().gt(0)),
        Feature(name="sold_price", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0)),
    ],
    join_keys=[
        JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="town_market_features"),
    ],
    ingestion_validation=ValidationMode.ERROR,
    offline_retrieval_validation={retrieval_validation},
    metadata=Metadata(description="Listing features", owner="team", tags={{}}),
)
"""


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


# ---------------------------------------------------------------------------
# Project scaffold helpers
# ---------------------------------------------------------------------------


def _scaffold_with_retrieval_validation_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ctx: dict[str, Any],
    mode_expr: str = "ValidationMode.NONE",
) -> None:
    """Scaffold a project with both definitions and apply."""
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    listing_src = _LISTING_SRC_TEMPLATE.format(retrieval_validation=mode_expr)
    (defs / "listing_features.py").write_text(listing_src, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    ctx["root"] = tmp_path


def _ingest_listing_rows(ctx: dict[str, Any]) -> None:
    """Ingest sample listing rows spanning February, March, and April 2024."""
    from kitefs.sdk.feature_store import FeatureStore

    rows = [
        {
            "listing_id": 1,
            "sold_at": _TS_FEB,
            "town_id": 1,
            "net_area": 80,
            "number_of_rooms": 3,
            "build_year": 2000,
            "sold_price": 250000.0,
        },
        {
            "listing_id": 2,
            "sold_at": _TS_MAR,
            "town_id": 1,
            "net_area": 120,
            "number_of_rooms": 4,
            "build_year": 2010,
            "sold_price": 400000.0,
        },
        {
            "listing_id": 3,
            "sold_at": _TS_APR,
            "town_id": 2,
            "net_area": 60,
            "number_of_rooms": 2,
            "build_year": 1995,
            "sold_price": 180000.0,
        },
    ]
    FeatureStore().ingest("listing_features", listing_features_frame(rows))
    ctx["ingested_rows"] = rows


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given('"listing_features" is registered')
def _given_listing_registered(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scaffold_with_retrieval_validation_mode(tmp_path, monkeypatch, ctx)


@given('valid "listing_features" rows have been ingested')
def _given_listing_rows_ingested(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scaffold_with_retrieval_validation_mode(tmp_path, monkeypatch, ctx)
    _ingest_listing_rows(ctx)


@given("no listing rows exist for December 2030")
def _given_no_dec_2030_rows() -> None:
    # The offline store is always fresh per scenario (tmp_path) and no ingest
    # for December 2030 has been performed, so this Given is satisfied implicitly.
    pass


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when('the user calls get_historical_features from "listing_features" with select ["net_area", "sold_price"]')
def _when_select_two(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
        )
    except Exception as exc:
        ctx["exception"] = exc


@when('the user calls get_historical_features from "listing_features" with select ["*"]')
def _when_select_wildcard(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["*"],
        )
    except Exception as exc:
        ctx["exception"] = exc


@when("the user retrieves listing features where sold_at is in April 2024")
def _when_filter_april(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
            where={
                "sold_at": {
                    "gte": datetime.datetime(2024, 4, 1, tzinfo=_UTC),
                    "lte": datetime.datetime(2024, 4, 30, 23, 59, 59, tzinfo=_UTC),
                }
            },
        )
    except Exception as exc:
        ctx["exception"] = exc


@when('the user retrieves "net_area" and "sold_price" for December 2030')
def _when_filter_dec_2030(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
            where={
                "sold_at": {
                    "gte": datetime.datetime(2030, 12, 1, tzinfo=_UTC),
                    "lte": datetime.datetime(2030, 12, 31, 23, 59, 59, tzinfo=_UTC),
                }
            },
        )
    except Exception as exc:
        ctx["exception"] = exc


@when('the user calls get_historical_features from "listing_features" with select ["city_name"]')
def _when_unknown_feature(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["city_name"],
        )
    except Exception as exc:
        ctx["exception"] = exc


@when('the user filters on "town_id" with gte 1')
def _when_filter_non_ts_column(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["net_area"],
            where={"town_id": {"gte": datetime.datetime(2024, 1, 1, tzinfo=_UTC)}},
        )
    except Exception as exc:
        ctx["exception"] = exc


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    assert ctx["exception"] is None, f"Unexpected exception: {ctx['exception']!r}"


@then('the result columns are ["listing_id", "sold_at", "town_id", "net_area", "sold_price"]')
def _then_result_columns_selected(ctx: dict[str, Any]) -> None:
    result: pd.DataFrame = ctx["result"]
    assert list(result.columns) == ["listing_id", "sold_at", "town_id", "net_area", "sold_price"]


@then("the result includes all declared listing feature columns")
def _then_result_includes_all_columns(ctx: dict[str, Any]) -> None:
    result: pd.DataFrame = ctx["result"]
    expected = {"listing_id", "sold_at", "town_id", "build_year", "net_area", "number_of_rooms", "sold_price"}
    assert set(result.columns) == expected


@then("every returned row has sold_at in April 2024")
def _then_all_rows_in_april(ctx: dict[str, Any]) -> None:
    result: pd.DataFrame = ctx["result"]
    assert len(result) > 0, "Expected at least one row in April 2024"
    for ts in result["sold_at"]:
        # Stored timestamps are naive UTC; pd.Timestamp gives .year/.month
        ts_pd = pd.Timestamp(ts)
        assert ts_pd.year == 2024 and ts_pd.month == 4, f"Row sold_at={ts} is not in April 2024"


@then("the result has zero rows")
def _then_zero_rows(ctx: dict[str, Any]) -> None:
    result: pd.DataFrame = ctx["result"]
    assert len(result) == 0


@then("RetrievalParameterError is raised")
def _then_retrieval_error_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exception"], RetrievalParameterError), (
        f"Expected RetrievalParameterError, got {type(ctx['exception'])!r}: {ctx['exception']}"
    )


@then('the error message contains "city_name"')
def _then_error_contains_city_name(ctx: dict[str, Any]) -> None:
    assert "city_name" in str(ctx["exception"])


@then('the error message contains "feature"')
def _then_error_contains_feature(ctx: dict[str, Any]) -> None:
    assert "feature" in str(ctx["exception"])


@then('the error message contains "town_id"')
def _then_error_contains_town_id(ctx: dict[str, Any]) -> None:
    assert "town_id" in str(ctx["exception"])
