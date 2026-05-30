"""Step definitions for Feature 15: remote S3 offline store ingest and retrieval."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
import pytest
import yaml
from pytest_bdd import given, scenarios, then, when

from kitefs.errors import ConfigurationError
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.aws import create_s3_bucket
from tests.helpers.dataframes import listing_features_frame, town_market_frame
from tests.helpers.tmp_store import make_initialized_project

scenarios("../features/feature_15_remote_offline.feature")

_UTC = datetime.UTC
_REMOTE_REGION = "eu-central-1"

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


def _seed_registry(s3_client: Any, bucket: str, prefix: str, groups: list[str]) -> None:
    """Upload a minimal registry.json to S3 containing the named feature groups."""
    from kitefs.registry.serializer import build_registry_document, serialize_registry_document
    from tests.fixtures.definitions import build_listing_features, build_town_market_features

    builders = {
        "listing_features": build_listing_features,
        "town_market_features": build_town_market_features,
    }
    feature_groups = [builders[g]() for g in groups]
    doc = build_registry_document(
        feature_groups,
        prior_document={"feature_groups": {}},
        now=datetime.datetime(2024, 1, 1, tzinfo=_UTC),
    )
    body = serialize_registry_document(doc).encode("utf-8")
    s3_client.put_object(Bucket=bucket, Key=f"{prefix}/registry.json", Body=body)


def _write_yaml(ctx: dict[str, Any]) -> None:
    (ctx["root"] / "kitefs.yaml").write_text(yaml.dump(ctx["yaml_doc"]), encoding="utf-8")


# ---------------------------------------------------------------------------
# Module-level autouse fixture — all Feature 15 scenarios run under moto
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_mocked_aws(mocked_aws: None) -> None:
    """Use moto-backed AWS clients for all Feature 15 scenarios."""


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


# ---------------------------------------------------------------------------
# Given — remote target with default bucket
# ---------------------------------------------------------------------------


@given('runtime.target resolves to "remote"')
def _given_target_resolves_remote(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up a remote-target project with the default test-bucket."""
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    ctx["s3_bucket"] = "test-bucket"
    ctx["s3_prefix"] = "kitefs"

    ctx["yaml_doc"] = {
        "version": 1,
        "project": {"name": "testproject"},
        "runtime": {"target": "remote"},
        "remote": {
            "region": _REMOTE_REGION,
            "registry": {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"},
            "offline_store": {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"},
            "online_store": {"type": "aws_dynamodb", "dynamodb_table_prefix": "kitefs_"},
        },
    }
    _write_yaml(ctx)

    client = boto3.client("s3", region_name=_REMOTE_REGION)
    create_s3_bucket(client, bucket="test-bucket", region=_REMOTE_REGION)
    ctx["s3_client"] = client


@given('the remote registry contains "town_market_features"')
def _given_registry_has_town_market(ctx: dict[str, Any]) -> None:
    """Seed town_market_features into the S3 registry."""
    _seed_registry(ctx["s3_client"], ctx["s3_bucket"], ctx["s3_prefix"], ["town_market_features"])


@given('the remote offline store is configured at "s3://company-ml/kitefs"')
def _given_offline_store_at_company_ml(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reconfigure kitefs.yaml to use s3://company-ml/kitefs; create the moto bucket."""
    bucket = "company-ml"
    prefix = "kitefs"
    ctx["s3_bucket"] = bucket
    ctx["s3_prefix"] = prefix

    ctx["yaml_doc"]["remote"]["offline_store"] = {"type": "aws_s3", "bucket": bucket, "s3_prefix": prefix}
    _write_yaml(ctx)

    create_s3_bucket(ctx["s3_client"], bucket=bucket, region=_REMOTE_REGION)

    # Re-seed the registry into the company-ml bucket.
    _seed_registry(ctx["s3_client"], ctx["s3_bucket"], ctx["s3_prefix"], ["town_market_features"])

    # Also seed registry in the registry bucket (still test-bucket/kitefs).
    reg = ctx["yaml_doc"]["remote"]["registry"]
    _seed_registry(ctx["s3_client"], reg["bucket"], reg["s3_prefix"], ["town_market_features"])


@given("the input DataFrame contains 6 valid rows with event_timestamp 2024-02-01T00:00:00Z")
def _given_six_row_dataframe(ctx: dict[str, Any]) -> None:
    """Build a 6-row town_market_features DataFrame for 2024-02-01."""
    ts = datetime.datetime(2024, 2, 1, tzinfo=_UTC)
    ctx["df"] = town_market_frame(
        [{"town_id": i, "event_timestamp": ts, "avg_price_per_sqm": 20000.0 + i * 100} for i in range(1, 7)]
    )


# ---------------------------------------------------------------------------
# Given — equivalent local and remote data
# ---------------------------------------------------------------------------


@given('equivalent local and remote offline data exists for "listing_features"')
def _given_local_and_remote_listing_data(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold a project, publish registry, ingest listing data both locally and via remote."""
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    bucket = "test-bucket"
    create_s3_bucket(boto3.client("s3", region_name=_REMOTE_REGION), bucket=bucket, region=_REMOTE_REGION)

    local_yaml = {
        "version": 1,
        "project": {"name": "testproject"},
        "runtime": {"target": "local"},
        "remote": {
            "region": _REMOTE_REGION,
            "registry": {"type": "aws_s3", "bucket": bucket, "s3_prefix": "kitefs"},
            "offline_store": {"type": "aws_s3", "bucket": bucket, "s3_prefix": "kitefs"},
            "online_store": {"type": "aws_dynamodb", "dynamodb_table_prefix": "kitefs_"},
        },
    }
    (tmp_path / "kitefs.yaml").write_text(yaml.dump(local_yaml), encoding="utf-8")
    FeatureStore().apply(publish=True)

    listing_rows = [
        {
            "listing_id": 1,
            "sold_at": datetime.datetime(2024, 3, 10, tzinfo=_UTC),
            "town_id": 1,
            "net_area": 80,
            "sold_price": 300000.0,
        }
    ]

    # Ingest locally.
    local_store = FeatureStore()
    local_store.ingest("listing_features", listing_features_frame(listing_rows))
    ctx["local_result"] = local_store.get_historical_features(
        from_="listing_features",
        select=["net_area", "sold_price"],
    )

    # Switch to remote, ingest, store the store reference for the When step.
    remote_yaml = {**local_yaml, "runtime": {"target": "remote"}}
    (tmp_path / "kitefs.yaml").write_text(yaml.dump(remote_yaml), encoding="utf-8")
    ctx["store"] = FeatureStore()
    ctx["store"].ingest("listing_features", listing_features_frame(listing_rows))


@given('equivalent local and remote offline data exists for "listing_features" and "town_market_features"')
def _given_local_and_remote_joined_data(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold a project with both groups, publish registry, ingest into remote store."""
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    bucket = "test-bucket"
    create_s3_bucket(boto3.client("s3", region_name=_REMOTE_REGION), bucket=bucket, region=_REMOTE_REGION)

    local_yaml = {
        "version": 1,
        "project": {"name": "testproject"},
        "runtime": {"target": "local"},
        "remote": {
            "region": _REMOTE_REGION,
            "registry": {"type": "aws_s3", "bucket": bucket, "s3_prefix": "kitefs"},
            "offline_store": {"type": "aws_s3", "bucket": bucket, "s3_prefix": "kitefs"},
            "online_store": {"type": "aws_dynamodb", "dynamodb_table_prefix": "kitefs_"},
        },
    }
    (tmp_path / "kitefs.yaml").write_text(yaml.dump(local_yaml), encoding="utf-8")
    FeatureStore().apply(publish=True)

    market_rows = [
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 2, 1, tzinfo=_UTC), "avg_price_per_sqm": 20000.0},
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 4, 1, tzinfo=_UTC), "avg_price_per_sqm": 25400.0},
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 5, 1, tzinfo=_UTC), "avg_price_per_sqm": 30000.0},
    ]
    listing_rows = [
        {
            "listing_id": 1002,
            "sold_at": datetime.datetime(2024, 4, 5, tzinfo=_UTC),
            "town_id": 1,
            "net_area": 90,
            "sold_price": 410000.0,
        }
    ]

    remote_yaml = {**local_yaml, "runtime": {"target": "remote"}}
    (tmp_path / "kitefs.yaml").write_text(yaml.dump(remote_yaml), encoding="utf-8")
    ctx["store"] = FeatureStore()
    ctx["store"].ingest("town_market_features", town_market_frame(market_rows))
    ctx["store"].ingest("listing_features", listing_features_frame(listing_rows))


