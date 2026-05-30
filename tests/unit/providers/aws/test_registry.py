"""Unit tests for AWSRegistryStore read and write operations."""

from __future__ import annotations

from typing import Any

import boto3
import pytest

from kitefs.errors import RegistryReadError
from kitefs.providers.aws.registry import AWSRegistryStore
from kitefs.registry.serializer import serialize_registry_document
from tests.helpers.aws import create_s3_bucket

_BUCKET = "test-bucket"
_REGION = "eu-central-1"
_PREFIX = "kitefs"

_SAMPLE_DOC: dict[str, Any] = {
    "feature_groups": {
        "town_market_features": {
            "name": "town_market_features",
            "storage_target": "OFFLINE_AND_ONLINE",
            "applied_at": "2024-01-01T00:00:00.000000Z",
            "last_materialized_at": None,
            "entity_key": {"name": "town_id", "dtype": "INTEGER", "description": None},
            "event_timestamp": {"name": "event_timestamp", "dtype": "DATETIME", "description": None},
            "features": [],
            "join_keys": [],
            "ingestion_validation": "ERROR",
            "offline_retrieval_validation": "NONE",
            "metadata": {"description": None, "owner": None, "tags": {}},
        }
    }
}


@pytest.fixture(autouse=True)
def _use_mocked_aws(mocked_aws: None) -> None:
    """Use moto-backed AWS clients for all tests in this module."""


@pytest.fixture
def s3_client() -> Any:
    """Pre-built boto3 S3 client pointed at eu-central-1."""
    client = boto3.client("s3", region_name=_REGION)
    create_s3_bucket(client, bucket=_BUCKET, region=_REGION)
    return client


@pytest.fixture
def store(s3_client: Any) -> AWSRegistryStore:
    """AWSRegistryStore wired to the moto bucket."""
    return AWSRegistryStore(s3_client, bucket=_BUCKET, s3_prefix=_PREFIX)


class TestAWSRegistryStoreWrite:
    """AWSRegistryStore.write uploads a deterministic JSON document to S3."""

    def test_write_then_read_roundtrip(self, store: AWSRegistryStore) -> None:
        """A written document is returned unchanged by read()."""
        store.write(_SAMPLE_DOC)
        result = store.read()
        assert result == _SAMPLE_DOC

    def test_write_is_byte_identical_to_shared_serializer(self, store: AWSRegistryStore, s3_client: Any) -> None:
        """S3 object bytes match serialize_registry_document output exactly."""
        store.write(_SAMPLE_DOC)
        body = s3_client.get_object(Bucket=_BUCKET, Key=f"{_PREFIX}/registry.json")["Body"].read()
        expected = serialize_registry_document(_SAMPLE_DOC).encode("utf-8")
        assert body == expected

    def test_write_uses_correct_key(self, store: AWSRegistryStore, s3_client: Any) -> None:
        """Object is placed at <prefix>/registry.json."""
        store.write(_SAMPLE_DOC)
        keys = [o["Key"] for o in s3_client.list_objects_v2(Bucket=_BUCKET).get("Contents", [])]
        assert f"{_PREFIX}/registry.json" in keys


class TestAWSRegistryStoreRead:
    """AWSRegistryStore.read fetches and validates the registry document from S3."""

    def test_read_missing_object_raises(self, store: AWSRegistryStore) -> None:
        """RegistryReadError with 'apply --publish' suggestion when object is absent."""
        with pytest.raises(RegistryReadError, match="apply --publish"):
            store.read()

    def test_read_malformed_json_raises(self, store: AWSRegistryStore, s3_client: Any) -> None:
        """RegistryReadError when the S3 body is not valid JSON."""
        s3_client.put_object(Bucket=_BUCKET, Key=f"{_PREFIX}/registry.json", Body=b"not json")
        with pytest.raises(RegistryReadError):
            store.read()

    def test_read_wrong_shape_raises_not_dict(self, store: AWSRegistryStore, s3_client: Any) -> None:
        """RegistryReadError when the document root is not a JSON object."""
        s3_client.put_object(Bucket=_BUCKET, Key=f"{_PREFIX}/registry.json", Body=b"[1, 2, 3]")
        with pytest.raises(RegistryReadError):
            store.read()

    def test_read_missing_feature_groups_key_raises(self, store: AWSRegistryStore, s3_client: Any) -> None:
        """RegistryReadError when 'feature_groups' key is absent."""
        import json

        body = json.dumps({"other_key": {}}).encode("utf-8")
        s3_client.put_object(Bucket=_BUCKET, Key=f"{_PREFIX}/registry.json", Body=body)
        with pytest.raises(RegistryReadError, match="feature_groups"):
            store.read()

    def test_read_empty_registry_returns_empty_groups(self, store: AWSRegistryStore, s3_client: Any) -> None:
        """An S3 object with empty feature_groups returns an empty dict."""
        import json

        body = json.dumps({"feature_groups": {}}).encode("utf-8")
        s3_client.put_object(Bucket=_BUCKET, Key=f"{_PREFIX}/registry.json", Body=body)
        result = store.read()
        assert result == {"feature_groups": {}}
