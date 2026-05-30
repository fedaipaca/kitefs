"""Unit tests for kitefs.cli.render — CLI presentation helpers."""

from __future__ import annotations

import datetime
import json

from kitefs.cli.render import render_apply, render_describe, render_ingest, render_list, render_materialize
from kitefs.enums import FeatureType, StorageTarget, ValidationMode
from kitefs.sdk.results import (
    ApplyResult,
    FailedGroup,
    FeatureGroupDescription,
    FeatureGroupSummary,
    FieldSpec,
    IngestResult,
    MaterializeResult,
    MetadataSpec,
    SkippedGroup,
    ValidationFailure,
    ValidationReport,
)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_NOW = datetime.datetime(2026, 5, 29, 12, 0, 0, tzinfo=datetime.UTC)
_NOW_STR = "2026-05-29T12:00:00.000000Z"


def _make_summary(name: str, **kw) -> FeatureGroupSummary:
    defaults = dict(
        owner="data-science-team",
        description=None,
        entity_key="town_id",
        storage_target=StorageTarget.OFFLINE_AND_ONLINE,
        feature_count=1,
    )
    return FeatureGroupSummary(name=name, **{**defaults, **kw})


def _make_description() -> FeatureGroupDescription:
    return FeatureGroupDescription(
        name="town_market_features",
        storage_target=StorageTarget.OFFLINE_AND_ONLINE,
        entity_key=FieldSpec(name="town_id", dtype=FeatureType.INTEGER, description=None, expect=None),
        event_timestamp=FieldSpec(name="event_timestamp", dtype=FeatureType.DATETIME, description=None, expect=None),
        features=[
            FieldSpec(
                name="avg_price_per_sqm",
                dtype=FeatureType.FLOAT,
                description=None,
                expect=[{"type": "not_null"}, {"type": "gt", "value": 0}],
            )
        ],
        join_keys=[],
        ingestion_validation=ValidationMode.ERROR,
        offline_retrieval_validation=ValidationMode.NONE,
        metadata=MetadataSpec(
            description="Town-level market stats",
            owner="data-science-team",
            tags={},
        ),
        applied_at=_NOW,
        last_materialized_at=None,
    )


# ---------------------------------------------------------------------------
# render_list — text
# ---------------------------------------------------------------------------


class TestRenderListText:
    """render_list(..., as_json=False) produces a human-readable table."""

    def test_empty_returns_sentinel(self) -> None:
        """Empty summaries list returns the 'No feature groups registered.' sentinel."""
        result = render_list([], as_json=False)
        assert result == "No feature groups registered."

    def test_header_row_present(self) -> None:
        """Output contains column headers."""
        result = render_list([_make_summary("town_market_features")], as_json=False)
        assert "NAME" in result
        assert "OWNER" in result
        assert "STORAGE TARGET" in result
        assert "FEATURES" in result

    def test_name_and_storage_target_in_output(self) -> None:
        """Group name and storage target appear in the rendered text."""
        result = render_list(
            [_make_summary("town_market_features", storage_target=StorageTarget.OFFLINE_AND_ONLINE)],
            as_json=False,
        )
        assert "town_market_features" in result
        assert "OFFLINE_AND_ONLINE" in result

    def test_multiple_rows(self) -> None:
        """Multiple groups each appear as a row."""
        summaries = [
            _make_summary("listing_features", storage_target=StorageTarget.OFFLINE, entity_key="listing_id"),
            _make_summary("town_market_features"),
        ]
        result = render_list(summaries, as_json=False)
        assert "listing_features" in result
        assert "town_market_features" in result


# ---------------------------------------------------------------------------
# render_list — json
# ---------------------------------------------------------------------------


class TestRenderListJson:
    """render_list(..., as_json=True) produces a valid JSON array."""

    def test_empty_returns_empty_array_string(self) -> None:
        """Empty summaries list returns '[]'."""
        assert render_list([], as_json=True) == "[]"

    def test_valid_json(self) -> None:
        """Output is parseable JSON."""
        result = render_list([_make_summary("town_market_features")], as_json=True)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_json_fields(self) -> None:
        """Each JSON object contains the contract fields."""
        result = render_list([_make_summary("town_market_features")], as_json=True)
        obj = json.loads(result)[0]
        assert obj["name"] == "town_market_features"
        assert obj["owner"] == "data-science-team"
        assert obj["entity_key"] == "town_id"
        assert obj["storage_target"] == "OFFLINE_AND_ONLINE"
        assert obj["feature_count"] == 1

    def test_storage_target_is_string_value(self) -> None:
        """storage_target is serialized as the enum string value, not the enum repr."""
        result = render_list([_make_summary("x", storage_target=StorageTarget.OFFLINE)], as_json=True)
        obj = json.loads(result)[0]
        assert obj["storage_target"] == "OFFLINE"


