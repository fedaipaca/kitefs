"""Step definitions for Feature 10: local SQLite online store materialization."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from kitefs.errors import FeatureGroupNotFoundError, FeatureGroupNotMaterializableError
from tests.helpers.dataframes import town_market_frame
from tests.helpers.tmp_store import make_initialized_project

scenarios("../features/feature_10_materialize.feature")

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
        Feature(name="sold_price", dtype=FeatureType.FLOAT),
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


@given('"town_market_features" has 72 offline rows for 12 months and 6 towns')
def _given_72_offline_rows(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold project, apply, ingest 12 months x 6 towns = 72 rows."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    store = FeatureStore()

    for month in range(1, 13):
        rows = [
            {
                "town_id": town_id,
                "avg_price_per_sqm": float(20000 + town_id * 100 + month),
                "event_timestamp": _ts(f"2024-{month:02d}-01T00:00:00"),
            }
            for town_id in range(1, 7)
        ]
        store.ingest("town_market_features", town_market_frame(rows))

    ctx["root"] = tmp_path
    ctx["store"] = store


@given('the registry contains only "town_market_features"')
def _given_registry_only_town_market(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold project with only town_market_features registered."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    ctx["root"] = tmp_path
    ctx["store"] = FeatureStore()


@given('"listing_features" is registered with storage_target OFFLINE')
def _given_listing_offline(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold project with listing_features as OFFLINE-only."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    ctx["root"] = tmp_path
    ctx["store"] = FeatureStore()


@given('"town_market_features" is registered with storage_target OFFLINE_AND_ONLINE')
def _given_town_market_online(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold project with town_market_features registered (no ingestion)."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    ctx["root"] = tmp_path
    ctx["store"] = FeatureStore()


@given('"town_market_features" has no offline rows')
def _given_no_offline_rows(ctx: dict[str, Any]) -> None:
    """No-op: the previous Given already leaves no rows ingested."""


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when('the user calls store.materialize("town_market_features")')
def _when_materialize_town_market(ctx: dict[str, Any]) -> None:
    """Call store.materialize() for town_market_features and capture the result."""
    try:
        ctx["result"] = ctx["store"].materialize("town_market_features")
        ctx["exc"] = None
    except Exception as exc:
        ctx["exc"] = exc
        ctx["result"] = None


@when('the user calls store.materialize("neighborhood_features")')
def _when_materialize_neighborhood(ctx: dict[str, Any]) -> None:
    """Call store.materialize() for a group not in the registry."""
    try:
        ctx["result"] = ctx["store"].materialize("neighborhood_features")
        ctx["exc"] = None
    except Exception as exc:
        ctx["exc"] = exc
        ctx["result"] = None


@when('the user calls store.materialize("listing_features")')
def _when_materialize_listing(ctx: dict[str, Any]) -> None:
    """Call store.materialize() for an OFFLINE-only group."""
    try:
        ctx["result"] = ctx["store"].materialize("listing_features")
        ctx["exc"] = None
    except Exception as exc:
        ctx["exc"] = exc
        ctx["result"] = None


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    """Assert that no exception was captured during the When step."""
    assert ctx["exc"] is None, f"Unexpected exception: {ctx['exc']}"


@then('result.succeeded contains "town_market_features"')
def _then_succeeded_contains_town_market(ctx: dict[str, Any]) -> None:
    assert "town_market_features" in ctx["result"].succeeded


@then("result.skipped is empty")
def _then_skipped_empty(ctx: dict[str, Any]) -> None:
    assert ctx["result"].skipped == []


@then("result.failed is empty")
def _then_failed_empty(ctx: dict[str, Any]) -> None:
    assert ctx["result"].failed == []


@then("SQLite table town_market_features has exactly 6 rows")
def _then_sqlite_has_6_rows(ctx: dict[str, Any]) -> None:
    db_path = ctx["root"] / "feature_store" / "data" / "online_store" / "online.db"
    with sqlite3.connect(str(db_path)) as conn:
        count = conn.execute('SELECT COUNT(*) FROM "town_market_features"').fetchone()[0]
    assert count == 6


@then('the registry entry for "town_market_features" has last_materialized_at set')
def _then_registry_last_materialized_set(ctx: dict[str, Any]) -> None:
    desc = ctx["store"].describe_feature_group("town_market_features")
    assert desc.last_materialized_at is not None


@then("FeatureGroupNotFoundError is raised")
def _then_not_found_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exc"], FeatureGroupNotFoundError), (
        f"Expected FeatureGroupNotFoundError, got {type(ctx['exc'])}"
    )


@then("FeatureGroupNotMaterializableError is raised")
def _then_not_materializable_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exc"], FeatureGroupNotMaterializableError), (
        f"Expected FeatureGroupNotMaterializableError, got {type(ctx['exc'])}"
    )


@then('the error message contains "neighborhood_features"')
def _then_error_contains_neighborhood(ctx: dict[str, Any]) -> None:
    assert "neighborhood_features" in str(ctx["exc"])


@then('the error message contains "listing_features"')
def _then_error_contains_listing(ctx: dict[str, Any]) -> None:
    assert "listing_features" in str(ctx["exc"])


@then('the error message contains "OFFLINE"')
def _then_error_contains_offline(ctx: dict[str, Any]) -> None:
    assert "OFFLINE" in str(ctx["exc"])


@then('result.skipped contains a group named "town_market_features" with reason "no offline data"')
def _then_skipped_contains_town_market(ctx: dict[str, Any]) -> None:
    skipped_names = {s.name: s.reason for s in ctx["result"].skipped}
    assert "town_market_features" in skipped_names
    assert skipped_names["town_market_features"] == "no offline data"


@then("result.succeeded is empty")
def _then_succeeded_empty(ctx: dict[str, Any]) -> None:
    assert ctx["result"].succeeded == []
