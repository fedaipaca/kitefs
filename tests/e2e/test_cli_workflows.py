"""End-to-end tests for CLI-only workflows — init → apply → list → describe."""

import json
import os
from pathlib import Path

from click.testing import CliRunner

from kitefs.cli import cli
from tests.helpers import LISTING_DEF, MINIMAL_DEF, TOWN_DEF

# A concrete definition for tests that only need one simple group.
_SIMPLE_DEF = MINIMAL_DEF.format(varname="listing_features", name="listing_features")


class TestInitThenApply:
    """CLI init followed by SDK apply produces a working project."""

    def test_init_then_apply_produces_valid_registry(self, tmp_path: Path) -> None:
        """Init via CLI, write a definition, apply via SDK — registry contains the group."""
        from kitefs.feature_store import FeatureStore

        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0

        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "listing.py").write_text(_SIMPLE_DEF, encoding="utf-8")

        fs = FeatureStore(project_root=tmp_path)
        apply_result = fs.apply()

        assert apply_result.group_count == 1
        assert "listing_features" in apply_result.registered_groups

        registry_path = tmp_path / "feature_store" / "registry.json"
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        assert "listing_features" in data["feature_groups"]
        assert data["version"] == "1.0"

    def test_init_scaffold_with_no_real_definitions_raises_definition_error(self, tmp_path: Path) -> None:
        """A freshly init'd project with only example_features.py cannot apply."""
        import pytest

        from kitefs.exceptions import DefinitionError
        from kitefs.feature_store import FeatureStore

        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0

        fs = FeatureStore(project_root=tmp_path)

        with pytest.raises(DefinitionError, match=r"No feature group definitions found"):
            fs.apply()


class TestCLIGoldenPath:
    """Full user workflow exercised entirely through CLI commands."""

    def test_init_apply_list_describe_full_cycle(self, tmp_path: Path) -> None:
        """Init → write definitions → apply → list → describe for both groups via CLI."""
        runner = CliRunner()

        # 1. kitefs init
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0

        # 2. Write reference use case definitions
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "listing.py").write_text(LISTING_DEF, encoding="utf-8")
        (defs_dir / "town.py").write_text(TOWN_DEF, encoding="utf-8")

        # 3. kitefs apply
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(cli, ["apply"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "2" in result.output

            # 4. kitefs list — both groups visible
            result = runner.invoke(cli, ["list"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "listing_features" in result.output
            assert "town_market_features" in result.output
            assert "data-science-team" in result.output

            # 5. kitefs describe listing_features — structural fields visible
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "listing_features" in result.output
            assert "listing_id" in result.output
            assert "net_area" in result.output
            assert "sold_price" in result.output
            assert "town_id" in result.output
            assert "town_market_features" in result.output
            assert "ERROR" in result.output

            # 6. kitefs describe town_market_features — OFFLINE_AND_ONLINE visible
            result = runner.invoke(cli, ["describe", "town_market_features"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "OFFLINE_AND_ONLINE" in result.output
            assert "avg_price_per_sqm" in result.output
        finally:
            os.chdir(old_cwd)

    def test_init_apply_list_json_describe_json_full_cycle(self, tmp_path: Path) -> None:
        """Full CLI cycle using --format json for list and describe."""
        runner = CliRunner()
        runner.invoke(cli, ["init", str(tmp_path)])
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "listing.py").write_text(LISTING_DEF, encoding="utf-8")
        (defs_dir / "town.py").write_text(TOWN_DEF, encoding="utf-8")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner.invoke(cli, ["apply"], catch_exceptions=False)

            # kitefs list --format json
            result = runner.invoke(cli, ["list", "--format", "json"], catch_exceptions=False)
            assert result.exit_code == 0
            parsed = json.loads(result.output)
            assert isinstance(parsed, list)
            assert len(parsed) == 2
            names = {s["name"] for s in parsed}
            assert names == {"listing_features", "town_market_features"}

            # kitefs describe listing_features --format json
            result = runner.invoke(cli, ["describe", "listing_features", "--format", "json"], catch_exceptions=False)
            assert result.exit_code == 0
            parsed = json.loads(result.output)
            assert parsed["name"] == "listing_features"
            assert parsed["entity_key"]["name"] == "listing_id"
            assert len(parsed["features"]) == 5
            assert parsed["join_keys"] == [{"field_name": "town_id", "referenced_group": "town_market_features"}]
        finally:
            os.chdir(old_cwd)