# ---------------------------------------------------------------------------
# render_describe — text
# ---------------------------------------------------------------------------


class TestRenderDescribeText:
    """render_describe(..., as_json=False) produces a human-readable description block."""

    def test_name_present(self) -> None:
        """Group name appears in text output."""
        result = render_describe(_make_description(), as_json=False)
        assert "town_market_features" in result

    def test_storage_target_present(self) -> None:
        """Storage target appears in text output."""
        result = render_describe(_make_description(), as_json=False)
        assert "OFFLINE_AND_ONLINE" in result

    def test_entity_key_present(self) -> None:
        """Entity key name appears in text output."""
        result = render_describe(_make_description(), as_json=False)
        assert "town_id" in result

    def test_feature_name_present(self) -> None:
        """Feature name appears in text output."""
        result = render_describe(_make_description(), as_json=False)
        assert "avg_price_per_sqm" in result

    def test_expect_constraints_present(self) -> None:
        """Constraint names appear in text output."""
        result = render_describe(_make_description(), as_json=False)
        assert "not_null" in result


# ---------------------------------------------------------------------------
# render_describe — json
# ---------------------------------------------------------------------------


class TestRenderDescribeJson:
    """render_describe(..., as_json=True) produces a JSON object matching the registry entry shape."""

    def test_valid_json(self) -> None:
        """Output is parseable JSON."""
        result = render_describe(_make_description(), as_json=True)
        assert isinstance(json.loads(result), dict)

    def test_entity_key_name(self) -> None:
        """entity_key.name in JSON is 'town_id'."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert data["entity_key"]["name"] == "town_id"

    def test_storage_target_value(self) -> None:
        """storage_target in JSON is the enum string value."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert data["storage_target"] == "OFFLINE_AND_ONLINE"

    def test_feature_name_present(self) -> None:
        """features array contains avg_price_per_sqm."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        feature_names = [f["name"] for f in data["features"]]
        assert "avg_price_per_sqm" in feature_names

    def test_entity_key_has_no_expect_key(self) -> None:
        """entity_key dict in JSON omits the 'expect' key (matches registry entry shape)."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert "expect" not in data["entity_key"]

    def test_event_timestamp_has_no_expect_key(self) -> None:
        """event_timestamp dict in JSON omits the 'expect' key."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert "expect" not in data["event_timestamp"]

    def test_feature_expect_in_json(self) -> None:
        """Feature constraints are present in the features array."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        f = data["features"][0]
        assert f["expect"] == [{"type": "not_null"}, {"type": "gt", "value": 0}]

    def test_applied_at_formatted_as_string(self) -> None:
        """applied_at datetime is re-serialized to an ISO string."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert data["applied_at"] == _NOW_STR

    def test_last_materialized_at_none(self) -> None:
        """last_materialized_at=None renders as JSON null."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert data["last_materialized_at"] is None


# ---------------------------------------------------------------------------
# Helpers for new result types
# ---------------------------------------------------------------------------


def _make_apply_result(registered_groups: list[str] | None = None, published: bool = False) -> ApplyResult:
    return ApplyResult(
        registered_groups=(
            registered_groups if registered_groups is not None else ["listing_features", "town_market_features"]
        ),
        published=published,
    )


def _make_ingest_result(
    accepted: int = 6, rejected: int = 0, files: int = 1, with_report: bool = False
) -> IngestResult:
    report = None
    if with_report:
        report = ValidationReport(
            pass_count=accepted,
            fail_count=rejected,
            failures=[
                ValidationFailure(
                    field="avg_price_per_sqm",
                    constraint="not_null",
                    actual_value=None,
                    entity_key_value=1,
                    row_index=0,
                )
            ]
            if rejected > 0
            else [],
        )
    return IngestResult(
        feature_group="town_market_features",
        accepted_rows=accepted,
        rejected_rows=rejected,
        written_files=[f"/tmp/store/year=2024/month=02/ing_{i}.parquet" for i in range(files)],
        validation_report=report,
    )


def _make_materialize_result(
    succeeded: list[str] | None = None,
    skipped: list[SkippedGroup] | None = None,
    failed: list[FailedGroup] | None = None,
) -> MaterializeResult:
    return MaterializeResult(
        succeeded=succeeded if succeeded is not None else [],
        skipped=skipped if skipped is not None else [],
        failed=failed if failed is not None else [],
    )


