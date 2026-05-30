"""Integration tests for Feature 16 defect fixes: remote DynamoDB materialization.

Covers four correctness issues identified in review:
1. last_materialized_at is written to local registry, not S3 registry.
2. ProviderError propagates from materialize() rather than being swallowed.
3. Whole-valued FLOAT features return as float after DynamoDB round-trip.
4. Null feature attributes in select return None, not a missing key.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import boto3
import pytest
import yaml

from kitefs.errors import ProviderError
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.aws import create_s3_bucket
from tests.helpers.dataframes import town_market_frame
from tests.helpers.tmp_store import make_initialized_project

_BUCKET = "test-bucket"
_REGION = "eu-central-1"
_PREFIX = "kitefs"
_UTC = datetime.UTC

_TOWN_MARKET_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup, FeatureType,
    StorageTarget, ValidationMode,
)

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="event_timestamp"),
    features=[Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT)],
    ingestion_validation=ValidationMode.NONE,
    offline_retrieval_validation=ValidationMode.NONE,
)
"""

_LOCAL_YAML: dict[str, Any] = {
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
    """Pre-built boto3 S3 client with the test bucket created."""
    client = boto3.client("s3", region_name=_REGION)
    create_s3_bucket(client, bucket=_BUCKET, region=_REGION)
    return client


@pytest.fixture
def remote_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, s3_client: Any) -> FeatureStore:
    """Remote-target FeatureStore with registry published to S3.

    Scaffolds a producer project, writes the definition, applies locally and
    publishes the registry to S3, then switches runtime.target to 'remote'.
    Both local and S3 registries therefore exist before materialization.
    """
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (tmp_path / "kitefs.yaml").write_text(yaml.dump(_LOCAL_YAML), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    FeatureStore().apply(publish=True)

    remote_yaml = {**_LOCAL_YAML, "runtime": {"target": "remote"}}
    (tmp_path / "kitefs.yaml").write_text(yaml.dump(remote_yaml), encoding="utf-8")
    return FeatureStore()


def _ingest_rows(store: FeatureStore, rows: list[dict]) -> None:
    store.ingest("town_market_features", town_market_frame(rows))


def _local_registry(tmp_path: Path) -> dict[str, Any]:
    path = tmp_path / "feature_store" / "registry.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _s3_registry(s3_client: Any) -> dict[str, Any]:
    body = s3_client.get_object(Bucket=_BUCKET, Key=f"{_PREFIX}/registry.json")["Body"].read()
    return json.loads(body)


def _write_stale_local_registry(tmp_path: Path) -> None:
    registry_path = tmp_path / "feature_store" / "registry.json"
    registry_path.write_text(json.dumps({"feature_groups": {}}, sort_keys=True, indent=2) + "\n", encoding="utf-8")


class TestLocalRegistryUpdatedOnRemoteMaterialize:
    """last_materialized_at lands in local registry, not S3 (Issue 1)."""

    def test_local_registry_stamped_after_remote_materialize(self, remote_store: FeatureStore, tmp_path: Path) -> None:
        """Remote materialize writes last_materialized_at to local registry.json."""
        _ingest_rows(
            remote_store,
            [{"town_id": 1, "event_timestamp": datetime.datetime(2025, 7, 1, tzinfo=_UTC), "avg_price_per_sqm": 100.0}],
        )

        s3_before = _s3_registry(boto3.client("s3", region_name=_REGION)).copy()
        result = remote_store.materialize("town_market_features")

        assert "town_market_features" in result.succeeded

        local_doc = _local_registry(tmp_path)
        local_ts = local_doc["feature_groups"]["town_market_features"].get("last_materialized_at")
        assert local_ts is not None, "local registry should have last_materialized_at after materialize"

        s3_after = _s3_registry(boto3.client("s3", region_name=_REGION))
        s3_ts_before = s3_before["feature_groups"]["town_market_features"].get("last_materialized_at")
        s3_ts_after = s3_after["feature_groups"]["town_market_features"].get("last_materialized_at")
        assert s3_ts_before == s3_ts_after, "S3 registry last_materialized_at should not change until apply --publish"

    def test_apply_publish_propagates_timestamp_to_s3(
        self, remote_store: FeatureStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """apply --publish after remote materialize propagates the timestamp to S3."""
        _ingest_rows(
            remote_store,
            [{"town_id": 1, "event_timestamp": datetime.datetime(2025, 7, 1, tzinfo=_UTC), "avg_price_per_sqm": 100.0}],
        )
        remote_store.materialize("town_market_features")

        # Switch back to local target to run apply --publish.
        (tmp_path / "kitefs.yaml").write_text(yaml.dump(_LOCAL_YAML), encoding="utf-8")
        FeatureStore().apply(publish=True)

        local_doc = _local_registry(tmp_path)
        s3_doc = _s3_registry(boto3.client("s3", region_name=_REGION))
        local_ts = local_doc["feature_groups"]["town_market_features"].get("last_materialized_at")
        s3_ts = s3_doc["feature_groups"]["town_market_features"].get("last_materialized_at")
        assert local_ts == s3_ts, "apply --publish should propagate local last_materialized_at to S3"


class TestStaleLocalRegistryHandled:
    """Stale local registry failures are reported as per-group failures."""

    def test_missing_local_group_returns_failed_group(self, remote_store: FeatureStore, tmp_path: Path) -> None:
        """Remote materialize does not leak KeyError when the local registry is stale."""
        _ingest_rows(
            remote_store,
            [{"town_id": 1, "event_timestamp": datetime.datetime(2025, 7, 1, tzinfo=_UTC), "avg_price_per_sqm": 100.0}],
        )
        _write_stale_local_registry(tmp_path)

        result = remote_store.materialize("town_market_features")

        assert result.succeeded == []
        assert len(result.failed) == 1
        failed = result.failed[0]
        assert failed.name == "town_market_features"
        assert "local working registry" in failed.error_message
        assert "apply" in failed.error_message

        lookup = remote_store.get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 1}},
        )
        assert lookup["avg_price_per_sqm"] == 100.0


