"""Step definitions for Feature 9: point-in-time historical retrieval with joins."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from pytest_bdd import given, scenarios, then, when

from kitefs.errors import JoinError, RetrievalParameterError
from tests.helpers.dataframes import listing_features_frame, town_market_frame
from tests.helpers.tmp_store import make_initialized_project

scenarios("../features/feature_9_historical_join.feature")

_UTC = datetime.UTC

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
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(description="Town market", owner="team", tags={}),
)
"""

_CITY_MARKET_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup, FeatureType,
    Metadata, StorageTarget, ValidationMode,
)

city_market_features = FeatureGroup(
    name="city_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="city_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="event_timestamp"),
    features=[
        Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT),
    ],
    ingestion_validation=ValidationMode.NONE,
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(description="City market", owner="team", tags={}),
)
"""

_LISTING_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup, FeatureType,
    JoinKey, Metadata, StorageTarget, ValidationMode,
)

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[
        Feature(name="net_area", dtype=FeatureType.INTEGER),
        Feature(name="sold_price", dtype=FeatureType.FLOAT),
    ],
    join_keys=[
        JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="town_market_features"),
    ],
    ingestion_validation=ValidationMode.NONE,
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(description="Listing features", owner="team", tags={}),
)
"""


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through one scenario."""
    return {}


def _setup_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    with_listing: bool,
    with_town_market: bool,
    with_city_market: bool,
) -> None:
    """Scaffold a project with selected definitions and apply."""
    if not (tmp_path / "kitefs.yaml").exists():
        make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    if with_town_market:
        (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    if with_city_market:
        (defs / "city_market_features.py").write_text(_CITY_MARKET_SRC, encoding="utf-8")
    if with_listing:
        (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()


def _store() -> Any:
    from kitefs.sdk.feature_store import FeatureStore

    return FeatureStore()


@given("listing_features contains listing 1002 sold on 2024-04-05 14:00:00 in town 1")
def _given_listing_1002(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_project(tmp_path, monkeypatch, with_listing=True, with_town_market=True, with_city_market=False)
    rows = [
        {
            "listing_id": 1002,
            "sold_at": datetime.datetime(2024, 4, 5, 14, 0, 0, tzinfo=_UTC),
            "town_id": 1,
            "net_area": 90,
            "sold_price": 400000.0,
        }
    ]
    _store().ingest("listing_features", listing_features_frame(rows))
    ctx["result"] = None
    ctx["exception"] = None


@given("town_market_features has rows for town 1 dated 2024-02-01, 2024-03-01, 2024-04-01, 2024-05-01")
def _given_market_rows_for_town_1() -> None:
    rows = [
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 2, 1, tzinfo=_UTC), "avg_price_per_sqm": 20000.0},
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 3, 1, tzinfo=_UTC), "avg_price_per_sqm": 23000.0},
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 4, 1, tzinfo=_UTC), "avg_price_per_sqm": 26000.0},
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 5, 1, tzinfo=_UTC), "avg_price_per_sqm": 30000.0},
    ]
    _store().ingest("town_market_features", town_market_frame(rows))


@given("listing 1010 was sold at 2024-01-20T17:00:00Z in town_id 3")
def _given_listing_1010(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_project(tmp_path, monkeypatch, with_listing=True, with_town_market=True, with_city_market=False)
    rows = [
        {
            "listing_id": 1010,
            "sold_at": datetime.datetime(2024, 1, 20, 17, 0, 0, tzinfo=_UTC),
            "town_id": 3,
            "net_area": 70,
            "sold_price": 250000.0,
        }
    ]
    _store().ingest("listing_features", listing_features_frame(rows))
    ctx["result"] = None
    ctx["exception"] = None


@given('the earliest "town_market_features" row is dated 2024-02-01T00:00:00Z')
def _given_earliest_market_row() -> None:
    rows = [
        {"town_id": 3, "event_timestamp": datetime.datetime(2024, 2, 1, tzinfo=_UTC), "avg_price_per_sqm": 18000.0},
    ]
    _store().ingest("town_market_features", town_market_frame(rows))


@given('"listing_features" is registered')
def _given_listing_registered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_project(tmp_path, monkeypatch, with_listing=True, with_town_market=True, with_city_market=False)


@given('"city_market_features" is registered')
def _given_city_registered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_project(tmp_path, monkeypatch, with_listing=True, with_town_market=True, with_city_market=True)


@given('"listing_features" and "town_market_features" are registered')
def _given_listing_and_town_registered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_project(tmp_path, monkeypatch, with_listing=True, with_town_market=True, with_city_market=False)


@given('"town_market_features" and "city_market_features" are registered')
def _given_town_and_city_registered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_project(tmp_path, monkeypatch, with_listing=False, with_town_market=True, with_city_market=True)


@given('"town_market_features" does not declare a join key to "city_market_features"')
def _given_town_has_no_join_key() -> None:
    pass


@when("I retrieve listing features joined to town market features")
def _when_retrieve_joined_for_1002(ctx: dict[str, Any]) -> None:
    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = _store().get_historical_features(
            from_="listing_features",
            join=["town_market_features"],
            select={"listing_features": ["net_area"], "town_market_features": ["avg_price_per_sqm"]},
        )
    except Exception as exc:
        ctx["exception"] = exc


@when('the user retrieves "listing_features" joined to "town_market_features"')
def _when_retrieve_listing_town(ctx: dict[str, Any]) -> None:
    _when_retrieve_joined_for_1002(ctx)


@when('the user calls get_historical_features with join ["town_market_features", "city_market_features"]')
def _when_multi_join(ctx: dict[str, Any]) -> None:
    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = _store().get_historical_features(
            from_="listing_features",
            join=["town_market_features", "city_market_features"],
            select={
                "listing_features": ["net_area"],
                "town_market_features": ["avg_price_per_sqm"],
                "city_market_features": ["avg_price_per_sqm"],
            },
        )
    except Exception as exc:
        ctx["exception"] = exc


@when('the user calls get_historical_features with join ["town_market_features"] and select ["net_area"]')
def _when_join_with_list_select(ctx: dict[str, Any]) -> None:
    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = _store().get_historical_features(
            from_="listing_features",
            join=["town_market_features"],
            select=["net_area"],
        )
    except Exception as exc:
        ctx["exception"] = exc


@when('the user retrieves "town_market_features" joined to "city_market_features"')
def _when_join_without_relationship(ctx: dict[str, Any]) -> None:
    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = _store().get_historical_features(
            from_="town_market_features",
            join=["city_market_features"],
            select={
                "town_market_features": ["avg_price_per_sqm"],
                "city_market_features": ["avg_price_per_sqm"],
            },
        )
    except Exception as exc:
        ctx["exception"] = exc


@then("listing 1002 gets town_market_features_avg_price_per_sqm from the 2024-04-01 row")
def _then_1002_gets_april_price(ctx: dict[str, Any]) -> None:
    result: pd.DataFrame = ctx["result"]
    assert result.loc[0, "listing_id"] == 1002
    assert result.loc[0, "town_market_features_avg_price_per_sqm"] == 26000.0


@then("the 2024-05-01 market row is not used")
def _then_may_row_not_used(ctx: dict[str, Any]) -> None:
    result: pd.DataFrame = ctx["result"]
    assert result.loc[0, "town_market_features_avg_price_per_sqm"] != 30000.0


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    assert ctx["exception"] is None, f"Unexpected exception: {ctx['exception']!r}"


@then("the row for listing_id 1010 is present")
def _then_listing_1010_present(ctx: dict[str, Any]) -> None:
    result: pd.DataFrame = ctx["result"]
    assert 1010 in result["listing_id"].tolist()


@then("town_market_features_avg_price_per_sqm is null for listing_id 1010")
def _then_1010_joined_value_null(ctx: dict[str, Any]) -> None:
    result: pd.DataFrame = ctx["result"]
    row = result[result["listing_id"] == 1010].iloc[0]
    assert pd.isna(row["town_market_features_avg_price_per_sqm"])


@then("JoinError is raised")
def _then_join_error(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exception"], JoinError), (
        f"Expected JoinError, got {type(ctx['exception'])!r}: {ctx['exception']}"
    )


@then("RetrievalParameterError is raised")
def _then_retrieval_parameter_error(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exception"], RetrievalParameterError), (
        f"Expected RetrievalParameterError, got {type(ctx['exception'])!r}: {ctx['exception']}"
    )


@then('the error message contains "at most one"')
def _then_error_contains_at_most_one(ctx: dict[str, Any]) -> None:
    assert "at most one" in str(ctx["exception"])


@then('the error message contains "select"')
def _then_error_contains_select(ctx: dict[str, Any]) -> None:
    assert "select" in str(ctx["exception"])


@then('the error message contains "dict"')
def _then_error_contains_dict(ctx: dict[str, Any]) -> None:
    assert "dict" in str(ctx["exception"])


@then('the error message contains "city_market_features"')
def _then_error_contains_city(ctx: dict[str, Any]) -> None:
    assert "city_market_features" in str(ctx["exception"])


@then('the error message contains "JoinKey"')
def _then_error_contains_joinkey(ctx: dict[str, Any]) -> None:
    assert "JoinKey" in str(ctx["exception"])
