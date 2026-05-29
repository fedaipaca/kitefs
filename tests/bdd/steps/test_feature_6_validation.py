"""Step definitions for Feature 6: validation engine."""

from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import pytest
from pytest_bdd import given, scenarios, then, when

from kitefs.enums import ValidationMode
from kitefs.errors import ValidationError
from kitefs.registry.parser import describe_feature_group
from kitefs.registry.serializer import build_registry_document
from kitefs.sdk.results import FeatureGroupDescription
from kitefs.validation import validate_dataframe
from tests.fixtures.definitions import build_town_market_features

scenarios("../features/feature_6_validation.feature")

_UTC = datetime.UTC
_TS_2024 = datetime.datetime(2024, 2, 1, tzinfo=_UTC)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


@pytest.fixture
def town_market_description() -> FeatureGroupDescription:
    """Return a FeatureGroupDescription for town_market_features via serializer round-trip."""
    doc = build_registry_document(
        [build_town_market_features()],
        prior_document={},
        now=datetime.datetime.now(_UTC),
    )
    return describe_feature_group(doc, "town_market_features")


# ---------------------------------------------------------------------------
# Given — description setup
# ---------------------------------------------------------------------------


@given('"town_market_features" expects "avg_price_per_sqm" to be not_null and gt 0')
def _given_town_market_not_null_and_gt(ctx: dict[str, Any], town_market_description: FeatureGroupDescription) -> None:
    ctx["description"] = town_market_description


@given('"town_market_features" expects "avg_price_per_sqm" to be gt 0')
def _given_town_market_gt(ctx: dict[str, Any], town_market_description: FeatureGroupDescription) -> None:
    ctx["description"] = town_market_description


@given('"town_market_features" has entity key "town_id"')
def _given_town_market_entity_key(ctx: dict[str, Any], town_market_description: FeatureGroupDescription) -> None:
    ctx["description"] = town_market_description


# ---------------------------------------------------------------------------
# Given — DataFrame construction
# ---------------------------------------------------------------------------


@given("a DataFrame contains town_id 1, avg_price_per_sqm 24500.0, and event_timestamp 2024-02-01T00:00:00Z")
def _given_one_valid_row(ctx: dict[str, Any]) -> None:
    ctx["frame"] = pd.DataFrame(
        {
            "town_id": [1],
            "avg_price_per_sqm": [24500.0],
            "event_timestamp": pd.to_datetime([_TS_2024]),
        }
    )


@given("a DataFrame contains town_id 3, avg_price_per_sqm -10.0, and event_timestamp 2024-02-01T00:00:00Z")
def _given_one_invalid_row(ctx: dict[str, Any]) -> None:
    ctx["frame"] = pd.DataFrame(
        {
            "town_id": [3],
            "avg_price_per_sqm": [-10.0],
            "event_timestamp": pd.to_datetime([_TS_2024]),
        }
    )


@given("a DataFrame contains town_id 1 with avg_price_per_sqm 24500.0")
def _given_valid_row_for_filter(ctx: dict[str, Any]) -> None:
    ctx["frame_rows"] = [
        {"town_id": 1, "avg_price_per_sqm": 24500.0, "event_timestamp": _TS_2024},
    ]


@given("the DataFrame contains town_id 3 with avg_price_per_sqm -10.0")
def _given_invalid_row_for_filter(ctx: dict[str, Any]) -> None:
    ctx["frame_rows"].append({"town_id": 3, "avg_price_per_sqm": -10.0, "event_timestamp": _TS_2024})
    ctx["frame"] = pd.DataFrame(ctx["frame_rows"])


@given("a DataFrame contains a null town_id and event_timestamp 2024-02-01T00:00:00Z")
def _given_null_entity_key(ctx: dict[str, Any]) -> None:
    ctx["frame"] = pd.DataFrame(
        {
            "town_id": [None],
            "avg_price_per_sqm": [100.0],
            "event_timestamp": pd.to_datetime([_TS_2024]),
        }
    )


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("the DataFrame is validated in ERROR mode")
def _when_validate_error(ctx: dict[str, Any]) -> None:
    ctx["exception"] = None
    ctx["result"] = None
    try:
        frame, report = validate_dataframe(
            ctx["description"], ctx["frame"], ValidationMode.ERROR, operation="ingestion"
        )
        ctx["result"] = (frame, report)
    except ValidationError as exc:
        ctx["exception"] = exc


