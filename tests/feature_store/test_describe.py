"""Tests for FeatureStore.describe_feature_group() — success, errors, and copy safety."""

import json
from pathlib import Path

import pytest

from kitefs.exceptions import FeatureGroupNotFoundError
from kitefs.feature_store import FeatureStore
from tests.helpers import LISTING_DEF, TOWN_DEF, setup_project


class TestDescribeFeatureGroupSuccess:
    """describe_feature_group() returns the full definition from the registry."""

    def test_returns_full_definition_dict(self, tmp_path: Path) -> None:
        """Default return is a dict with all registry fields for the group."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.describe_feature_group("listing_features")

        assert isinstance(result, dict)
        assert result["name"] == "listing_features"
        assert "entity_key" in result
        assert "event_timestamp" in result
        assert "features" in result
        assert "join_keys" in result
        assert "ingestion_validation" in result
        assert "offline_retrieval_validation" in result
        assert "metadata" in result
        assert "applied_at" in result
        assert "last_materialized_at" in result

    def test_metadata_fields_present(self, tmp_path: Path) -> None:
        """Metadata owner and description are included in the describe output."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.describe_feature_group("listing_features")

        assert isinstance(result, dict)
        meta = result["metadata"]
        assert meta["owner"] == "data-science-team"
        assert meta["description"] == "Historical sold listing attributes and prices"

    def test_last_materialized_at_present_even_when_none(self, tmp_path: Path) -> None:
        """last_materialized_at is included as null for groups not yet materialized."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.describe_feature_group("listing_features")

        assert isinstance(result, dict)
        assert "last_materialized_at" in result
        assert result["last_materialized_at"] is None

    def test_json_format_returns_json_string(self, tmp_path: Path) -> None:
        """format='json' returns a JSON string of the full group definition."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.describe_feature_group("listing_features", format="json")

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["name"] == "listing_features"

    def test_target_writes_json_file(self, tmp_path: Path) -> None:
        """target parameter writes the full definition as JSON to the specified file."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()
        output_path = tmp_path / "describe_out.json"

        result = fs.describe_feature_group("listing_features", target=str(output_path))

        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["name"] == "listing_features"
        assert isinstance(result, str)

    def test_storage_target_value(self, tmp_path: Path) -> None:
        """storage_target is serialized as the enum value string."""
        setup_project(tmp_path, {"town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.describe_feature_group("town_market_features")

        assert isinstance(result, dict)
        assert result["storage_target"] == "OFFLINE_AND_ONLINE"


class TestDescribeFeatureGroupErrors:
    """describe_feature_group() raises FeatureGroupNotFoundError for missing groups."""

    def test_unknown_name_raises_feature_group_not_found_error(self, tmp_path: Path) -> None:
        """Describing a non-existent group raises FeatureGroupNotFoundError."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        with pytest.raises(FeatureGroupNotFoundError, match=r"ghost"):
            fs.describe_feature_group("ghost")

    def test_error_message_suggests_kitefs_list(self, tmp_path: Path) -> None:
        """Error message suggests running kitefs list to see available groups."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        with pytest.raises(FeatureGroupNotFoundError, match=r"kitefs list"):
            fs.describe_feature_group("nonexistent")


class TestDescribeFeatureGroupReturnsCopy:
    """describe_feature_group() returns a copy; mutating it does not affect the registry."""

    def test_mutating_result_does_not_affect_subsequent_call(self, tmp_path: Path) -> None:
        """Mutating a returned dict does not corrupt subsequent describe calls."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        first = fs.describe_feature_group("listing_features")
        assert isinstance(first, dict)
        original_entity_key_name = first["entity_key"]["name"]

        # Mutate a nested value in the returned dict.
        first["entity_key"]["name"] = "mutated_name"

        second = fs.describe_feature_group("listing_features")
        assert isinstance(second, dict)
        assert second["entity_key"]["name"] == original_entity_key_name
