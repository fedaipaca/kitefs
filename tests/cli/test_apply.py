"""Tests for the ``kitefs apply`` CLI command."""

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from kitefs.cli import cli
from kitefs.exceptions import ProviderError
from tests.helpers import LISTING_DEF, MINIMAL_DEF, TOWN_DEF, setup_project


def _runner() -> CliRunner:
    """Create a Click test runner with isolated filesystem disabled (we use tmp_path)."""
    return CliRunner()


# A concrete definition for CLI tests.
_SIMPLE_DEF = MINIMAL_DEF.format(varname="listing_features", name="listing_features")


class TestApplyHelp:
    """``kitefs apply --help`` advertises no custom options or arguments."""

    def test_help_exits_zero(self) -> None:
        """apply --help exits with code 0."""
        result = _runner().invoke(cli, ["apply", "--help"])

        assert result.exit_code == 0

    def test_no_custom_options(self) -> None:
        """apply --help shows only the built-in --help option."""
        result = _runner().invoke(cli, ["apply", "--help"])

        lines = result.output.strip().splitlines()
        option_lines = [line.strip() for line in lines if line.strip().startswith("--")]
        assert all("--help" in line for line in option_lines)


class TestApplySuccess:
    """Successful ``kitefs apply`` exits 0 and prints a summary."""

    def test_exit_code_is_zero(self, tmp_path: Path) -> None:
        """Successful apply exits with code 0."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": _SIMPLE_DEF})
            result = runner.invoke(cli, ["apply"], catch_exceptions=False)

        assert result.exit_code == 0

    def test_prints_summary(self, tmp_path: Path) -> None:
        """Apply prints the number of registered groups in its summary."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": _SIMPLE_DEF})
            result = runner.invoke(cli, ["apply"], catch_exceptions=False)

        assert "1" in result.output
        assert "registered" in result.output.lower() or "applied" in result.output.lower()

    def test_registry_json_updated(self, tmp_path: Path) -> None:
        """Apply writes the registered group to registry.json on disk."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"listing.py": _SIMPLE_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)

            registry = json.loads((td_path / "feature_store" / "registry.json").read_text(encoding="utf-8"))

        assert "listing_features" in registry["feature_groups"]

    def test_multiple_groups_summary(self, tmp_path: Path) -> None:
        """Applying two groups prints count '2' in the summary."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(
                Path(td),
                {"listing.py": LISTING_DEF, "town.py": TOWN_DEF},
            )
            result = runner.invoke(cli, ["apply"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "2" in result.output


class TestApplyOutsideProject:
    """``kitefs apply`` outside a KiteFS project fails with exit 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Apply outside a project exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1

    def test_error_message_suggests_init(self, tmp_path: Path) -> None:
        """Apply outside a project suggests running kitefs init."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["apply"])

        assert "kitefs init" in result.output or "kitefs init" in (result.stderr or "")

    def test_error_goes_to_stderr(self, tmp_path: Path) -> None:
        """Error output is written to stderr, not stdout."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1
        assert "No KiteFS project found" in result.stderr

    def test_no_traceback(self, tmp_path: Path) -> None:
        """Apply outside a project does not show a traceback."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["apply"])

        assert "Traceback" not in result.output


class TestApplyInvalidDefinitions:
    """``kitefs apply`` with broken definitions exits 1 with errors to stderr."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Apply with broken definitions exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"broken.py": "import nonexistent_module_xyz\n"})
            result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1

    def test_error_message_contains_filename(self, tmp_path: Path) -> None:
        """Error includes the broken definition filename for debugging."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"broken.py": "import nonexistent_module_xyz\n"})
            result = runner.invoke(cli, ["apply"])

        combined = result.output + (result.stderr or "")
        assert "broken.py" in combined

    def test_no_traceback(self, tmp_path: Path) -> None:
        """Apply with broken definitions does not show a traceback."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"broken.py": "import nonexistent_module_xyz\n"})
            result = runner.invoke(cli, ["apply"])

        assert "Traceback" not in result.output


class TestApplyNoDefinitions:
    """``kitefs apply`` with no definition files exits 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Apply with no definition files exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td))
            result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1

    def test_error_message_is_actionable(self, tmp_path: Path) -> None:
        """Error tells the user no definitions were found."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td))
            result = runner.invoke(cli, ["apply"])

        combined = result.output + (result.stderr or "")
        assert "No feature group definitions found" in combined


class TestApplyProviderError:
    """``kitefs apply`` handles ProviderError with exit 1."""

    def test_provider_error_exits_one(self, tmp_path: Path) -> None:
        """ProviderError during apply exits 1 with the error message."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": _SIMPLE_DEF})

            with patch(
                "kitefs.feature_store.FeatureStore.apply",
                side_effect=ProviderError("Disk full"),
            ):
                result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1
        combined = result.output + (result.stderr or "")
        assert "Disk full" in combined
