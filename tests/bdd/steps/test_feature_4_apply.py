"""Step definitions for Feature 4: local registry apply."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from kitefs.errors import DefinitionDiscoveryError, DefinitionValidationError
from tests.helpers.tmp_store import make_initialized_project

scenarios("../features/feature_4_apply.feature")

# ---------------------------------------------------------------------------
# Inline stand-in definition sources
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

# A second file that also declares town_market_features (used for the duplicate scenario).
_TOWN_MARKET_DUPE_SRC = """\
from kitefs import FeatureGroup, EntityKey, EventTimestamp, Feature, FeatureType, StorageTarget

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="event_timestamp"),
    features=[Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT)],
)
"""


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given('"listing_features.py" and "town_market_features.py" exist in "feature_store/definitions/"')
def _given_both_definition_files(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    # Replace the scaffolded town_market_features.py with the inline stand-in.
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path


@given('"feature_store/definitions/" contains no FeatureGroup definitions')
def _given_no_feature_group_definitions(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    # Remove the scaffolded definition so no FeatureGroup is discovered.
    (tmp_path / "feature_store" / "definitions" / "town_market_features.py").unlink()
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path


@given('the registry already contains "town_market_features"')
def _given_registry_has_town_market(ctx: dict[str, Any]) -> None:
    registry_path = ctx["root"] / "feature_store" / "registry.json"
    doc = {
        "feature_groups": {
            "town_market_features": {
                "name": "town_market_features",
                "applied_at": "2026-01-01T00:00:00.000000Z",
                "last_materialized_at": None,
            }
        }
    }
    registry_path.write_text(json.dumps(doc), encoding="utf-8")


@given('two definition files both declare a FeatureGroup named "town_market_features"')
def _given_duplicate_group_name(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs / "town_market_features_copy.py").write_text(_TOWN_MARKET_DUPE_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path


@given("the registry already contains an empty registry")
def _given_empty_registry(ctx: dict[str, Any]) -> None:
    registry_path = ctx["root"] / "feature_store" / "registry.json"
    registry_path.write_text(json.dumps({"feature_groups": {}}), encoding="utf-8")
    ctx["original_registry"] = {"feature_groups": {}}


@given('"listing_features.py" references "town_market_features"')
def _given_listing_with_join_ref(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path


@given('"town_market_features.py" is missing')
def _given_town_market_missing(ctx: dict[str, Any]) -> None:
    definition_path = ctx["root"] / "feature_store" / "definitions" / "town_market_features.py"
    definition_path.unlink()


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("the user calls FeatureStore().apply()")
def _when_apply(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    try:
        ctx["result"] = FeatureStore().apply()
        ctx["exception"] = None
    except Exception as exc:
        ctx["result"] = None
        ctx["exception"] = exc


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    assert ctx["exception"] is None, f"Unexpected exception: {ctx['exception']}"


@then('result.registered_groups equals ["listing_features", "town_market_features"]')
def _then_registered_groups(ctx: dict[str, Any]) -> None:
    assert ctx["result"].registered_groups == ["listing_features", "town_market_features"]


@then("result.published is False")
def _then_published_false(ctx: dict[str, Any]) -> None:
    assert ctx["result"].published is False


@then('"feature_store/registry.json" contains "listing_features"')
def _then_registry_contains_listing(ctx: dict[str, Any]) -> None:
    content = (ctx["root"] / "feature_store" / "registry.json").read_text(encoding="utf-8")
    assert "listing_features" in content


@then('"feature_store/registry.json" contains "town_market_features"')
def _then_registry_contains_town_market(ctx: dict[str, Any]) -> None:
    content = (ctx["root"] / "feature_store" / "registry.json").read_text(encoding="utf-8")
    assert "town_market_features" in content


@then("DefinitionDiscoveryError is raised")
def _then_discovery_error_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exception"], DefinitionDiscoveryError), (
        f"Expected DefinitionDiscoveryError, got: {type(ctx['exception'])}: {ctx['exception']}"
    )


@then("DefinitionValidationError is raised")
def _then_validation_error_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exception"], DefinitionValidationError), (
        f"Expected DefinitionValidationError, got: {type(ctx['exception'])}: {ctx['exception']}"
    )


@then('the error message contains "FeatureGroup"')
def _then_error_contains_featuregroup(ctx: dict[str, Any]) -> None:
    assert "FeatureGroup" in str(ctx["exception"])


@then('the error message contains "declare"')
def _then_error_contains_declare(ctx: dict[str, Any]) -> None:
    assert "declare" in str(ctx["exception"])


@then('the error message contains "town_market_features"')
def _then_error_contains_town_market(ctx: dict[str, Any]) -> None:
    assert "town_market_features" in str(ctx["exception"])


@then('the error message contains "duplicate"')
def _then_error_contains_duplicate(ctx: dict[str, Any]) -> None:
    assert "duplicate" in str(ctx["exception"])


@then('the error message contains "referenced"')
def _then_error_contains_referenced(ctx: dict[str, Any]) -> None:
    assert "referenced" in str(ctx["exception"])


@then('the registry still contains "town_market_features"')
def _then_registry_still_has_town_market(ctx: dict[str, Any]) -> None:
    doc = json.loads((ctx["root"] / "feature_store" / "registry.json").read_text(encoding="utf-8"))
    assert "town_market_features" in doc["feature_groups"]


@then("the registry remains an empty registry")
def _then_registry_still_empty(ctx: dict[str, Any]) -> None:
    doc = json.loads((ctx["root"] / "feature_store" / "registry.json").read_text(encoding="utf-8"))
    assert doc == {"feature_groups": {}}
