"""Tests for the ``kitefs list`` CLI command."""

import json
from pathlib import Path

from click.testing import CliRunner

from kitefs.cli import cli
from tests.helpers import LISTING_DEF, MINIMAL_DEF, TOWN_DEF, setup_project


def _runner() -> CliRunner:
    """Create a Click test runner with isolated filesystem disabled (we use tmp_path)."""
    return CliRunner()


# ---------------------------------------------------------------------------
# kitefs list --help
# ---------------------------------------------------------------------------


class TestListHelp:
    """``kitefs list --help`` shows the format and target options."""

    def test_help_exits_zero(self) -> None:
        """list --help exits with code 0."""
        result = _runner().invoke(cli, ["list", "--help"])

        assert result.exit_code == 0

    def test_shows_format_option(self) -> None:
        """list --help shows the --format option."""
        result = _runner().invoke(cli, ["list", "--help"])

        assert "--format" in result.output

    def test_shows_target_option(self) -> None:
        """list --help shows the --target option."""
        result = _runner().invoke(cli, ["list", "--help"])

        assert "--target" in result.output


# ---------------------------------------------------------------------------
# kitefs list — success paths
# ---------------------------------------------------------------------------


class TestListSuccess:
    """Successful ``kitefs list`` renders feature group summaries."""

    def test_exit_code_is_zero(self, tmp_path: Path) -> None:
        """Successful list exits with code 0."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert result.exit_code == 0

    def test_output_contains_group_names(self, tmp_path: Path) -> None:
        """List output includes the names of all registered feature groups."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert "listing_features" in result.output
        assert "town_market_features" in result.output

    def test_output_contains_summary_values(self, tmp_path: Path) -> None:
        """List output includes owner and entity key summary values."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert "data-science-team" in result.output
        assert "listing_id" in result.output

    def test_empty_registry_prints_informational_message(self, tmp_path: Path) -> None:
        """An empty registry prints an informational message, not an error."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td))
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "No feature groups registered" in result.output

    def test_json_format_prints_json_to_stdout(self, tmp_path: Path) -> None:
        """list --format json prints parseable JSON array to stdout."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list", "--format", "json"], catch_exceptions=False)

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_target_writes_file_and_confirms_path(self, tmp_path: Path) -> None:
        """list --target writes JSON to a file and confirms the path."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            output_file = td_path / "list_output.json"
            result = runner.invoke(cli, ["list", "--target", str(output_file)], catch_exceptions=False)

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert "Output written to" in result.output


# ---------------------------------------------------------------------------
# kitefs list — error paths
# ---------------------------------------------------------------------------


class TestListOutsideProject:
    """``kitefs list`` outside a KiteFS project fails with exit 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """List outside a project exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 1

    def test_error_message_suggests_init(self, tmp_path: Path) -> None:
        """List outside a project suggests running kitefs init."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["list"])

        combined = result.output + (result.stderr or "")
        assert "kitefs init" in combined


# ---------------------------------------------------------------------------
# kitefs list — None owner renders cleanly (no literal "None" in output)
# ---------------------------------------------------------------------------


class TestListOwnerNoneRenders:
    """A feature group with no owner shows an empty cell, not the string 'None'."""

    def test_none_owner_does_not_appear_as_string(self, tmp_path: Path) -> None:
        """A None owner renders as an empty cell, not the literal string 'None'."""
        minimal = MINIMAL_DEF.format(varname="no_owner_group", name="no_owner_group")
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"minimal.py": minimal})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "None" not in result.output

    def test_none_owner_json_format_contains_null(self, tmp_path: Path) -> None:
        """JSON output serializes None owner as JSON null."""
        minimal = MINIMAL_DEF.format(varname="no_owner_group", name="no_owner_group")
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"minimal.py": minimal})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list", "--format", "json"], catch_exceptions=False)

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["owner"] is None
