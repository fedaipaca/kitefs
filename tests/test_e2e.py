"""End-to-end tests for KiteFS user workflows.

Each test exercises a complete, multi-step user journey — from project
initialisation through definition registration and feature group
inspection. Tests use realistic reference use case data (listing_features
and town_market_features with join keys, Expect constraints, metadata,
and validation modes) to catch integration issues that unit tests miss.

These tests are organised by workflow pattern:
- CLI-only golden path (init → apply → list → describe via CLI)
- SDK-only golden path (FeatureStore API without CLI)
- Re-apply lifecycle (registry state across multiple apply cycles)
- Error workflows (validation errors, empty registries, missing groups)
- Reference use case integrity (registry JSON structure correctness)
- File target output (--target flag end-to-end)
"""

import json
from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from kitefs.cli import cli
from kitefs.exceptions import DefinitionError, FeatureGroupNotFoundError
from kitefs.feature_store import FeatureStore
from kitefs.registry import ApplyResult
from tests.helpers import LISTING_DEF, MINIMAL_DEF, TOWN_DEF, setup_project

# A concrete definition for tests that only need one simple group.
_SIMPLE_DEF = MINIMAL_DEF.format(varname="listing_features", name="listing_features")


# ---------------------------------------------------------------------------
# Moved from test_feature_store.py — original end-to-end tests
# ---------------------------------------------------------------------------


class TestInitThenApply:
    """CLI init followed by SDK apply produces a working project."""

    def test_init_then_apply_produces_valid_registry(self, tmp_path: Path) -> None:
        """Init via CLI, write a definition, apply via SDK — registry contains the group."""
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
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0

        fs = FeatureStore(project_root=tmp_path)

        with pytest.raises(DefinitionError, match=r"No feature group definitions found"):
            fs.apply()


# ---------------------------------------------------------------------------
# CLI-only golden path
# ---------------------------------------------------------------------------


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
        import os

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

        import os

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


# ---------------------------------------------------------------------------
# SDK-only golden path
# ---------------------------------------------------------------------------


class TestSDKGoldenPath:
    """Full user workflow exercised through FeatureStore SDK only."""

    def test_sdk_apply_list_describe_full_cycle(self, tmp_path: Path) -> None:
        """Apply → list → describe for both groups using SDK methods."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)

        # 1. apply
        result = fs.apply()
        assert isinstance(result, ApplyResult)
        assert result.group_count == 2
        assert result.registered_groups == ("listing_features", "town_market_features")

        # 2. list_feature_groups
        summaries = fs.list_feature_groups()
        assert isinstance(summaries, list)
        assert len(summaries) == 2
        names = {s["name"] for s in summaries}
        assert names == {"listing_features", "town_market_features"}
        for s in summaries:
            assert "owner" in s
            assert "entity_key" in s
            assert "storage_target" in s
            assert "feature_count" in s

        # 3. describe listing_features
        listing = fs.describe_feature_group("listing_features")
        assert isinstance(listing, dict)
        assert listing["name"] == "listing_features"
        assert listing["entity_key"]["name"] == "listing_id"
        assert listing["event_timestamp"]["name"] == "event_timestamp"
        assert len(listing["features"]) == 5
        assert listing["join_keys"] == [{"field_name": "town_id", "referenced_group": "town_market_features"}]
        assert listing["ingestion_validation"] == "ERROR"
        assert listing["offline_retrieval_validation"] == "NONE"
        assert listing["metadata"]["owner"] == "data-science-team"
        assert listing["applied_at"] is not None
        assert listing["last_materialized_at"] is None

        # 4. describe town_market_features
        town = fs.describe_feature_group("town_market_features")
        assert isinstance(town, dict)
        assert town["storage_target"] == "OFFLINE_AND_ONLINE"
        assert len(town["features"]) == 1
        assert town["features"][0]["name"] == "avg_price_per_sqm"

    def test_sdk_apply_list_json_describe_json(self, tmp_path: Path) -> None:
        """SDK format='json' and target parameters produce correct output."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        # list as JSON string
        list_json = fs.list_feature_groups(format="json")
        assert isinstance(list_json, str)
        parsed = json.loads(list_json)
        assert len(parsed) == 2

        # describe as JSON string
        desc_json = fs.describe_feature_group("listing_features", format="json")
        assert isinstance(desc_json, str)
        parsed = json.loads(desc_json)
        assert parsed["name"] == "listing_features"

        # list with target
        output_path = tmp_path / "list_output.json"
        fs.list_feature_groups(target=str(output_path))
        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(data) == 2

        # describe with target
        desc_path = tmp_path / "describe_output.json"
        fs.describe_feature_group("listing_features", target=str(desc_path))
        assert desc_path.exists()
        data = json.loads(desc_path.read_text(encoding="utf-8"))
        assert data["name"] == "listing_features"


