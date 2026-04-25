"""End-to-end tests for SDK-only workflows — FeatureStore API without CLI."""

import json
from pathlib import Path

from kitefs.feature_store import FeatureStore
from kitefs.registry import ApplyResult
from tests.helpers import LISTING_DEF, TOWN_DEF, setup_project


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
