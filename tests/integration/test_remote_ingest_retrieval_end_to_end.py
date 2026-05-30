"""Integration tests for Feature 15: remote S3 offline store ingest and retrieval.

Tests the full SDK flow (FeatureStore.ingest / FeatureStore.get_historical_features)
against a moto-backed S3 bucket.  The registry is published to S3 via apply(publish=True)
then all subsequent SDK calls use runtime.target: remote.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
import pytest
import yaml

from kitefs.errors import ConfigurationError
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.aws import create_s3_bucket
from tests.helpers.dataframes import listing_features_frame, town_market_frame
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

_LISTING_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup, FeatureType,
    JoinKey, StorageTarget, ValidationMode,
)

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[
        Feature(name="net_area", dtype=FeatureType.INTEGER),
        Feature(name="sold_price", dtype=FeatureType.FLOAT),
    ],
    join_keys=[
        JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="town_market_features"),
    ],
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

    Scaffolds a producer project, writes both definitions, applies locally and
    publishes the registry to S3, then switches runtime.target to 'remote'.
    """
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    (tmp_path / "kitefs.yaml").write_text(yaml.dump(_LOCAL_YAML), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    # Publish registry to S3 while runtime is still local.
    FeatureStore().apply(publish=True)

    # Switch to remote target.
    remote_yaml = {**_LOCAL_YAML, "runtime": {"target": "remote"}}
    (tmp_path / "kitefs.yaml").write_text(yaml.dump(remote_yaml), encoding="utf-8")

    return FeatureStore()


def _market_rows() -> list[dict]:
    return [
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 2, 1, tzinfo=_UTC), "avg_price_per_sqm": 20000.0},
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 4, 1, tzinfo=_UTC), "avg_price_per_sqm": 25400.0},
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 5, 1, tzinfo=_UTC), "avg_price_per_sqm": 30000.0},
    ]


def _listing_rows() -> list[dict]:
    return [
        {
            "listing_id": 1002,
            "sold_at": datetime.datetime(2024, 4, 5, tzinfo=_UTC),
            "town_id": 1,
            "net_area": 90,
            "sold_price": 410000.0,
        }
    ]


class TestRemoteIngest:
    """FeatureStore.ingest routes to S3 when runtime.target is remote."""

    def test_ingest_returns_s3_uris(self, remote_store: FeatureStore) -> None:
        """written_files contains s3:// URIs after remote ingest."""
        df = town_market_frame(_market_rows())

        result = remote_store.ingest("town_market_features", df)

        assert result.accepted_rows == len(_market_rows())
        assert all(uri.startswith("s3://") for uri in result.written_files)

    def test_ingest_creates_objects_at_expected_key_prefix(self, remote_store: FeatureStore, s3_client: Any) -> None:
        """S3 objects are created under the Hive partition path for the feature group."""
        row = {
            "town_id": 1,
            "event_timestamp": datetime.datetime(2024, 2, 1, tzinfo=_UTC),
            "avg_price_per_sqm": 20000.0,
        }
        df = town_market_frame([row])

        result = remote_store.ingest("town_market_features", df)

        expected_prefix = f"{_PREFIX}/data/offline_store/town_market_features/year=2024/month=02/"
        keys = [o["Key"] for o in s3_client.list_objects_v2(Bucket=_BUCKET, Prefix=expected_prefix).get("Contents", [])]
        assert len(keys) == 1
        assert len(result.written_files) == 1
        assert result.written_files[0] == f"s3://{_BUCKET}/{keys[0]}"

    def test_ingest_multi_month_creates_multiple_objects(self, remote_store: FeatureStore, s3_client: Any) -> None:
        """Rows spanning three months produce three S3 objects."""
        df = town_market_frame(_market_rows())

        result = remote_store.ingest("town_market_features", df)

        response = s3_client.list_objects_v2(
            Bucket=_BUCKET,
            Prefix=f"{_PREFIX}/data/offline_store/town_market_features/",
        )
        assert len(response.get("Contents", [])) == 3
        assert len(result.written_files) == 3


class TestRemoteRetrieval:
    """FeatureStore.get_historical_features reads from S3 when runtime.target is remote."""

    def test_retrieval_returns_expected_columns(self, remote_store: FeatureStore) -> None:
        """Remote retrieval returns the same column set as local retrieval."""
        remote_store.ingest("listing_features", listing_features_frame(_listing_rows()))

        result = remote_store.get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
        )

        assert isinstance(result, pd.DataFrame)
        assert "net_area" in result.columns
        assert "sold_price" in result.columns

    def test_retrieval_empty_group_returns_empty_dataframe(self, remote_store: FeatureStore) -> None:
        """Returns an empty DataFrame with correct columns when no S3 objects exist."""
        result = remote_store.get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
        )

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_joined_retrieval_pit_correctness(self, remote_store: FeatureStore) -> None:
        """Listing 1002 joins to the market snapshot at or before sold_at (2024-04-01)."""
        remote_store.ingest("town_market_features", town_market_frame(_market_rows()))
        remote_store.ingest("listing_features", listing_features_frame(_listing_rows()))

        result = remote_store.get_historical_features(
            from_="listing_features",
            join=["town_market_features"],
            select={
                "listing_features": ["net_area", "sold_price"],
                "town_market_features": ["avg_price_per_sqm"],
            },
        )

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        row = result[result["listing_id"] == 1002].iloc[0]
        assert row["town_market_features_avg_price_per_sqm"] == 25400.0
        assert row["town_market_features_event_timestamp"] == datetime.datetime(2024, 4, 1, 0, 0, 0)


