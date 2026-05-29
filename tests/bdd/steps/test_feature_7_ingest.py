"""Step definitions for Feature 7: local offline store ingestion."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from pytest_bdd import given, scenarios, then, when

from kitefs.errors import FeatureGroupNotFoundError, IngestionShapeError
from tests.helpers.dataframes import town_market_frame
from tests.helpers.tmp_store import make_initialized_project

scenarios("../features/feature_7_ingest.feature")

_UTC = datetime.UTC
_TS_2024_02 = datetime.datetime(2024, 2, 1, tzinfo=_UTC)

# A full definition source with configurable ingestion_validation so the FILTER
# scenario can override it without needing a separate fixture file.
_TOWN_MARKET_SRC_TEMPLATE = """\
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
    ingestion_validation={ingestion_validation},
    metadata=Metadata(
        description="Monthly town-level market aggregate",
        owner="data-science-team",
        tags={{}},
    ),
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
# Given — project scaffold helpers
# ---------------------------------------------------------------------------


def _scaffold_with_validation_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ctx: dict[str, Any],
    mode_expr: str,
) -> None:
    """Scaffold a project and apply town_market_features with the given mode string."""
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    src = _TOWN_MARKET_SRC_TEMPLATE.format(ingestion_validation=mode_expr)
    (defs / "town_market_features.py").write_text(src, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    ctx["root"] = tmp_path


@given('"town_market_features" is registered')
def _given_town_market_registered(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scaffold_with_validation_mode(tmp_path, monkeypatch, ctx, "ValidationMode.ERROR")


@given('"town_market_features" is registered with ingestion_validation FILTER')
def _given_town_market_filter(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scaffold_with_validation_mode(tmp_path, monkeypatch, ctx, "ValidationMode.FILTER")


@given('the registry contains only "town_market_features"')
def _given_registry_only_town_market(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scaffold_with_validation_mode(tmp_path, monkeypatch, ctx, "ValidationMode.ERROR")


# ---------------------------------------------------------------------------
# Given — DataFrame construction
# ---------------------------------------------------------------------------


@given("the input DataFrame contains 6 valid rows with event_timestamp 2024-02-01T00:00:00Z")
def _given_six_valid_rows(ctx: dict[str, Any]) -> None:
    ctx["df"] = town_market_frame(
        [
            {"town_id": i, "avg_price_per_sqm": float(20000 + i * 100), "event_timestamp": _TS_2024_02}
            for i in range(1, 7)
        ]
    )


@given("the input DataFrame contains valid town market rows")
def _given_valid_rows_for_error_scenario(ctx: dict[str, Any]) -> None:
    ctx["df"] = town_market_frame([{"town_id": 1, "avg_price_per_sqm": 24500.0, "event_timestamp": _TS_2024_02}])


@given('the input DataFrame contains "town_id" and "event_timestamp" but not "avg_price_per_sqm"')
def _given_df_missing_feature(ctx: dict[str, Any]) -> None:
    ctx["df"] = pd.DataFrame({"town_id": [1], "event_timestamp": [_TS_2024_02]})


@given("the input DataFrame contains 2 rows whose avg_price_per_sqm values are -10.0 and -20.0")
def _given_all_invalid_rows(ctx: dict[str, Any]) -> None:
    ctx["df"] = town_market_frame(
        [
            {"town_id": 1, "avg_price_per_sqm": -10.0, "event_timestamp": _TS_2024_02},
            {"town_id": 2, "avg_price_per_sqm": -20.0, "event_timestamp": _TS_2024_02},
        ]
    )


# ---------------------------------------------------------------------------
# Given — CSV file on disk
# ---------------------------------------------------------------------------


@given('"data/town_market_2024_02.csv" contains 6 valid town market rows')
def _given_csv_file(ctx: dict[str, Any]) -> None:
    root: Path = ctx["root"]
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    csv_path = data_dir / "town_market_2024_02.csv"
    rows = [
        {"town_id": i, "avg_price_per_sqm": float(20000 + i * 100), "event_timestamp": "2024-02-01T00:00:00Z"}
        for i in range(1, 7)
    ]
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    ctx["data_path"] = str(csv_path)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when('the user calls store.ingest("town_market_features", df)')
def _when_ingest_df(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = FeatureStore().ingest("town_market_features", ctx["df"])
    except Exception as exc:
        ctx["exception"] = exc


@when('the user calls store.ingest("town_market_features", "data/town_market_2024_02.csv")')
def _when_ingest_csv(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = FeatureStore().ingest("town_market_features", ctx["data_path"])
    except Exception as exc:
        ctx["exception"] = exc


@when('the user calls store.ingest("neighborhood_features", df)')
def _when_ingest_unknown_group(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = FeatureStore().ingest("neighborhood_features", ctx["df"])
    except Exception as exc:
        ctx["exception"] = exc


@when('the user calls store.ingest("town_market_features", "data/town_market.xlsx")')
def _when_ingest_xlsx(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    ctx["exception"] = None
    ctx["result"] = None
    try:
        ctx["result"] = FeatureStore().ingest(
            "town_market_features",
            "data/town_market.xlsx",
        )
    except Exception as exc:
        ctx["exception"] = exc


# ---------------------------------------------------------------------------
# Then — success assertions
# ---------------------------------------------------------------------------


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    assert ctx["exception"] is None, (
        f"Expected no exception but got {type(ctx['exception']).__name__}: {ctx['exception']}"
    )


@then('result.feature_group is "town_market_features"')
def _then_result_feature_group(ctx: dict[str, Any]) -> None:
    assert ctx["result"].feature_group == "town_market_features"


@then("result.accepted_rows is 6")
def _then_accepted_6(ctx: dict[str, Any]) -> None:
    assert ctx["result"].accepted_rows == 6, f"Expected 6, got {ctx['result'].accepted_rows}"


@then("result.accepted_rows is 0")
def _then_accepted_0(ctx: dict[str, Any]) -> None:
    assert ctx["result"].accepted_rows == 0, f"Expected 0, got {ctx['result'].accepted_rows}"


@then("result.rejected_rows is 0")
def _then_rejected_0(ctx: dict[str, Any]) -> None:
    assert ctx["result"].rejected_rows == 0, f"Expected 0, got {ctx['result'].rejected_rows}"


@then("result.rejected_rows is 2")
def _then_rejected_2(ctx: dict[str, Any]) -> None:
    assert ctx["result"].rejected_rows == 2, f"Expected 2, got {ctx['result'].rejected_rows}"


@then("result.written_files contains exactly 1 path")
def _then_written_files_1(ctx: dict[str, Any]) -> None:
    files = ctx["result"].written_files
    assert len(files) == 1, f"Expected 1 written file, got {len(files)}: {files}"


@then("result.written_files is empty")
def _then_written_files_empty(ctx: dict[str, Any]) -> None:
    assert ctx["result"].written_files == [], f"Expected no written files, got {ctx['result'].written_files}"


@then('the written file is under "feature_store/data/offline_store/town_market_features/year=2024/month=02/"')
def _then_file_under_partition(ctx: dict[str, Any]) -> None:
    files = ctx["result"].written_files
    assert len(files) == 1
    path = files[0]
    expected_fragment = str(
        Path("feature_store") / "data" / "offline_store" / "town_market_features" / "year=2024" / "month=02"
    )
    assert expected_fragment in path, f"Expected path containing '{expected_fragment}', got: {path}"
    assert Path(path).exists(), f"Written file does not exist: {path}"


# ---------------------------------------------------------------------------
# Then — error assertions
# ---------------------------------------------------------------------------


@then("FeatureGroupNotFoundError is raised")
def _then_not_found_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exception"], FeatureGroupNotFoundError), (
        f"Expected FeatureGroupNotFoundError, got: {type(ctx['exception'])}: {ctx['exception']}"
    )


@then("IngestionShapeError is raised")
def _then_shape_error_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exception"], IngestionShapeError), (
        f"Expected IngestionShapeError, got: {type(ctx['exception'])}: {ctx['exception']}"
    )


@then('the error message contains "neighborhood_features"')
def _then_error_contains_neighborhood(ctx: dict[str, Any]) -> None:
    assert "neighborhood_features" in str(ctx["exception"])


@then('the error message contains ".csv"')
def _then_error_contains_csv(ctx: dict[str, Any]) -> None:
    assert ".csv" in str(ctx["exception"])


@then('the error message contains ".parquet"')
def _then_error_contains_parquet(ctx: dict[str, Any]) -> None:
    assert ".parquet" in str(ctx["exception"])


@then('the error message contains "avg_price_per_sqm"')
def _then_error_contains_field(ctx: dict[str, Any]) -> None:
    assert "avg_price_per_sqm" in str(ctx["exception"])


@then("no offline file is written")
def _then_no_offline_file(ctx: dict[str, Any]) -> None:
    root: Path | None = ctx.get("root")
    if root is None:
        return
    offline_root = root / "feature_store" / "data" / "offline_store"
    parquet_files = list(offline_root.rglob("*.parquet")) if offline_root.exists() else []
    assert parquet_files == [], f"Expected no offline files, but found: {parquet_files}"
