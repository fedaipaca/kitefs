"""End-to-end tests for reference use case registry integrity and file target output."""

import json
import os
from datetime import datetime
from pathlib import Path

from click.testing import CliRunner

from kitefs.cli import cli
from kitefs.feature_store import FeatureStore
from tests.helpers import LISTING_DEF, TOWN_DEF, setup_project


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


class TestFileTargetOutput:
    """End-to-end file output via CLI --target flag."""

    def test_list_target_produces_valid_json_file(self, tmp_path: Path) -> None:
        """kitefs list --target writes a JSON file matching the SDK JSON output."""
        runner = CliRunner()
        runner.invoke(cli, ["init", str(tmp_path)])
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "listing.py").write_text(LISTING_DEF, encoding="utf-8")
        (defs_dir / "town.py").write_text(TOWN_DEF, encoding="utf-8")

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