class TestProviderErrorPropagates:
    """ProviderError from the online store raises, not a MaterializeResult.failed (Issue 2)."""

    def test_provider_error_raises_from_materialize(self, remote_store: FeatureStore) -> None:
        """materialize raises ProviderError when the online store raises it."""
        _ingest_rows(
            remote_store,
            [{"town_id": 1, "event_timestamp": datetime.datetime(2025, 7, 1, tzinfo=_UTC), "avg_price_per_sqm": 100.0}],
        )

        # Patch the DynamoDB client's batch_write_item to simulate a credential failure.
        remote_store._provider._dynamodb.batch_write_item = MagicMock(
            side_effect=ProviderError("AWS credentials missing")
        )

        with pytest.raises(ProviderError):
            remote_store.materialize("town_market_features")


class TestFloatTypeEquivalence:
    """Whole-valued FLOAT features return as float, not int (Issue 3)."""

    def test_whole_valued_float_is_float(self, remote_store: FeatureStore) -> None:
        """avg_price_per_sqm 15200.0 stored in DynamoDB comes back as float, not int."""
        _ingest_rows(
            remote_store,
            [
                {
                    "town_id": 5,
                    "event_timestamp": datetime.datetime(2025, 7, 1, tzinfo=_UTC),
                    "avg_price_per_sqm": 15200.0,
                }
            ],
        )
        remote_store.materialize("town_market_features")

        result = remote_store.get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 5}},
        )

        price = result.get("avg_price_per_sqm")
        assert isinstance(price, float), f"expected float, got {type(price).__name__}: {price!r}"
        assert price == 15200.0


class TestNullFeatureInSelectReturnsNone:
    """Null feature attributes in select return None, not a missing key (Issue 4)."""

    def test_null_feature_present_as_none_in_result(self, remote_store: FeatureStore) -> None:
        """A feature with None value appears in the result dict with value None."""
        _ingest_rows(
            remote_store,
            [
                {
                    "town_id": 1,
                    "event_timestamp": datetime.datetime(2025, 7, 1, tzinfo=_UTC),
                    "avg_price_per_sqm": None,
                }
            ],
        )
        remote_store.materialize("town_market_features")

        result = remote_store.get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 1}},
        )

        assert result != {}, "expected a hit, not an empty dict"
        assert "avg_price_per_sqm" in result, "null feature should be present in result"
        assert result["avg_price_per_sqm"] is None
