"""Step definitions for Feature 11: local online store retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from kitefs.errors import FeatureGroupNotMaterializableError, RetrievalParameterError
from tests.helpers.dataframes import town_market_frame
from tests.helpers.tmp_store import make_initialized_project

scenarios("../features/feature_11_online_retrieval.feature")

_TOWN_MARKET_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup, FeatureType,
    Metadata, StorageTarget, ValidationMode,
)

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="event_timestamp"),
    features=[
        Feature(
            name="avg_price_per_sqm",
            dtype=FeatureType.FLOAT,
            expect=Expect().not_null().gt(0),
        ),
    ],
    ingestion_validation=ValidationMode.ERROR,
    metadata=Metadata(
        description="Monthly town-level market aggregate",
        owner="data-science-team",
        tags={},
    ),
)
"""

_LISTING_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup, FeatureType,
    Metadata, StorageTarget, ValidationMode,
)

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[
        Feature(name="net_area", dtype=FeatureType.INTEGER),
    ],
    ingestion_validation=ValidationMode.NONE,
    metadata=Metadata(description="Listing features", owner="team", tags={}),
)
"""


def _ts(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str).replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given('"town_market_features" has been materialized with a row for town_id 1')
def _given_materialized_with_town_id_1(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold, apply, ingest rows for town_id 1, and materialize."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    store = FeatureStore()
    rows = [
        {"town_id": 1, "avg_price_per_sqm": 27800.0, "event_timestamp": _ts("2025-06-01T00:00:00")},
        {"town_id": 2, "avg_price_per_sqm": 18000.0, "event_timestamp": _ts("2025-06-01T00:00:00")},
    ]
    store.ingest("town_market_features", town_market_frame(rows))
    store.materialize("town_market_features")
    ctx["root"] = tmp_path
    ctx["store"] = FeatureStore()


@given('"town_market_features" has been materialized without a row for town_id 999')
def _given_materialized_without_town_id_999(
    ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scaffold, apply, ingest rows that do NOT include town_id 999, and materialize."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    store = FeatureStore()
    rows = [
        {"town_id": 1, "avg_price_per_sqm": 24500.0, "event_timestamp": _ts("2025-06-01T00:00:00")},
    ]
    store.ingest("town_market_features", town_market_frame(rows))
    store.materialize("town_market_features")
    ctx["root"] = tmp_path
    ctx["store"] = FeatureStore()


@given('"town_market_features" is registered with storage_target OFFLINE_AND_ONLINE')
def _given_town_market_registered_online(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold and apply town_market_features with no ingestion or materialization."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    ctx["root"] = tmp_path
    ctx["store"] = FeatureStore()


@given('"town_market_features" has not been materialized')
def _given_not_materialized(ctx: dict[str, Any]) -> None:
    """No-op: the previous Given already left no materialization."""


@given('"listing_features" is registered with storage_target OFFLINE')
def _given_listing_offline(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold and apply listing_features as an OFFLINE-only group."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    ctx["root"] = tmp_path
    ctx["store"] = FeatureStore()


@given('"town_market_features" is registered with entity key "town_id"')
def _given_town_market_with_entity_key(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold and apply town_market_features (entity key = town_id)."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    ctx["root"] = tmp_path
    ctx["store"] = FeatureStore()


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    'the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 1'  # noqa: E501
)
def _when_get_town_market_town_id_1(ctx: dict[str, Any]) -> None:
    try:
        ctx["result"] = ctx["store"].get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 1}},
        )
        ctx["exc"] = None
    except Exception as exc:
        ctx["exc"] = exc
        ctx["result"] = None


@when(
    'the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 999'  # noqa: E501
)
def _when_get_town_market_town_id_999(ctx: dict[str, Any]) -> None:
    try:
        ctx["result"] = ctx["store"].get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 999}},
        )
        ctx["exc"] = None
    except Exception as exc:
        ctx["exc"] = exc
        ctx["result"] = None


@when(
    'the user calls get_online_features from "listing_features" with select ["net_area"] where listing_id equals 1002'
)
def _when_get_listing_features(ctx: dict[str, Any]) -> None:
    try:
        ctx["result"] = ctx["store"].get_online_features(
            from_="listing_features",
            select=["net_area"],
            where={"listing_id": {"eq": 1002}},
        )
        ctx["exc"] = None
    except Exception as exc:
        ctx["exc"] = exc
        ctx["result"] = None


@when("the user calls get_online_features with where avg_price_per_sqm equals 24500.0")
def _when_get_with_wrong_where_field(ctx: dict[str, Any]) -> None:
    try:
        ctx["result"] = ctx["store"].get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"avg_price_per_sqm": {"eq": 24500.0}},
        )
        ctx["exc"] = None
    except Exception as exc:
        ctx["exc"] = exc
        ctx["result"] = None


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    assert ctx["exc"] is None, f"Unexpected exception: {ctx['exc']}"


@then("the result contains town_id 1")
def _then_result_contains_town_id_1(ctx: dict[str, Any]) -> None:
    assert ctx["result"]["town_id"] == 1


@then('the result contains "event_timestamp"')
def _then_result_contains_event_timestamp(ctx: dict[str, Any]) -> None:
    assert "event_timestamp" in ctx["result"]


@then('the result contains "avg_price_per_sqm"')
def _then_result_contains_avg_price(ctx: dict[str, Any]) -> None:
    assert "avg_price_per_sqm" in ctx["result"]


@then("the result is {}")
def _then_result_is_empty(ctx: dict[str, Any]) -> None:
    assert ctx["result"] == {}


@then("FeatureGroupNotMaterializableError is raised")
def _then_not_materializable_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exc"], FeatureGroupNotMaterializableError), (
        f"Expected FeatureGroupNotMaterializableError, got {type(ctx['exc'])}"
    )


@then("RetrievalParameterError is raised")
def _then_retrieval_parameter_error_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exc"], RetrievalParameterError), f"Expected RetrievalParameterError, got {type(ctx['exc'])}"


@then('the error message contains "listing_features"')
def _then_error_contains_listing_features(ctx: dict[str, Any]) -> None:
    assert "listing_features" in str(ctx["exc"])


@then('the error message contains "OFFLINE"')
def _then_error_contains_offline(ctx: dict[str, Any]) -> None:
    assert "OFFLINE" in str(ctx["exc"])


@then('the error message contains "avg_price_per_sqm"')
def _then_error_contains_avg_price(ctx: dict[str, Any]) -> None:
    assert "avg_price_per_sqm" in str(ctx["exc"])


@then('the error message contains "town_id"')
def _then_error_contains_town_id(ctx: dict[str, Any]) -> None:
    assert "town_id" in str(ctx["exc"])