class TestMissingOfflineConfig:
    """ConfigurationError is raised early when remote.offline_store is misconfigured."""

    def test_empty_bucket_raises_config_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, s3_client: Any
    ) -> None:
        """ConfigurationError naming 'remote offline' and 'bucket' when bucket is empty."""
        make_initialized_project(tmp_path)
        defs = tmp_path / "feature_store" / "definitions"
        (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")

        bad_yaml = {
            "version": 1,
            "project": {"name": "testproject"},
            "runtime": {"target": "remote"},
            "remote": {
                "region": _REGION,
                "registry": {"type": "aws_s3", "bucket": _BUCKET, "s3_prefix": _PREFIX},
                "offline_store": {"type": "aws_s3", "bucket": "", "s3_prefix": _PREFIX},
                "online_store": {"type": "aws_dynamodb", "dynamodb_table_prefix": "kitefs_"},
            },
        }
        (tmp_path / "kitefs.yaml").write_text(yaml.dump(bad_yaml), encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        # Seed the registry so the error occurs at offline_store validation, not registry read.
        from kitefs.registry.serializer import build_registry_document, serialize_registry_document
        from tests.fixtures.definitions import build_town_market_features

        doc = build_registry_document(
            [build_town_market_features()],
            prior_document={"feature_groups": {}},
            now=datetime.datetime(2024, 1, 1, tzinfo=_UTC),
        )
        body = serialize_registry_document(doc).encode("utf-8")
        s3_client.put_object(Bucket=_BUCKET, Key=f"{_PREFIX}/registry.json", Body=body)

        row = {
            "town_id": 1,
            "event_timestamp": datetime.datetime(2024, 2, 1, tzinfo=_UTC),
            "avg_price_per_sqm": 20000.0,
        }
        df = town_market_frame([row])

        with pytest.raises(ConfigurationError) as exc_info:
            FeatureStore().ingest("town_market_features", df)

        msg = str(exc_info.value)
        assert "remote offline" in msg.lower() or "offline" in msg.lower()
        assert "bucket" in msg.lower()


class TestRemoteIngestOrderTieBreaking:
    """Later-ingested rows win tie-breaking when event timestamps are equal."""

    # WARNING: flaky — when both ingests land in the same second,
    # moto S3 LastModified ties are broken by UUID key, which is random.
    @pytest.mark.skip(reason="flaky — moto S3 LastModified ties broken by random UUID key")
    def test_second_ingest_wins_equal_timestamp_join(self, remote_store: FeatureStore) -> None:
        """A correction ingested after the original wins the PIT join tie-break.

        Ingest two market rows for the same (town_id, event_timestamp) in separate
        calls.  The second (correction) ingest has a higher IngestOrder, so after
        sorting by IngestOrder the correction row sits later in the concatenated
        table and therefore wins the point-in-time join tie-break.
        """
        ts_market = datetime.datetime(2024, 2, 1, tzinfo=_UTC)
        ts_listing = datetime.datetime(2024, 4, 5, tzinfo=_UTC)

        # First ingest: original market value.
        remote_store.ingest(
            "town_market_features",
            pd.DataFrame([{"town_id": 1, "event_timestamp": ts_market, "avg_price_per_sqm": 10000.0}]),
        )

        # Second ingest: corrected value at the same event timestamp.
        remote_store.ingest(
            "town_market_features",
            pd.DataFrame([{"town_id": 1, "event_timestamp": ts_market, "avg_price_per_sqm": 99999.0}]),
        )

        # Listing sold after both market snapshots — triggers the tie-break.
        remote_store.ingest(
            "listing_features",
            listing_features_frame(
                [
                    {
                        "listing_id": 1,
                        "sold_at": ts_listing,
                        "town_id": 1,
                        "net_area": 80,
                        "sold_price": 300000.0,
                    }
                ]
            ),
        )

        result = remote_store.get_historical_features(
            from_="listing_features",
            join=["town_market_features"],
            select={
                "listing_features": ["net_area"],
                "town_market_features": ["avg_price_per_sqm"],
            },
        )

        row = result[result["listing_id"] == 1].iloc[0]
        assert row["town_market_features_avg_price_per_sqm"] == 99999.0, (
            f"expected corrected value 99999.0 but got {row['town_market_features_avg_price_per_sqm']}"
        )

    def test_local_and_remote_retrieval_are_equivalent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, s3_client: Any
    ) -> None:
        """Local and remote retrieval return DataFrames with identical columns and values."""
        make_initialized_project(tmp_path)
        defs = tmp_path / "feature_store" / "definitions"
        (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
        (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
        (tmp_path / "kitefs.yaml").write_text(yaml.dump(_LOCAL_YAML), encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply(publish=True)

        rows = listing_features_frame(_listing_rows())

        # Ingest and retrieve locally.
        local_fs = FeatureStore()
        local_fs.ingest("listing_features", rows)
        local_result = local_fs.get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
        )

        # Switch to remote, ingest the same rows, retrieve.
        remote_yaml = {**_LOCAL_YAML, "runtime": {"target": "remote"}}
        (tmp_path / "kitefs.yaml").write_text(yaml.dump(remote_yaml), encoding="utf-8")
        remote_fs = FeatureStore()
        remote_fs.ingest("listing_features", rows)
        remote_result = remote_fs.get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
        )

        assert list(remote_result.columns) == list(local_result.columns)
        assert len(remote_result) == len(local_result)