# ---------------------------------------------------------------------------
# render_apply — text
# ---------------------------------------------------------------------------


class TestRenderApplyText:
    """render_apply(..., as_json=False) produces human-readable text."""

    def test_contains_group_names(self) -> None:
        """Group names appear in the output."""
        result = render_apply(_make_apply_result(), as_json=False)
        assert "listing_features" in result
        assert "town_market_features" in result

    def test_text_format(self) -> None:
        """Output starts with 'Applied feature groups:'."""
        result = render_apply(_make_apply_result(["town_market_features"]), as_json=False)
        assert result.startswith("Applied feature groups:")
        assert "town_market_features" in result

    def test_empty_groups_uses_none_sentinel(self) -> None:
        """Empty registered_groups renders as '(none)'."""
        result = render_apply(_make_apply_result([]), as_json=False)
        assert "(none)" in result

    def test_published_true_appends_published_line(self) -> None:
        """published=True appends 'Published to remote registry.' on a new line."""
        result = render_apply(_make_apply_result(published=True), as_json=False)
        assert "Published to remote registry." in result

    def test_published_false_omits_published_line(self) -> None:
        """published=False does not include the published confirmation line."""
        result = render_apply(_make_apply_result(published=False), as_json=False)
        assert "Published to remote registry." not in result


# ---------------------------------------------------------------------------
# render_apply — json
# ---------------------------------------------------------------------------


class TestRenderApplyJson:
    """render_apply(..., as_json=True) produces a valid JSON object."""

    def test_valid_json(self) -> None:
        """Output is parseable JSON."""
        result = render_apply(_make_apply_result(), as_json=True)
        assert isinstance(json.loads(result), dict)

    def test_registered_groups_field(self) -> None:
        """JSON contains registered_groups as a list."""
        data = json.loads(render_apply(_make_apply_result(), as_json=True))
        assert data["registered_groups"] == ["listing_features", "town_market_features"]

    def test_published_field(self) -> None:
        """JSON contains published as a bool."""
        data = json.loads(render_apply(_make_apply_result(published=True), as_json=True))
        assert data["published"] is True


# ---------------------------------------------------------------------------
# render_ingest — text
# ---------------------------------------------------------------------------


class TestRenderIngestText:
    """render_ingest(..., as_json=False) produces human-readable text."""

    def test_contains_accepted_rows(self) -> None:
        """Accepted row count appears in output."""
        result = render_ingest(_make_ingest_result(accepted=6), as_json=False)
        assert "6" in result

    def test_contains_feature_group_name(self) -> None:
        """Feature group name appears in output."""
        result = render_ingest(_make_ingest_result(), as_json=False)
        assert "town_market_features" in result

    def test_contains_ingested_prefix(self) -> None:
        """Output contains the 'Ingested' prefix."""
        result = render_ingest(_make_ingest_result(), as_json=False)
        assert result.startswith("Ingested")

    def test_contains_written_files_count(self) -> None:
        """Written file count appears in output."""
        result = render_ingest(_make_ingest_result(files=3), as_json=False)
        assert "3" in result

    def test_contains_rejected_rows(self) -> None:
        """Rejected row count appears in output."""
        result = render_ingest(_make_ingest_result(rejected=2), as_json=False)
        assert "Rejected 2" in result

    def test_validation_summary_present_when_report_set(self) -> None:
        """A non-None validation_report appends a Validation: summary line."""
        result = render_ingest(_make_ingest_result(accepted=5, rejected=1, with_report=True), as_json=False)
        assert "Validation:" in result
        assert "passed" in result
        assert "failed" in result

    def test_validation_summary_absent_when_report_none(self) -> None:
        """A None validation_report (NONE mode) omits the Validation: line."""
        result = render_ingest(_make_ingest_result(), as_json=False)
        assert "Validation:" not in result


# ---------------------------------------------------------------------------
# render_ingest — json
# ---------------------------------------------------------------------------


