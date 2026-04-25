"""End-to-end tests for error workflows — validation errors, empty registries, missing groups."""

import json
import os
from pathlib import Path

from click.testing import CliRunner

from kitefs.cli import cli
from tests.helpers import LISTING_DEF, TOWN_DEF


class TestErrorWorkflows:
    """Error accumulation and user-facing error quality across the full stack."""

    def test_multiple_validation_errors_all_reported_via_cli(self, tmp_path: Path) -> None:
        """Multiple broken definitions produce ALL errors in stderr, not just the first."""
        runner = CliRunner()
        runner.invoke(cli, ["init", str(tmp_path)])
        defs_dir = tmp_path / "feature_store" / "definitions"

        # Write two broken definition files
        (defs_dir / "broken_one.py").write_text("import nonexistent_package_abc\n", encoding="utf-8")
        (defs_dir / "broken_two.py").write_text("def !!!\n", encoding="utf-8")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(cli, ["apply"])
            assert result.exit_code == 1

            combined = result.output + (result.stderr or "")
            assert "broken_one.py" in combined
            assert "broken_two.py" in combined
        finally:
            os.chdir(old_cwd)

        # Verify registry is unchanged (still empty from init)
        registry_path = tmp_path / "feature_store" / "registry.json"
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        assert data["feature_groups"] == {}

    def test_cli_list_before_apply_shows_empty_registry(self, tmp_path: Path) -> None:
        """Listing an empty registry after init shows an informational message, not an error."""
        runner = CliRunner()
        runner.invoke(cli, ["init", str(tmp_path)])

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(cli, ["list"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "No feature groups registered" in result.output
        finally:
            os.chdir(old_cwd)

    def test_cli_describe_nonexistent_after_apply(self, tmp_path: Path) -> None:
        """Describing a non-existent group after apply shows the name and suggests kitefs list."""
        runner = CliRunner()
        runner.invoke(cli, ["init", str(tmp_path)])
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "listing.py").write_text(LISTING_DEF, encoding="utf-8")
        (defs_dir / "town.py").write_text(TOWN_DEF, encoding="utf-8")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "nonexistent_group"])

            assert result.exit_code == 1
            combined = result.output + (result.stderr or "")
            assert "nonexistent_group" in combined
            assert "kitefs list" in combined
        finally:
            os.chdir(old_cwd)