@when("the DataFrame is validated in FILTER mode")
def _when_validate_filter(ctx: dict[str, Any]) -> None:
    ctx["exception"] = None
    ctx["result"] = None
    try:
        frame, report = validate_dataframe(
            ctx["description"], ctx["frame"], ValidationMode.FILTER, operation="ingestion"
        )
        ctx["result"] = (frame, report)
    except ValidationError as exc:
        ctx["exception"] = exc


@when("the DataFrame is validated in NONE mode")
def _when_validate_none(ctx: dict[str, Any]) -> None:
    ctx["exception"] = None
    ctx["result"] = None
    try:
        frame, report = validate_dataframe(ctx["description"], ctx["frame"], ValidationMode.NONE, operation="ingestion")
        ctx["result"] = (frame, report)
    except ValidationError as exc:
        ctx["exception"] = exc


# ---------------------------------------------------------------------------
# Then — success assertions
# ---------------------------------------------------------------------------


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    assert ctx["exception"] is None, (
        f"Expected no exception but got {type(ctx['exception']).__name__}: {ctx['exception']}"
    )


@then("the validation report has pass_count 1")
def _then_pass_count_1(ctx: dict[str, Any]) -> None:
    if ctx["result"] is not None:
        _, report = ctx["result"]
    else:
        report = ctx["exception"].report
    assert report is not None, "Expected a ValidationReport but got None"
    assert report.pass_count == 1, f"Expected pass_count=1, got {report.pass_count}"


@then("the validation report has fail_count 0")
def _then_fail_count_0(ctx: dict[str, Any]) -> None:
    if ctx["result"] is not None:
        _, report = ctx["result"]
    else:
        report = ctx["exception"].report
    assert report is not None
    assert report.fail_count == 0, f"Expected fail_count=0, got {report.fail_count}"


@then("the validation report has fail_count 1")
def _then_fail_count_1(ctx: dict[str, Any]) -> None:
    if ctx["result"] is not None:
        _, report = ctx["result"]
    else:
        report = ctx["exception"].report
    assert report is not None
    assert report.fail_count == 1, f"Expected fail_count=1, got {report.fail_count}"


# ---------------------------------------------------------------------------
# Then — failure assertions
# ---------------------------------------------------------------------------


@then("ValidationError is raised")
def _then_validation_error_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exception"], ValidationError), (
        f"Expected ValidationError but got {type(ctx['exception'])}: {ctx['exception']}"
    )


@then('the error report contains one failure for field "avg_price_per_sqm"')
def _then_one_failure_for_avg_price(ctx: dict[str, Any]) -> None:
    report = ctx["exception"].report
    assert report is not None
    failures = [f for f in report.failures if f.field == "avg_price_per_sqm"]
    assert len(failures) == 1, f"Expected 1 failure for avg_price_per_sqm, got {len(failures)}: {failures}"


@then('the error report contains a failure for field "town_id"')
def _then_failure_for_town_id(ctx: dict[str, Any]) -> None:
    report = ctx["exception"].report
    assert report is not None
    failures = [f for f in report.failures if f.field == "town_id"]
    assert failures, f"Expected at least one failure for town_id, got none. All failures: {report.failures}"


# ---------------------------------------------------------------------------
# Then — FILTER mode assertions
# ---------------------------------------------------------------------------


@then("the returned DataFrame contains only town_id 1")
def _then_contains_only_town_id_1(ctx: dict[str, Any]) -> None:
    assert ctx["result"] is not None, "Expected a result tuple but got None (exception was raised)"
    frame, _ = ctx["result"]
    assert list(frame["town_id"]) == [1], f"Expected only town_id=1 in result, got: {list(frame['town_id'])}"
