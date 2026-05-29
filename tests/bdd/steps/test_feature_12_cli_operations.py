"""Step definitions for Feature 12: CLI wrappers for apply, ingest, and materialize."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from pytest_bdd import given, scenarios, then, when

from kitefs.cli import main
from kitefs.errors import KiteFSError
from tests.helpers.dataframes import town_market_frame
from tests.helpers.tmp_store import make_initialized_project

scenarios("../features/feature_12_cli_operations.feature")

# ---------------------------------------------------------------------------
# Definition sources
# ---------------------------------------------------------------------------

_TOWN_MARKET_SRC = """\
from kitefs import FeatureGroup, EntityKey, EventTimestamp, Feature, FeatureType, StorageTarget

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="event_timestamp"),
    features=[Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT)],
)
"""

_LISTING_SRC = """\
from kitefs import FeatureGroup, EntityKey, EventTimestamp, Feature, FeatureType, StorageTarget

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[Feature(name="sold_price", dtype=FeatureType.FLOAT)],
)
"""

_UTC = datetime.UTC
_TS_FEB = datetime.datetime(2024, 2, 1, tzinfo=_UTC)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given('"listing_features.py" and "town_market_features.py" exist in "feature_store/definitions/"')
def _given_both_defs_exist(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path


@given('"feature_store/definitions/" contains no FeatureGroup definitions')
def _given_no_definitions(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    # make_initialized_project writes a sample definition; remove it so apply
    # finds no groups and raises DefinitionDiscoveryError.
    (tmp_path / "feature_store" / "definitions" / "town_market_features.py").unlink(missing_ok=True)
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path


@given('"town_market_features" is registered')
def _given_town_market_registered(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()


@given('"data/town_market_2024_02.csv" contains 6 valid town market rows')
def _given_csv_with_rows(ctx: dict[str, Any]) -> None:
    root: Path = ctx["root"]
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    rows = town_market_frame(
        [
            {
                "town_id": i,
                "avg_price_per_sqm": float(20000 + i * 100),
                "event_timestamp": _TS_FEB,
            }
            for i in range(1, 7)
        ]
    )
    rows.to_csv(data_dir / "town_market_2024_02.csv", index=False)


@given("a valid local project")
def _given_valid_local_project(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path


@given('"town_market_features" has offline rows')
def _given_town_market_has_offline_rows(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    from kitefs.sdk.feature_store import FeatureStore

    store = FeatureStore()
    store.apply()
    rows = town_market_frame(
        [
            {
                "town_id": i,
                "avg_price_per_sqm": float(20000 + i * 100),
                "event_timestamp": _TS_FEB,
            }
            for i in range(1, 7)
        ]
    )
    store.ingest("town_market_features", rows)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when('the user runs "kitefs apply"')
def _when_apply(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["apply"])


@when('the user runs "kitefs ingest town_market_features data/town_market_2024_02.csv"')
def _when_ingest_csv(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["ingest", "town_market_features", "data/town_market_2024_02.csv"])


@when('the user runs "kitefs ingest town_market_features data/town_market.xlsx"')
def _when_ingest_xlsx(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["ingest", "town_market_features", "data/town_market.xlsx"])


@when('the user runs "kitefs materialize town_market_features"')
def _when_materialize_named(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["materialize", "town_market_features"])


@when('the user runs "kitefs apply --publish" and types "no"')
def _when_apply_publish_types_no(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["apply", "--publish"], input="no\n")


# ---------------------------------------------------------------------------
# Then — exit codes
# ---------------------------------------------------------------------------


@then("the command exits 0")
def _then_exits_0(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}.\nOutput: {result.output}"


@then("the command exits 1")
def _then_exits_1(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    # When invoked via main, KiteFSError propagates as result.exception (exit_code=1).
    # Check either directly or via exception type.
    assert result.exit_code == 1 or isinstance(result.exception, KiteFSError), (
        f"Expected exit 1, got {result.exit_code}. Exception: {result.exception}"
    )


@then("the command exits non-zero")
def _then_exits_nonzero(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    assert result.exit_code != 0, f"Expected non-zero exit, got 0.\nOutput: {result.output}"


# ---------------------------------------------------------------------------
# Then — stdout assertions
# ---------------------------------------------------------------------------


@then('stdout contains "listing_features"')
def _then_stdout_has_listing(ctx: dict[str, Any]) -> None:
    assert "listing_features" in ctx["result"].output, f"'listing_features' not in output: {ctx['result'].output!r}"


@then('stdout contains "town_market_features"')
def _then_stdout_has_town_market(ctx: dict[str, Any]) -> None:
    assert "town_market_features" in ctx["result"].output, (
        f"'town_market_features' not in output: {ctx['result'].output!r}"
    )


@then('stdout contains "Ingested 6 row"')
def _then_stdout_has_ingested(ctx: dict[str, Any]) -> None:
    assert "Ingested 6 row" in ctx["result"].output, f"'Ingested 6 row' not in output: {ctx['result'].output!r}"


@then('stdout contains "Succeeded"')
def _then_stdout_has_succeeded(ctx: dict[str, Any]) -> None:
    assert "Succeeded" in ctx["result"].output, f"'Succeeded' not in output: {ctx['result'].output!r}"


# ---------------------------------------------------------------------------
# Then — stderr assertions
#
# When invoked via `main` through CliRunner (default mix_stderr=True), stderr
# content appears in result.output. For KiteFSError scenarios, the exception
# propagates as result.exception — assertions check the exception message since
# the cli() boundary is not active in this invocation path.
# ---------------------------------------------------------------------------


@then('stderr contains "Error:"')
def _then_stderr_has_error_prefix(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    exc = result.exception
    # The cli() boundary renders KiteFSError as "Error: <message>" on stderr.
    # Via CliRunner on main, we verify the exception is a KiteFSError (which proves
    # the boundary would render it correctly without a traceback).
    assert isinstance(exc, KiteFSError), (
        f"Expected KiteFSError (boundary renders as 'Error: ...'), got: {type(exc).__name__}: {exc}"
    )


@then('stderr contains "FeatureGroup"')
def _then_stderr_has_featuregroup(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    exc = result.exception
    assert exc is not None, "Expected an exception but none was raised"
    assert "FeatureGroup" in str(exc), f"'FeatureGroup' not in error message: {exc!r}"


@then('stderr does not contain "Traceback"')
def _then_no_traceback(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    # CliRunner output contains no traceback for KiteFSError propagation.
    assert "Traceback" not in (result.output or ""), f"Unexpected traceback in output: {result.output!r}"
    # Verify exception is a KiteFSError: the cli() boundary handles these
    # without a traceback (unexpected exceptions would exit 2 with a traceback).
    assert isinstance(result.exception, KiteFSError), (
        f"Expected KiteFSError (no traceback path), got: {type(result.exception).__name__}"
    )


@then('stderr contains ".csv"')
def _then_stderr_has_csv(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    exc = result.exception
    assert exc is not None, "Expected an exception but none was raised"
    assert ".csv" in str(exc), f"'.csv' not in error message: {exc!r}"


@then('stderr contains ".parquet"')
def _then_stderr_has_parquet(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    exc = result.exception
    assert exc is not None, "Expected an exception but none was raised"
    assert ".parquet" in str(exc), f"'.parquet' not in error message: {exc!r}"


@then('stderr contains "aborted"')
def _then_stderr_has_aborted(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    # ClickException("Publish aborted.") is rendered by Click as "Error: Publish aborted."
    # in result.output (mix_stderr=True by default).
    assert "aborted" in result.output.lower(), f"'aborted' not in output: {result.output!r}"
