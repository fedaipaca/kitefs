"""Integration tests for FeatureStore.apply(publish=True) — remote registry publish."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import boto3
import pytest
import yaml

from kitefs.errors import ConfigurationError
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.aws import create_s3_bucket
from tests.helpers.tmp_store import make_initialized_project

_BUCKET = "test-bucket"
_REGION = "eu-central-1"
_PREFIX = "kitefs"

# Inline definition sources reusing the same feature definitions as other integration tests.
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

_LISTING_SRC = """\
from kitefs import FeatureGroup, EntityKey, EventTimestamp, Feature, FeatureType, JoinKey, StorageTarget

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[Feature(name="net_area", dtype=FeatureType.INTEGER)],
    join_keys=[JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="town_market_features")],
)
"""

_REMOTE_YAML: dict[str, Any] = {
    "version": 1,
    "project": {"name": "kitefs_featurestore_project"},
    "runtime": {"target": "local"},
    "remote": {
        "region": _REGION,
        "registry": {"type": "aws_s3", "bucket": _BUCKET, "s3_prefix": _PREFIX},
        "offline_store": {"type": "aws_s3", "bucket": _BUCKET, "s3_prefix": _PREFIX},
        "online_store": {"type": "aws_dynamodb", "dynamodb_table_prefix": "kitefs_"},
    },
}


@pytest.fixture(autouse=True)
def _use_mocked_aws(mocked_aws: None) -> None:
    """Use moto-backed AWS clients for all tests in this module."""


@pytest.fixture
def s3_client() -> Any:
    """Pre-built boto3 S3 client pointed at eu-central-1 with the test bucket created."""
    client = boto3.client("s3", region_name=_REGION)
    create_s3_bucket(client, bucket=_BUCKET, region=_REGION)
    return client


@pytest.fixture
def producer_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, s3_client: Any) -> Path:
    """Scaffold a producer project with both definitions and a remote-aware kitefs.yaml."""
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    (tmp_path / "kitefs.yaml").write_text(yaml.dump(_REMOTE_YAML), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestApplyPublish:
    """apply(publish=True) writes local registry and pushes the same document to S3."""

    def test_returns_published_true(self, producer_project: Path) -> None:
        """ApplyResult.published is True when publish=True succeeds."""
        result = FeatureStore().apply(publish=True)
        assert result.published is True

    def test_registered_groups_sorted(self, producer_project: Path) -> None:
        """registered_groups contains both groups sorted alphabetically."""
        result = FeatureStore().apply(publish=True)
        assert result.registered_groups == ["listing_features", "town_market_features"]

    def test_local_registry_is_written(self, producer_project: Path) -> None:
        """The local registry.json is created and parseable."""
        FeatureStore().apply(publish=True)
        local = producer_project / "feature_store" / "registry.json"
        assert local.exists()
        doc = json.loads(local.read_text(encoding="utf-8"))
        assert "listing_features" in doc["feature_groups"]
        assert "town_market_features" in doc["feature_groups"]

    def test_s3_object_matches_local_file(self, producer_project: Path, s3_client: Any) -> None:
        """S3 registry.json bytes are identical to the local file bytes."""
        FeatureStore().apply(publish=True)
        local_bytes = (producer_project / "feature_store" / "registry.json").read_bytes()
        s3_bytes = s3_client.get_object(Bucket=_BUCKET, Key=f"{_PREFIX}/registry.json")["Body"].read()
        assert s3_bytes == local_bytes

    def test_s3_object_contains_both_groups(self, producer_project: Path, s3_client: Any) -> None:
        """S3 registry.json JSON document contains both group names."""
        FeatureStore().apply(publish=True)
        body = s3_client.get_object(Bucket=_BUCKET, Key=f"{_PREFIX}/registry.json")["Body"].read()
        doc = json.loads(body)
        assert "listing_features" in doc["feature_groups"]
        assert "town_market_features" in doc["feature_groups"]

    def test_plain_apply_does_not_publish(self, producer_project: Path, s3_client: Any) -> None:
        """apply(publish=False) returns published=False and writes nothing to S3."""
        result = FeatureStore().apply(publish=False)

        assert result.published is False
        response = s3_client.list_objects_v2(Bucket=_BUCKET)
        assert response.get("KeyCount", 0) == 0


class TestApplyPublishMisconfig:
    """apply(publish=True) raises ConfigurationError before any work on invalid config."""

    def test_missing_registry_bucket_raises_before_discovery(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, s3_client: Any
    ) -> None:
        """ConfigurationError on empty bucket; feature groups must not be registered."""
        make_initialized_project(tmp_path)
        defs = tmp_path / "feature_store" / "definitions"
        (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")

        bad_yaml = {
            **_REMOTE_YAML,
            "remote": {
                **_REMOTE_YAML["remote"],
                "registry": {"type": "aws_s3", "bucket": "", "s3_prefix": _PREFIX},
            },
        }
        (tmp_path / "kitefs.yaml").write_text(yaml.dump(bad_yaml), encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigurationError):
            FeatureStore().apply(publish=True)

        # The registry must not contain the group — config validation fires before discovery.
        registry = tmp_path / "feature_store" / "registry.json"
        doc = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {"feature_groups": {}}
        assert "town_market_features" not in doc.get("feature_groups", {})