class TestRenderIngestJson:
    """render_ingest(..., as_json=True) produces a valid JSON object."""

    def test_valid_json(self) -> None:
        """Output is parseable JSON."""
        assert isinstance(json.loads(render_ingest(_make_ingest_result(), as_json=True)), dict)

    def test_accepted_rows_field(self) -> None:
        """JSON contains accepted_rows."""
        data = json.loads(render_ingest(_make_ingest_result(accepted=6), as_json=True))
        assert data["accepted_rows"] == 6

    def test_rejected_rows_field(self) -> None:
        """JSON contains rejected_rows."""
        data = json.loads(render_ingest(_make_ingest_result(rejected=2), as_json=True))
        assert data["rejected_rows"] == 2

    def test_feature_group_field(self) -> None:
        """JSON contains feature_group name."""
        data = json.loads(render_ingest(_make_ingest_result(), as_json=True))
        assert data["feature_group"] == "town_market_features"

    def test_written_files_field(self) -> None:
        """JSON contains written_files as a list."""
        data = json.loads(render_ingest(_make_ingest_result(files=2), as_json=True))
        assert isinstance(data["written_files"], list)
        assert len(data["written_files"]) == 2

    def test_validation_report_null_when_absent(self) -> None:
        """validation_report is null when IngestResult has no report."""
        data = json.loads(render_ingest(_make_ingest_result(), as_json=True))
        assert data["validation_report"] is None

    def test_validation_report_present_when_set(self) -> None:
        """validation_report serializes pass_count, fail_count, failures."""
        data = json.loads(render_ingest(_make_ingest_result(accepted=5, rejected=1, with_report=True), as_json=True))
        rpt = data["validation_report"]
        assert rpt is not None
        assert "pass_count" in rpt
        assert "fail_count" in rpt
        assert isinstance(rpt["failures"], list)


# ---------------------------------------------------------------------------
# render_materialize — text
# ---------------------------------------------------------------------------


class TestRenderMaterializeText:
    """render_materialize(..., as_json=False) produces human-readable text."""

    def test_success_text(self) -> None:
        """Succeeded groups appear in output."""
        result = render_materialize(_make_materialize_result(succeeded=["town_market_features"]), as_json=False)
        assert "Succeeded" in result
        assert "town_market_features" in result

    def test_all_sections_present(self) -> None:
        """Succeeded, Skipped, and Failed sections always appear."""
        result = render_materialize(_make_materialize_result(succeeded=["g"]), as_json=False)
        assert "Succeeded:" in result
        assert "Skipped:" in result
        assert "Failed:" in result

    def test_empty_sections_use_none_sentinel(self) -> None:
        """Empty sections render as '(none)'."""
        result = render_materialize(_make_materialize_result(succeeded=["g"]), as_json=False)
        assert "(none)" in result

    def test_skipped_with_reason(self) -> None:
        """Skipped group name and reason appear in output."""
        result = render_materialize(
            _make_materialize_result(skipped=[SkippedGroup(name="g", reason="no offline data")]),
            as_json=False,
        )
        assert "g" in result
        assert "no offline data" in result

    def test_failed_with_error_message(self) -> None:
        """Failed group name and error message appear in output."""
        result = render_materialize(
            _make_materialize_result(failed=[FailedGroup(name="g", error_message="write failed")]),
            as_json=False,
        )
        assert "g" in result
        assert "write failed" in result


# ---------------------------------------------------------------------------
# render_materialize — json
# ---------------------------------------------------------------------------


class TestRenderMaterializeJson:
    """render_materialize(..., as_json=True) produces a valid JSON object."""

    def test_valid_json(self) -> None:
        """Output is parseable JSON."""
        assert isinstance(json.loads(render_materialize(_make_materialize_result(), as_json=True)), dict)

    def test_succeeded_field(self) -> None:
        """JSON contains succeeded as a string list."""
        data = json.loads(
            render_materialize(_make_materialize_result(succeeded=["town_market_features"]), as_json=True)
        )
        assert data["succeeded"] == ["town_market_features"]

    def test_skipped_field(self) -> None:
        """JSON contains skipped as a list of {name, reason} objects."""
        data = json.loads(
            render_materialize(
                _make_materialize_result(skipped=[SkippedGroup(name="g", reason="no offline data")]),
                as_json=True,
            )
        )
        assert data["skipped"] == [{"name": "g", "reason": "no offline data"}]

    def test_failed_field(self) -> None:
        """JSON contains failed as a list of {name, error_message} objects."""
        data = json.loads(
            render_materialize(
                _make_materialize_result(failed=[FailedGroup(name="g", error_message="boom")]),
                as_json=True,
            )
        )
        assert data["failed"] == [{"name": "g", "error_message": "boom"}]

    def test_empty_result(self) -> None:
        """All-empty result serializes with empty lists for all three fields."""
        data = json.loads(render_materialize(_make_materialize_result(), as_json=True))
        assert data == {"succeeded": [], "skipped": [], "failed": []}
