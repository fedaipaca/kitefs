"""Tests for the ``kitefs describe`` CLI command."""

import json
from pathlib import Path

from click.testing import CliRunner

from kitefs.cli import cli
from tests.helpers import LISTING_DEF, TOWN_DEF, setup_project


def _runner() -> CliRunner:
    """Create a Click test runner with isolated filesystem disabled (we use tmp_path)."""
    return CliRunner()


class TestDescribeHelp:
    """``kitefs describe --help`` shows the name argument and options."""

    def test_help_exits_zero(self) -> None:
        """describe --help exits with code 0."""
        result = _runner().invoke(cli, ["describe", "--help"])

        assert result.exit_code == 0

    def test_shows_name_argument(self) -> None:
        """describe --help shows the feature group name argument."""
        result = _runner().invoke(cli, ["describe", "--help"])

        assert "feature_group_name" in result.output.lower() or "name" in result.output.lower()

    def test_shows_format_option(self) -> None:
        """describe --help shows the --format option."""
        result = _runner().invoke(cli, ["describe", "--help"])

        assert "--format" in result.output

    def test_shows_target_option(self) -> None:
        """describe --help shows the --target option."""
        result = _runner().invoke(cli, ["describe", "--help"])

        assert "--target" in result.output


class TestDescribeSuccess:
    """Successful ``kitefs describe`` renders the full feature group definition."""

    def test_exit_code_is_zero(self, tmp_path: Path) -> None:
        """Successful describe exits with code 0."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert result.exit_code == 0

    def test_output_contains_group_name(self, tmp_path: Path) -> None:
        """Describe output includes the feature group name."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert "listing_features" in result.output

    def test_output_contains_structural_fields(self, tmp_path: Path) -> None:
        """Describe output shows entity key, event timestamp, and storage target."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert "listing_id" in result.output
        assert "event_timestamp" in result.output
        assert "OFFLINE" in result.output

    def test_output_contains_features(self, tmp_path: Path) -> None:
        """Describe output lists the feature names."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert "net_area" in result.output
        assert "sold_price" in result.output

    def test_output_contains_validation_modes(self, tmp_path: Path) -> None:
        """Describe output shows the ingestion validation mode."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert "ERROR" in result.output

    def test_json_format_prints_json_to_stdout(self, tmp_path: Path) -> None:
        """describe --format json prints parseable JSON to stdout."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features", "--format", "json"], catch_exceptions=False)

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["name"] == "listing_features"

    def test_target_writes_file_and_confirms_path(self, tmp_path: Path) -> None:
        """describe --target writes JSON to a file and confirms the path."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            output_file = td_path / "describe_output.json"
            result = runner.invoke(
                cli, ["describe", "listing_features", "--target", str(output_file)], catch_exceptions=False
            )

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert data["name"] == "listing_features"
        assert "Output written to" in result.output


class TestDescribeOutsideProject:
    """``kitefs describe`` outside a KiteFS project fails with exit 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Describe outside a project exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["describe", "anything"])

        assert result.exit_code == 1

    def test_error_message_suggests_init(self, tmp_path: Path) -> None:
        """Describe outside a project suggests running kitefs init."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["describe", "anything"])

        combined = result.output + (result.stderr or "")
        assert "kitefs init" in combined


class TestDescribeUnknownGroup:
    """``kitefs describe`` with unknown group name exits 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Describing a non-existent group exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "missing_group"])

        assert result.exit_code == 1

    def test_error_message_includes_group_name(self, tmp_path: Path) -> None:
        """Error includes the requested group name for debugging."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "missing_group"])

        combined = result.output + (result.stderr or "")
        assert "missing_group" in combined

    def test_error_suggests_kitefs_list(self, tmp_path: Path) -> None:
        """Error suggests running kitefs list to see available groups."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "missing_group"])

        combined = result.output + (result.stderr or "")
        assert "kitefs list" in combined

    def test_no_traceback(self, tmp_path: Path) -> None:
        """Describe error does not show a traceback."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "missing_group"])

        assert "Traceback" not in result.output


class TestDescribeJoinKeysShown:
    """``kitefs describe`` renders the join keys section when present."""

    def test_join_key_field_and_target_group_shown(self, tmp_path: Path) -> None:
        """Describe shows join key field name and referenced group."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "town_id" in result.output
        assert "town_market_features" in result.output

    def test_no_join_keys_section_absent_for_group_without_joins(self, tmp_path: Path) -> None:
        """Describe omits the Join Keys section when the group has no join keys."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "town_market_features"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "Join Keys" not in result.output
