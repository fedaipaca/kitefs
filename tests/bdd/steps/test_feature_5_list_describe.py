"""Step definitions for Feature 5: local registry list and describe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from pytest_bdd import given, scenarios, then, when

from kitefs.cli import main
from tests.helpers.tmp_store import make_initialized_project

scenarios("../features/feature_5_list_describe.feature")

# ---------------------------------------------------------------------------
# Inline definition sources — same base as feature_4 but with explicit metadata
# so feature_count values match the spec (1 feature per group).
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
from kitefs import FeatureGroup, EntityKey, EventTimestamp, Feature, FeatureType, JoinKey, StorageTarget

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[Feature(name="net_area", dtype=FeatureType.INTEGER)],
    join_keys=[JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="town_market_features")],
)
"""


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


@given('"listing_features" and "town_market_features" have been applied')
def _given_both_applied(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    # Apply so the registry is populated.
    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()


@given("the registry contains no feature groups")
def _given_empty_registry(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    # The scaffolded registry.json is already {"feature_groups": {}}.


@given('"town_market_features" has been applied')
def _given_town_market_applied(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()


@given('the registry contains only "listing_features" and "town_market_features"')
def _given_both_in_registry(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when('the user runs "kitefs list"')
def _when_list(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["list"])


@when("the user calls FeatureStore().list_feature_groups()")
def _when_list_sdk(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    try:
        ctx["sdk_result"] = FeatureStore().list_feature_groups()
        ctx["exception"] = None
    except Exception as exc:
        ctx["sdk_result"] = None
        ctx["exception"] = exc


@when('the user runs "kitefs describe town_market_features --format json"')
def _when_describe_json(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["describe", "town_market_features", "--format", "json"])


@when('the user runs "kitefs describe neighborhood_features"')
def _when_describe_unknown(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["describe", "neighborhood_features"])


# ---------------------------------------------------------------------------
# Then — exit codes
# ---------------------------------------------------------------------------


@then("the command exits 0")
def _then_exits_0(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}.\nOutput: {result.output}"


@then("the command exits non-zero")
def _then_exits_nonzero(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    assert result.exit_code != 0, f"Expected non-zero exit, got 0.\nOutput: {result.output}"


# ---------------------------------------------------------------------------
# Then — stdout assertions
# ---------------------------------------------------------------------------


@then('stdout contains "listing_features"')
def _then_stdout_has_listing(ctx: dict[str, Any]) -> None:
    assert "listing_features" in ctx["result"].output


@then('stdout contains "town_market_features"')
def _then_stdout_has_town_market(ctx: dict[str, Any]) -> None:
    assert "town_market_features" in ctx["result"].output


@then("stdout is a JSON object")
def _then_stdout_is_json_object(ctx: dict[str, Any]) -> None:
    output = ctx["result"].output.strip()
    data = json.loads(output)
    assert isinstance(data, dict), f"Expected a JSON object, got: {type(data)}"
    ctx["json_output"] = data


@then('the JSON output has entity_key.name "town_id"')
def _then_json_entity_key_name(ctx: dict[str, Any]) -> None:
    data = ctx.get("json_output") or json.loads(ctx["result"].output.strip())
    assert data["entity_key"]["name"] == "town_id"


@then('the JSON output has storage_target "OFFLINE_AND_ONLINE"')
def _then_json_storage_target(ctx: dict[str, Any]) -> None:
    data = ctx.get("json_output") or json.loads(ctx["result"].output.strip())
    assert data["storage_target"] == "OFFLINE_AND_ONLINE"


@then('the JSON output contains feature "avg_price_per_sqm"')
def _then_json_contains_feature(ctx: dict[str, Any]) -> None:
    data = ctx.get("json_output") or json.loads(ctx["result"].output.strip())
    feature_names = [f["name"] for f in data.get("features", [])]
    assert "avg_price_per_sqm" in feature_names


# ---------------------------------------------------------------------------
# Then — SDK result assertions
# ---------------------------------------------------------------------------


@then("the result is an empty list")
def _then_result_is_empty_list(ctx: dict[str, Any]) -> None:
    assert ctx["exception"] is None, f"Unexpected exception: {ctx['exception']}"
    assert ctx["sdk_result"] == []


# ---------------------------------------------------------------------------
# Then — stderr assertions
#
# When invoked via `main`, KiteFSError propagates to CliRunner rather than
# reaching the cli() error boundary. The exception object carries the message
# that the boundary would render to stderr in real CLI usage.
# ---------------------------------------------------------------------------


@then('stderr contains "FeatureGroupNotFoundError"')
def _then_stderr_has_error_class(ctx: dict[str, Any]) -> None:
    exc = ctx["result"].exception
    assert exc is not None, "Expected an exception but none was raised"
    assert type(exc).__name__ == "FeatureGroupNotFoundError", (
        f"Expected FeatureGroupNotFoundError, got {type(exc).__name__}: {exc}"
    )


@then('stderr contains "neighborhood_features"')
def _then_stderr_has_neighborhood(ctx: dict[str, Any]) -> None:
    err = str(ctx["result"].exception or "")
    assert "neighborhood_features" in err, f"Expected 'neighborhood_features' in error: {err!r}"


@then('stderr contains "listing_features"')
def _then_stderr_has_listing_err(ctx: dict[str, Any]) -> None:
    err = str(ctx["result"].exception or "")
    assert "listing_features" in err, f"Expected 'listing_features' in error: {err!r}"


@then('stderr contains "town_market_features"')
def _then_stderr_has_town_market_err(ctx: dict[str, Any]) -> None:
    err = str(ctx["result"].exception or "")
    assert "town_market_features" in err, f"Expected 'town_market_features' in error: {err!r}"