# ---------------------------------------------------------------------------
# Re-apply lifecycle
# ---------------------------------------------------------------------------


class TestReApplyLifecycle:
    """Registry state management across multiple apply cycles (KTD-3 full rebuild)."""

    def test_reapply_preserves_last_materialized_at(self, tmp_path: Path) -> None:
        """Existing group's last_materialized_at survives re-apply; new group gets null."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        # Simulate materialization by patching registry.json directly
        registry_path = tmp_path / "feature_store" / "registry.json"
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        data["feature_groups"]["listing_features"]["last_materialized_at"] = "2025-06-01T12:00:00+00:00"
        registry_path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")

        # Add a new group and re-apply
        defs_dir = tmp_path / "feature_store" / "definitions"
        new_group_def = MINIMAL_DEF.format(varname="extra_group", name="extra_group")
        (defs_dir / "extra.py").write_text(new_group_def, encoding="utf-8")
        fs2 = FeatureStore(project_root=tmp_path)
        fs2.apply()

        # Verify
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        assert data["feature_groups"]["listing_features"]["last_materialized_at"] == "2025-06-01T12:00:00+00:00"
        assert data["feature_groups"]["extra_group"]["last_materialized_at"] is None

        # Both applied_at should be recent
        for group_data in data["feature_groups"].values():
            applied = datetime.fromisoformat(group_data["applied_at"])
            assert applied is not None

    def test_reapply_removes_deleted_definitions(self, tmp_path: Path) -> None:
        """Deleting a definition file removes the group from registry on re-apply."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        # Verify both exist
        assert len(fs.list_feature_groups()) == 2

        # Delete listing definition (not town, since listing references town via join key)
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "listing.py").unlink()

        # Re-apply
        fs2 = FeatureStore(project_root=tmp_path)
        result = fs2.apply()

        assert result.group_count == 1
        assert "listing_features" not in result.registered_groups

        # list_feature_groups also reflects the deletion
        summaries = fs2.list_feature_groups()
        assert isinstance(summaries, list)
        assert len(summaries) == 1
        assert summaries[0]["name"] == "town_market_features"

        # describe the deleted group raises error
        with pytest.raises(FeatureGroupNotFoundError):
            fs2.describe_feature_group("listing_features")

    def test_reapply_updates_modified_definitions(self, tmp_path: Path) -> None:
        """Modifying a definition is reflected in describe after re-apply."""
        setup_project(tmp_path, {"town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        # Verify original has 1 feature
        desc = fs.describe_feature_group("town_market_features")
        assert isinstance(desc, dict)
        assert len(desc["features"]) == 1

        # Modify: add a second feature
        modified_town = TOWN_DEF.replace(
            "                expect=Expect().not_null().gt(0)),\n    ],",
            "                expect=Expect().not_null().gt(0)),\n"
            '        Feature(name="median_price", dtype=FeatureType.FLOAT,\n'
            '                description="Median sold price in this town"),\n    ],',
        )
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "town.py").write_text(modified_town, encoding="utf-8")

        # Re-apply with a fresh FeatureStore
        fs2 = FeatureStore(project_root=tmp_path)
        fs2.apply()

        desc2 = fs2.describe_feature_group("town_market_features")
        assert isinstance(desc2, dict)
        assert len(desc2["features"]) == 2
        feature_names = {f["name"] for f in desc2["features"]}
        assert "avg_price_per_sqm" in feature_names
        assert "median_price" in feature_names

    def test_reapply_all_or_nothing_on_validation_failure(self, tmp_path: Path) -> None:
        """Adding a broken definition fails apply without altering the existing registry."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        # Snapshot the registry before the bad apply
        registry_path = tmp_path / "feature_store" / "registry.json"
        original_content = registry_path.read_text(encoding="utf-8")

        # Add a broken definition
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "broken.py").write_text("import nonexistent_module_xyz\n", encoding="utf-8")

        # Re-apply should fail
        fs2 = FeatureStore(project_root=tmp_path)
        with pytest.raises(DefinitionError):
            fs2.apply()

        # Registry must be unchanged
        assert registry_path.read_text(encoding="utf-8") == original_content

        # Original groups still accessible via a new FeatureStore
        fs3 = FeatureStore(project_root=tmp_path)
        summaries = fs3.list_feature_groups()
        assert isinstance(summaries, list)
        assert len(summaries) == 2
        names = {s["name"] for s in summaries}
        assert names == {"listing_features", "town_market_features"}


# ---------------------------------------------------------------------------
# Error workflows
# ---------------------------------------------------------------------------


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

        import os

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

        import os

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

        import os

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


# ---------------------------------------------------------------------------
# Reference use case registry integrity
# ---------------------------------------------------------------------------


class TestReferenceUseCaseIntegrity:
    """The complete reference use case produces a correct, self-consistent registry."""

    def test_reference_use_case_registry_structure(self, tmp_path: Path) -> None:
        """Full registry.json structure is correct for the reference use case definitions."""
        runner = CliRunner()
        runner.invoke(cli, ["init", str(tmp_path)])
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "listing.py").write_text(LISTING_DEF, encoding="utf-8")
        (defs_dir / "town.py").write_text(TOWN_DEF, encoding="utf-8")

        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        registry_path = tmp_path / "feature_store" / "registry.json"
        data = json.loads(registry_path.read_text(encoding="utf-8"))

        # Top-level structure
        assert data["version"] == "1.0"
        assert set(data["feature_groups"].keys()) == {"listing_features", "town_market_features"}

        # listing_features
        listing = data["feature_groups"]["listing_features"]
        assert listing["storage_target"] == "OFFLINE"
        assert listing["entity_key"]["name"] == "listing_id"
        assert listing["entity_key"]["dtype"] == "INTEGER"
        assert listing["event_timestamp"]["name"] == "event_timestamp"
        assert listing["event_timestamp"]["dtype"] == "DATETIME"
        assert listing["ingestion_validation"] == "ERROR"
        assert listing["offline_retrieval_validation"] == "NONE"
        assert listing["last_materialized_at"] is None
        datetime.fromisoformat(listing["applied_at"])  # Must not raise

        # Features sorted alphabetically
        feature_names = [f["name"] for f in listing["features"]]
        assert feature_names == sorted(feature_names)
        assert len(listing["features"]) == 5

        # Expect constraints on net_area (not_null + gt(0))
        net_area = next(f for f in listing["features"] if f["name"] == "net_area")
        assert net_area["expect"] is not None
        assert len(net_area["expect"]) == 2

        # Expect constraints on build_year (not_null + gte(1900) + lte(2030))
        build_year = next(f for f in listing["features"] if f["name"] == "build_year")
        assert build_year["expect"] is not None
        assert len(build_year["expect"]) == 3

        # Join keys
        assert listing["join_keys"] == [{"field_name": "town_id", "referenced_group": "town_market_features"}]

        # Metadata
        assert listing["metadata"]["owner"] == "data-science-team"
        assert listing["metadata"]["description"] == "Historical sold listing attributes and prices"
        assert listing["metadata"]["tags"] == {"domain": "real-estate", "cadence": "monthly"}

        # town_market_features
        town = data["feature_groups"]["town_market_features"]
        assert town["storage_target"] == "OFFLINE_AND_ONLINE"
        assert town["entity_key"]["name"] == "town_id"
        assert town["entity_key"]["dtype"] == "INTEGER"
        assert len(town["features"]) == 1
        assert town["features"][0]["name"] == "avg_price_per_sqm"
        assert town["join_keys"] == []
        assert town["last_materialized_at"] is None

        # Cross-group consistency: join key types match
        listing_town_id_feature = next(f for f in listing["features"] if f["name"] == "town_id")
        assert listing_town_id_feature["dtype"] == town["entity_key"]["dtype"]

    def test_reference_use_case_describe_roundtrip(self, tmp_path: Path) -> None:
        """Described output matches what was defined for both groups."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        # listing_features roundtrip
        listing = fs.describe_feature_group("listing_features")
        assert isinstance(listing, dict)
        assert listing["name"] == "listing_features"
        assert listing["entity_key"]["name"] == "listing_id"
        assert listing["entity_key"]["dtype"] == "INTEGER"
        feature_names = {f["name"] for f in listing["features"]}
        assert feature_names == {"net_area", "number_of_rooms", "build_year", "sold_price", "town_id"}
        assert listing["metadata"]["owner"] == "data-science-team"
        assert listing["metadata"]["tags"] == {"domain": "real-estate", "cadence": "monthly"}

        # town_market_features roundtrip
        town = fs.describe_feature_group("town_market_features")
        assert isinstance(town, dict)
        assert town["name"] == "town_market_features"
        assert town["storage_target"] == "OFFLINE_AND_ONLINE"
        assert town["entity_key"]["name"] == "town_id"
        assert len(town["features"]) == 1
        assert town["features"][0]["name"] == "avg_price_per_sqm"
        assert town["metadata"]["owner"] == "data-science-team"


# ---------------------------------------------------------------------------
# File target output
# ---------------------------------------------------------------------------


class TestFileTargetOutput:
    """End-to-end file output via CLI --target flag."""

    def test_list_target_produces_valid_json_file(self, tmp_path: Path) -> None:
        """kitefs list --target writes a JSON file matching the SDK JSON output."""
        runner = CliRunner()
        runner.invoke(cli, ["init", str(tmp_path)])
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "listing.py").write_text(LISTING_DEF, encoding="utf-8")
        (defs_dir / "town.py").write_text(TOWN_DEF, encoding="utf-8")

        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            output_file = tmp_path / "list_output.json"
            result = runner.invoke(cli, ["list", "--target", str(output_file)], catch_exceptions=False)
            assert result.exit_code == 0
            assert output_file.exists()
            data = json.loads(output_file.read_text(encoding="utf-8"))
            assert isinstance(data, list)
            assert len(data) == 2
            names = {s["name"] for s in data}
            assert names == {"listing_features", "town_market_features"}
        finally:
            os.chdir(old_cwd)

    def test_describe_target_produces_valid_json_file(self, tmp_path: Path) -> None:
        """kitefs describe --target writes a JSON file with the full group definition."""
        runner = CliRunner()
        runner.invoke(cli, ["init", str(tmp_path)])
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "listing.py").write_text(LISTING_DEF, encoding="utf-8")
        (defs_dir / "town.py").write_text(TOWN_DEF, encoding="utf-8")

        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            output_file = tmp_path / "describe_output.json"
            result = runner.invoke(
                cli,
                ["describe", "listing_features", "--target", str(output_file)],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert output_file.exists()
            data = json.loads(output_file.read_text(encoding="utf-8"))
            assert data["name"] == "listing_features"
            assert len(data["features"]) == 5
            assert data["join_keys"] == [{"field_name": "town_id", "referenced_group": "town_market_features"}]
        finally:
            os.chdir(old_cwd)
