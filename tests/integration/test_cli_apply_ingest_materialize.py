"""Integration tests for kitefs apply, ingest, and materialize CLI commands."""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from kitefs.cli import cli, main
from tests.helpers.dataframes import town_market_frame
from tests.helpers.tmp_store import make_initialized_project

# ---------------------------------------------------------------------------
# Reference definition sources
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
def applied_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Scaffold a project with both listing and town market features applied."""
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    return tmp_path


@pytest.fixture
def ingest_ready_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Project with town_market_features applied and a CSV file ready to ingest."""
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
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
    return tmp_path


@pytest.fixture
def materialize_ready_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Project with town_market_features applied and offline rows ingested."""
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
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
    return tmp_path


# ---------------------------------------------------------------------------
# TestCliApply
# ---------------------------------------------------------------------------


class TestCliApply:
    """kitefs apply — happy path and option behaviour."""

    def test_apply_exits_zero_and_lists_groups(self, applied_project: Path) -> None:
        """apply exits 0 and prints registered group names."""
        runner = CliRunner()
        result = runner.invoke(main, ["apply"])
        assert result.exit_code == 0, result.output
        assert "listing_features" in result.output
        assert "town_market_features" in result.output

    def test_apply_json_output(self, applied_project: Path) -> None:
        """apply --format json prints parseable JSON with registered_groups."""
        runner = CliRunner()
        result = runner.invoke(main, ["apply", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "registered_groups" in data
        assert "town_market_features" in data["registered_groups"]

    def test_apply_publish_decline_before_config_load(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Declining the publish confirmation aborts before config is loaded."""
        monkeypatch.chdir(tmp_path)  # directory has no kitefs.yaml
        runner = CliRunner()
        result = runner.invoke(main, ["apply", "--publish"], input="no\n")
        assert result.exit_code != 0
        assert "aborted" in result.output.lower()
        # Error must NOT mention missing config — it aborts before config loading.
        assert "kitefs.yaml" not in result.output.lower()

    def test_apply_publish_no_confirm_skips_prompt(
        self, applied_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--publish --no-confirm skips the confirmation prompt and calls apply(publish=True)."""
        from kitefs.sdk.results import ApplyResult

        class _FakeStore:
            def __init__(self) -> None:
                pass

            def apply(self, *, publish: bool = False) -> ApplyResult:
                return ApplyResult(registered_groups=["town_market_features"], published=publish)

        monkeypatch.setattr("kitefs.sdk.feature_store.FeatureStore", _FakeStore)
        runner = CliRunner()
        result = runner.invoke(main, ["apply", "--publish", "--no-confirm"])
        assert result.exit_code == 0, result.output
        assert "Applied" in result.output
        assert "Published to remote registry." in result.output

    def test_apply_publish_yes_calls_sdk_with_publish_true(
        self, applied_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """apply --publish with exact 'yes' confirmation calls apply(publish=True)."""
        from kitefs.sdk.results import ApplyResult

        publish_calls: list[bool] = []

        class _FakeStore:
            def __init__(self) -> None:
                pass

            def apply(self, *, publish: bool = False) -> ApplyResult:
                publish_calls.append(publish)
                return ApplyResult(registered_groups=["town_market_features"], published=publish)

        monkeypatch.setattr("kitefs.sdk.feature_store.FeatureStore", _FakeStore)
        runner = CliRunner()
        result = runner.invoke(main, ["apply", "--publish"], input="yes\n")

        assert result.exit_code == 0, result.output
        assert publish_calls == [True], f"Expected apply(publish=True), got publish_calls={publish_calls}"
        assert "Published to remote registry." in result.output

    @pytest.mark.parametrize("bad_input", ["Yes\n", "YES\n", "y\n", " yes\n"], ids=["Yes", "YES", "y", "space_yes"])
    def test_apply_publish_case_sensitive_rejection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_input: str
    ) -> None:
        """Confirmation inputs that are not exact 'yes' abort before config loading."""
        monkeypatch.chdir(tmp_path)  # no kitefs.yaml — aborts before config load
        runner = CliRunner()
        result = runner.invoke(main, ["apply", "--publish"], input=bad_input)
        assert result.exit_code != 0
        assert "aborted" in result.output.lower()
        assert "kitefs.yaml" not in result.output.lower()


# ---------------------------------------------------------------------------
# TestCliIngest
# ---------------------------------------------------------------------------


class TestCliIngest:
    """kitefs ingest — file ingestion and error handling."""

    def test_ingest_csv_exits_zero(self, ingest_ready_project: Path) -> None:
        """ingest CSV exits 0 and reports accepted rows and group name."""
        csv_path = ingest_ready_project / "data" / "town_market_2024_02.csv"
        runner = CliRunner()
        result = runner.invoke(main, ["ingest", "town_market_features", str(csv_path)])
        assert result.exit_code == 0, result.output
        assert "Ingested" in result.output
        assert "6" in result.output
        assert "town_market_features" in result.output

    def test_ingest_csv_json_output(self, ingest_ready_project: Path) -> None:
        """ingest --format json produces parseable JSON with accepted_rows."""
        csv_path = ingest_ready_project / "data" / "town_market_2024_02.csv"
        runner = CliRunner()
        result = runner.invoke(main, ["ingest", "town_market_features", str(csv_path), "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["feature_group"] == "town_market_features"
        assert data["accepted_rows"] == 6

    def test_ingest_unsupported_extension_exits_nonzero(self, ingest_ready_project: Path) -> None:
        """ingest rejects unsupported file extension before contacting the SDK."""
        runner = CliRunner()
        result = runner.invoke(main, ["ingest", "town_market_features", "data.json"])
        assert result.exit_code != 0
        # IngestionShapeError propagates as result.exception via CliRunner.
        assert result.exception is not None
        assert ".json" in str(result.exception) or "unsupported" in str(result.exception).lower()

    def test_ingest_unsupported_extension_error_before_sdk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Extension check fires before FeatureStore is constructed (no config needed)."""
        monkeypatch.chdir(tmp_path)  # empty directory without kitefs.yaml
        runner = CliRunner()
        result = runner.invoke(main, ["ingest", "town_market_features", "data.json"])
        assert result.exit_code != 0
        # Error must be about the extension, not about missing config.
        assert "kitefs.yaml" not in result.output.lower()


# ---------------------------------------------------------------------------
# TestCliMaterialize
# ---------------------------------------------------------------------------


class TestCliMaterialize:
    """kitefs materialize — online store population."""

    def test_materialize_named_group_exits_zero(self, materialize_ready_project: Path) -> None:
        """materialize <group> exits 0 and mentions the group name."""
        runner = CliRunner()
        result = runner.invoke(main, ["materialize", "town_market_features"])
        assert result.exit_code == 0, result.output
        assert "town_market_features" in result.output
        assert "Succeeded" in result.output

    def test_materialize_all_groups_exits_zero(self, materialize_ready_project: Path) -> None:
        """materialize with no argument processes all groups."""
        runner = CliRunner()
        result = runner.invoke(main, ["materialize"])
        assert result.exit_code == 0, result.output
        assert "Succeeded" in result.output

    def test_materialize_json_output(self, materialize_ready_project: Path) -> None:
        """materialize --format json produces parseable JSON with succeeded list."""
        runner = CliRunner()
        result = runner.invoke(main, ["materialize", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "succeeded" in data
        assert "town_market_features" in data["succeeded"]

    def test_materialize_failed_exits_one(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """materialize exits 1 and prints summary when result.failed is non-empty."""
        make_initialized_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        from kitefs.sdk.results import FailedGroup, MaterializeResult

        failed_result = MaterializeResult(
            succeeded=[],
            skipped=[],
            failed=[FailedGroup(name="town_market_features", error_message="write failed")],
        )

        class _FakeStore:
            def __init__(self) -> None:
                pass

            def materialize(self, group_name: str | None = None) -> MaterializeResult:
                return failed_result

        monkeypatch.setattr("kitefs.sdk.feature_store.FeatureStore", _FakeStore)
        runner = CliRunner()
        result = runner.invoke(main, ["materialize"])
        assert result.exit_code == 1
        # Summary must still be printed before exiting.
        assert "town_market_features" in result.output
        assert "write failed" in result.output


# ---------------------------------------------------------------------------
# TestCliExpectedErrorBoundary
# ---------------------------------------------------------------------------


class TestCliExpectedErrorBoundary:
    """apply in a project with no definitions hits the KiteFSError boundary."""

    def test_apply_no_definitions_exits_1_no_traceback(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """apply with no definitions exits 1, prints Error: on stderr, no Traceback."""
        make_initialized_project(tmp_path)
        # make_initialized_project writes a sample definition; remove it so apply
        # finds no groups and raises DefinitionDiscoveryError.
        (tmp_path / "feature_store" / "definitions" / "town_market_features.py").unlink(missing_ok=True)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["kitefs", "apply"])

        with pytest.raises(SystemExit) as ei:
            cli()

        assert ei.value.code == 1
        out, err = capsys.readouterr()
        assert out == ""
        assert "Error:" in err
        assert "FeatureGroup" in err
        assert "Traceback" not in err
