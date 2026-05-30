"""Integration tests for kitefs list and kitefs describe CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from kitefs.cli import main
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


@pytest.fixture
def applied_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Scaffold a project with town_market_features applied."""
    make_initialized_project(tmp_path)
    (tmp_path / "feature_store" / "definitions" / "town_market_features.py").write_text(
        _TOWN_MARKET_SRC, encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    from kitefs.sdk.feature_store import FeatureStore

    FeatureStore().apply()
    return tmp_path


class TestListOutputFile:
    """--output PATH writes the rendered content to a file instead of stdout."""

    def test_output_file_is_written(self, applied_project: Path) -> None:
        """--output PATH creates the file with rendered content."""
        out_file = applied_project / "out.txt"
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--output", str(out_file)])

        assert result.exit_code == 0, result.output
        assert out_file.exists()
        assert "town_market_features" in out_file.read_text(encoding="utf-8")

    def test_stdout_is_empty_when_output_file_used(self, applied_project: Path) -> None:
        """When --output is set, stdout receives no content."""
        out_file = applied_project / "out.txt"
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--output", str(out_file)])

        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_output_file_json(self, applied_project: Path) -> None:
        """--output PATH with --format json writes valid JSON to the file."""
        out_file = applied_project / "out.json"
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--format", "json", "--output", str(out_file)])

        assert result.exit_code == 0
        content = out_file.read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, list)
        assert parsed[0]["name"] == "town_market_features"


class TestListJsonFormat:
    """kitefs list --format json round-trips through json.loads."""

    def test_json_is_valid_array(self, applied_project: Path) -> None:
        """--format json produces a valid JSON array on stdout."""
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--format", "json"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)

    def test_json_contains_group(self, applied_project: Path) -> None:
        """JSON array contains the applied feature group."""
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--format", "json"])

        parsed = json.loads(result.output)
        names = [g["name"] for g in parsed]
        assert "town_market_features" in names

    def test_invalid_format_rejected_by_click(self, applied_project: Path) -> None:
        """--format with an invalid value is rejected before any SDK work (exit 2)."""
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--format", "yaml"])
        assert result.exit_code == 2


class TestDescribeOutputFile:
    """kitefs describe --output PATH writes to file instead of stdout."""

    def test_output_file_is_written(self, applied_project: Path) -> None:
        """--output PATH creates the file with rendered content."""
        out_file = applied_project / "desc.txt"
        runner = CliRunner()
        result = runner.invoke(main, ["describe", "town_market_features", "--output", str(out_file)])

        assert result.exit_code == 0
        assert out_file.exists()
        assert "town_market_features" in out_file.read_text(encoding="utf-8")

    def test_json_output_file_round_trips(self, applied_project: Path) -> None:
        """--format json --output PATH writes a parseable JSON object."""
        out_file = applied_project / "desc.json"
        runner = CliRunner()
        result = runner.invoke(
            main, ["describe", "town_market_features", "--format", "json", "--output", str(out_file)]
        )

        assert result.exit_code == 0
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert data["name"] == "town_market_features"
        assert data["entity_key"]["name"] == "town_id"


class TestOutputWriteFailure:
    """--output PATH write failures produce a user-facing error, not a traceback."""

    def test_list_output_unwritable_path_exits_nonzero(self, applied_project: Path) -> None:
        """list --output into a missing parent directory exits non-zero with actionable message."""
        out_file = applied_project / "no_such_dir" / "out.txt"
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--output", str(out_file)])

        assert result.exit_code != 0
        assert "Could not write output to" in result.output

    def test_describe_output_unwritable_path_exits_nonzero(self, applied_project: Path) -> None:
        """describe --output into a missing parent directory exits non-zero with actionable message."""
        out_file = applied_project / "no_such_dir" / "desc.txt"
        runner = CliRunner()
        result = runner.invoke(main, ["describe", "town_market_features", "--output", str(out_file)])

        assert result.exit_code != 0
        assert "Could not write output to" in result.output


class TestImportIsolation:
    """kitefs.cli must not eagerly import SDK or registry modules."""

    def test_list_describe_not_imported_at_cli_import(self) -> None:
        """Importing kitefs.cli must not pull in kitefs.sdk or kitefs.registry."""
        import subprocess
        import sys

        script = "import kitefs.cli, sys; mods = sorted(k for k in sys.modules if k.startswith('kitefs')); print(mods)"
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        imported = result.stdout.strip()
        for forbidden in ["kitefs.sdk", "kitefs.registry", "kitefs.config", "kitefs.providers"]:
            assert forbidden not in imported, f"Forbidden module eagerly imported: {forbidden}"
