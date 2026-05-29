"""Step definitions for Feature 1: definition types and construction-time validation."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from kitefs import (
    DefinitionError,
    EntityKey,
    EventTimestamp,
    Expect,
    Feature,
    FeatureGroup,
    FeatureType,
    JoinKey,
    Metadata,
    StorageTarget,
    ValidationMode,
)
from tests.fixtures.definitions import build_listing_features

scenarios("../features/feature_1_definitions.feature")


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


# ---------------------------------------------------------------------------
# Scenario: Construct the reference listing feature group
# ---------------------------------------------------------------------------


@given('the "listing_features" definition from the reference use case')
def _given_listing_features_def(ctx: dict[str, Any]) -> None:
    ctx["build"] = build_listing_features


@when("the user constructs the FeatureGroup")
def _when_construct_feature_group(ctx: dict[str, Any]) -> None:
    try:
        ctx["result"] = ctx["build"]()
        ctx["exc"] = None
    except DefinitionError as exc:
        ctx["exc"] = exc
        ctx["result"] = None


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    assert ctx.get("exc") is None, f"Unexpected DefinitionError: {ctx.get('exc')}"


@then('the FeatureGroup name is "listing_features"')
def _then_feature_group_name(ctx: dict[str, Any]) -> None:
    assert ctx["result"].name == "listing_features"


# ---------------------------------------------------------------------------
# Scenario: Reject an invalid entity key dtype
# ---------------------------------------------------------------------------


@given('an EntityKey named "listing_id" with dtype FLOAT')
def _given_invalid_entity_key(ctx: dict[str, Any]) -> None:
    ctx["build"] = lambda: EntityKey(name="listing_id", dtype=FeatureType.FLOAT)


@when("the user constructs the EntityKey")
def _when_construct_entity_key(ctx: dict[str, Any]) -> None:
    try:
        ctx["result"] = ctx["build"]()
        ctx["exc"] = None
    except DefinitionError as exc:
        ctx["exc"] = exc
        ctx["result"] = None


@then("DefinitionError is raised")
def _then_definition_error_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx.get("exc"), DefinitionError), f"Expected DefinitionError but got: {ctx.get('exc')!r}"


@then('the error message contains "listing_id"')
def _then_message_contains_listing_id(ctx: dict[str, Any]) -> None:
    assert "listing_id" in str(ctx["exc"])


@then('the error message contains "STRING or INTEGER"')
def _then_message_contains_string_or_integer(ctx: dict[str, Any]) -> None:
    assert "STRING or INTEGER" in str(ctx["exc"])


# ---------------------------------------------------------------------------
# Scenario: Reject an invalid expectation threshold
# ---------------------------------------------------------------------------


@given("a new Expect object")
def _given_new_expect(ctx: dict[str, Any]) -> None:
    ctx["expect"] = Expect()


@when('the user declares gt "zero"')
def _when_declare_gt_zero(ctx: dict[str, Any]) -> None:
    try:
        ctx["expect"].gt("zero")
        ctx["exc"] = None
    except DefinitionError as exc:
        ctx["exc"] = exc


@then('the error message contains "gt"')
def _then_message_contains_gt(ctx: dict[str, Any]) -> None:
    assert "gt" in str(ctx["exc"])


@then('the error message contains "int, float, or datetime"')
def _then_message_contains_numeric_types(ctx: dict[str, Any]) -> None:
    assert "int, float, or datetime" in str(ctx["exc"])


# ---------------------------------------------------------------------------
# Scenario: Reject metadata without an owner
# ---------------------------------------------------------------------------


@given('Metadata with description "Monthly town-level market aggregate" and an empty owner')
def _given_metadata_empty_owner(ctx: dict[str, Any]) -> None:
    ctx["build"] = lambda: Metadata(
        description="Monthly town-level market aggregate",
        owner="",
    )


@when("the user constructs the Metadata")
def _when_construct_metadata(ctx: dict[str, Any]) -> None:
    try:
        ctx["result"] = ctx["build"]()
        ctx["exc"] = None
    except DefinitionError as exc:
        ctx["exc"] = exc
        ctx["result"] = None


@then('the error message contains "owner"')
def _then_message_contains_owner(ctx: dict[str, Any]) -> None:
    assert "owner" in str(ctx["exc"])


# ---------------------------------------------------------------------------
# Scenario: Reject a feature group with an invalid name
# ---------------------------------------------------------------------------


@given('a FeatureGroup named "123-invalid"')
def _given_invalid_fg_name(ctx: dict[str, Any]) -> None:
    ctx["build"] = lambda: FeatureGroup(
        name="123-invalid",
        storage_target=StorageTarget.OFFLINE,
        entity_key=EntityKey(name="entity_id", dtype=FeatureType.INTEGER),
        event_timestamp=EventTimestamp(name="event_ts"),
        features=[Feature(name="value", dtype=FeatureType.FLOAT)],
    )


@then('the error message contains "123-invalid"')
def _then_message_contains_invalid_name(ctx: dict[str, Any]) -> None:
    assert "123-invalid" in str(ctx["exc"])


@then('the error message contains "identifier"')
def _then_message_contains_identifier(ctx: dict[str, Any]) -> None:
    assert "identifier" in str(ctx["exc"])


# ---------------------------------------------------------------------------
# Scenario: Reject duplicate field names within a feature group
# ---------------------------------------------------------------------------


@given('a FeatureGroup named "listing_features" whose entity key and feature are both named "listing_id"')
def _given_fg_duplicate_names(ctx: dict[str, Any]) -> None:
    ctx["build"] = lambda: FeatureGroup(
        name="listing_features",
        storage_target=StorageTarget.OFFLINE,
        entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
        event_timestamp=EventTimestamp(name="sold_at"),
        features=[Feature(name="listing_id", dtype=FeatureType.FLOAT)],
    )


@then('the error message contains "listing_id"')
def _then_message_contains_field_name(ctx: dict[str, Any]) -> None:
    assert "listing_id" in str(ctx["exc"])


@then('the error message contains "duplicate"')
def _then_message_contains_duplicate(ctx: dict[str, Any]) -> None:
    assert "duplicate" in str(ctx["exc"])


# ---------------------------------------------------------------------------
# Scenario: Import public definition names from the top-level package
# ---------------------------------------------------------------------------


@given(
    "the user imports FeatureGroup, Feature, EntityKey, EventTimestamp, FeatureType, "
    "StorageTarget, Expect, JoinKey, ValidationMode, Metadata, and DefinitionError from kitefs"
)
def _given_imports_done(ctx: dict[str, Any]) -> None:
    # All names are already imported at the top of this module; no exception at import time.
    ctx["imported"] = [
        FeatureGroup,
        Feature,
        EntityKey,
        EventTimestamp,
        FeatureType,
        StorageTarget,
        Expect,
        JoinKey,
        ValidationMode,
        Metadata,
        DefinitionError,
    ]
    ctx["exc"] = None


@when("the imports complete")
def _when_imports_complete(ctx: dict[str, Any]) -> None:
    pass  # imports happened at module load; nothing to do here