# ---------------------------------------------------------------------------
# Given — empty offline prefix scenario
# ---------------------------------------------------------------------------


@given('"listing_features" is registered')
def _given_listing_features_registered(ctx: dict[str, Any]) -> None:
    """Seed listing_features and town_market_features into the S3 registry."""
    _seed_registry(ctx["s3_client"], ctx["s3_bucket"], ctx["s3_prefix"], ["listing_features", "town_market_features"])


@given('no S3 objects exist under the offline prefix for "listing_features"')
def _given_no_offline_objects(ctx: dict[str, Any]) -> None:
    """Nothing to do — the offline prefix is already empty by default."""


# ---------------------------------------------------------------------------
# Given — missing offline bucket scenario
# ---------------------------------------------------------------------------


@given("remote.offline_store.bucket is empty")
def _given_offline_bucket_empty(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reconfigure kitefs.yaml so that remote.offline_store.bucket is absent."""
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path

    # Seed registry so ConfigurationError fires at offline validation, not registry read.
    _seed_registry(ctx["s3_client"], ctx["s3_bucket"], ctx["s3_prefix"], ["town_market_features"])

    ctx["yaml_doc"]["remote"]["offline_store"]["bucket"] = ""
    _write_yaml(ctx)

    ctx["df"] = town_market_frame(
        [{"town_id": 1, "event_timestamp": datetime.datetime(2024, 2, 1, tzinfo=_UTC), "avg_price_per_sqm": 20000.0}]
    )


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when('the user calls store.ingest("town_market_features", df)')
def _when_ingest_town_market(ctx: dict[str, Any]) -> None:
    """Call ingest and capture result or exception."""
    ctx["exc"] = None
    try:
        ctx["result"] = FeatureStore().ingest("town_market_features", ctx["df"])
    except Exception as exc:
        ctx["exc"] = exc


@when('the user retrieves "net_area" and "sold_price" from "listing_features" using the remote runtime')
def _when_retrieve_listing_remote(ctx: dict[str, Any]) -> None:
    """Call get_historical_features on the remote store for listing_features."""
    ctx["exc"] = None
    try:
        ctx["result"] = ctx["store"].get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
        )
    except Exception as exc:
        ctx["exc"] = exc


@when('the user retrieves "listing_features" joined to "town_market_features" using the remote runtime')
def _when_retrieve_joined_remote(ctx: dict[str, Any]) -> None:
    """Call get_historical_features with a join on the remote store."""
    ctx["exc"] = None
    try:
        ctx["result"] = ctx["store"].get_historical_features(
            from_="listing_features",
            join=["town_market_features"],
            select={
                "listing_features": ["net_area", "sold_price"],
                "town_market_features": ["avg_price_per_sqm"],
            },
        )
    except Exception as exc:
        ctx["exc"] = exc


@when('the user retrieves "net_area" and "sold_price" from "listing_features"')
def _when_retrieve_listing_empty(ctx: dict[str, Any]) -> None:
    """Call get_historical_features against an empty offline store."""
    ctx["exc"] = None
    try:
        ctx["result"] = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
        )
    except Exception as exc:
        ctx["exc"] = exc


# ---------------------------------------------------------------------------
# Then — general
# ---------------------------------------------------------------------------


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    """Assert that no exception was captured during the When step."""
    assert ctx["exc"] is None, f"unexpected exception: {ctx['exc']}"


@then("ConfigurationError is raised")
def _then_config_error_raised(ctx: dict[str, Any]) -> None:
    """Assert that a ConfigurationError was raised."""
    assert isinstance(ctx["exc"], ConfigurationError), f"expected ConfigurationError, got {ctx['exc']!r}"


@then('the error message contains "remote offline"')
def _then_error_contains_remote_offline(ctx: dict[str, Any]) -> None:
    """Assert that the error message references the remote offline store."""
    assert "offline" in str(ctx["exc"]).lower(), str(ctx["exc"])


@then('the error message contains "bucket"')
def _then_error_contains_bucket(ctx: dict[str, Any]) -> None:
    """Assert that the error message names the bucket setting."""
    assert "bucket" in str(ctx["exc"]).lower(), str(ctx["exc"])


# ---------------------------------------------------------------------------
# Then — ingest
# ---------------------------------------------------------------------------


@then("result.accepted_rows is 6")
def _then_accepted_rows_six(ctx: dict[str, Any]) -> None:
    """Assert that accepted_rows equals 6."""
    assert ctx["result"].accepted_rows == 6


@then("result.written_files contains exactly 1 S3 URI")
def _then_written_files_one_uri(ctx: dict[str, Any]) -> None:
    """Assert that exactly one S3 URI was returned."""
    assert len(ctx["result"].written_files) == 1
    assert ctx["result"].written_files[0].startswith("s3://")


@then('the S3 URI starts with "s3://company-ml/kitefs/data/offline_store/town_market_features/year=2024/month=02/"')
def _then_s3_uri_correct_prefix(ctx: dict[str, Any]) -> None:
    """Assert that the written S3 URI has the expected partition path."""
    uri = ctx["result"].written_files[0]
    expected = "s3://company-ml/kitefs/data/offline_store/town_market_features/year=2024/month=02/"
    assert uri.startswith(expected), f"URI {uri!r} does not start with {expected!r}"


# ---------------------------------------------------------------------------
# Then — retrieval
# ---------------------------------------------------------------------------


@then("the returned columns match the local result columns")
def _then_columns_match_local(ctx: dict[str, Any]) -> None:
    """Assert that remote retrieval columns equal local retrieval columns in order."""
    assert isinstance(ctx["result"], pd.DataFrame)
    assert list(ctx["result"].columns) == list(ctx["local_result"].columns)


@then("listing_id 1002 has town_market_features_event_timestamp 2024-04-01T00:00:00Z")
def _then_listing_1002_event_ts(ctx: dict[str, Any]) -> None:
    """Assert point-in-time join selected the 2024-04-01 market snapshot."""
    result = ctx["result"]
    row = result[result["listing_id"] == 1002].iloc[0]
    assert row["town_market_features_event_timestamp"] == datetime.datetime(2024, 4, 1, 0, 0, 0)


@then("listing_id 1002 has town_market_features_avg_price_per_sqm 25400.0")
def _then_listing_1002_avg_price(ctx: dict[str, Any]) -> None:
    """Assert the correct avg_price_per_sqm was joined for listing 1002."""
    result = ctx["result"]
    row = result[result["listing_id"] == 1002].iloc[0]
    assert row["town_market_features_avg_price_per_sqm"] == 25400.0


@then("the result has zero rows")
def _then_zero_rows(ctx: dict[str, Any]) -> None:
    """Assert the returned DataFrame is empty."""
    assert isinstance(ctx["result"], pd.DataFrame)
    assert len(ctx["result"]) == 0
