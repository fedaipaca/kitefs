"""Step definitions for Feature 16: remote DynamoDB online store materialize and retrieval."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import boto3
import pytest
import yaml
from botocore.exceptions import ClientError
from pytest_bdd import given, scenarios, then, when

from kitefs.constants import DATETIME_FMT
from kitefs.errors import ConfigurationError, OnlineStoreReadError
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.aws import create_dynamodb_table, create_s3_bucket
from tests.helpers.dataframes import town_market_frame

scenarios("../features/feature_16_remote_online.feature")

_UTC = datetime.UTC
_REMOTE_REGION = "eu-central-1"
_S3_BUCKET = "test-bucket"
_S3_PREFIX = "kitefs"
_DYNAMO_PREFIX = "kitefs_"
_GROUP = "town_market_features"
_TABLE = f"{_DYNAMO_PREFIX}{_GROUP}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_remote_yaml(*, online_store: dict[str, Any] | None = "default") -> dict[str, Any]:
    """Build the kitefs.yaml dict for a remote target.

    Pass online_store=None to omit the remote.online_store section entirely
    (used to test the 'missing config' BDD scenario).
    """
    remote: dict[str, Any] = {
        "region": _REMOTE_REGION,
        "registry": {"type": "aws_s3", "bucket": _S3_BUCKET, "s3_prefix": _S3_PREFIX},
        "offline_store": {"type": "aws_s3", "bucket": _S3_BUCKET, "s3_prefix": _S3_PREFIX},
    }
    if online_store == "default":
        remote["online_store"] = {"type": "aws_dynamodb", "dynamodb_table_prefix": _DYNAMO_PREFIX}
    elif online_store is not None:
        remote["online_store"] = online_store

    return {
        "version": 1,
        "project": {"name": "testproject"},
        "runtime": {"target": "remote"},
        "remote": remote,
    }


def _write_yaml(ctx: dict[str, Any]) -> None:
    (ctx["root"] / "kitefs.yaml").write_text(yaml.dump(ctx["yaml_doc"]), encoding="utf-8")


def _seed_registry(s3_client: Any, bucket: str, prefix: str) -> None:
    """Upload a minimal registry.json containing town_market_features to S3.

    Also writes the same document to the local working registry so that
    remote materialize can update last_materialized_at locally (spec FR-MAT-001).
    """
    from kitefs.registry.serializer import build_registry_document, serialize_registry_document
    from tests.fixtures.definitions import build_town_market_features

    doc = build_registry_document(
        [build_town_market_features()],
        prior_document={"feature_groups": {}},
        now=datetime.datetime(2024, 1, 1, tzinfo=_UTC),
    )
    body = serialize_registry_document(doc).encode("utf-8")
    s3_client.put_object(Bucket=bucket, Key=f"{prefix}/registry.json", Body=body)

    # Mirror the document to the local working registry.  The real producer
    # workflow runs apply() (which writes locally) before apply --publish;
    # without this, remote materialize cannot find the local registry to stamp.
    local_registry = Path.cwd() / "feature_store" / "registry.json"
    local_registry.parent.mkdir(parents=True, exist_ok=True)
    local_registry.write_text(serialize_registry_document(doc), encoding="utf-8")


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "GetItem")


# ---------------------------------------------------------------------------
# Module-level autouse fixture — all Feature 16 scenarios run under moto
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_mocked_aws(mocked_aws: None) -> None:
    """Use moto-backed AWS clients for all Feature 16 scenarios."""


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


# ---------------------------------------------------------------------------
# Given — shared remote target setup
# ---------------------------------------------------------------------------


@given('runtime.target resolves to "remote"')
def _given_target_resolves_remote(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up a remote-target project with S3 + DynamoDB in moto."""
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    ctx["yaml_doc"] = _make_remote_yaml()
    _write_yaml(ctx)

    s3_client = boto3.client("s3", region_name=_REMOTE_REGION)
    create_s3_bucket(s3_client, bucket=_S3_BUCKET, region=_REMOTE_REGION)
    ctx["s3_client"] = s3_client
    ctx["dynamodb_client"] = boto3.client("dynamodb", region_name=_REMOTE_REGION)


@given('remote offline data exists for "town_market_features" with 72 rows for 12 months and 6 towns')
def _given_72_rows_remote(ctx: dict[str, Any]) -> None:
    """Seed the S3 registry and ingest 72 rows (6 towns x 12 months) via FeatureStore.ingest."""
    _seed_registry(ctx["s3_client"], _S3_BUCKET, _S3_PREFIX)

    rows: list[dict[str, Any]] = []
    for month in range(1, 13):
        for town_id in range(1, 7):
            rows.append(
                {
                    "town_id": town_id,
                    "event_timestamp": datetime.datetime(2025, month, 1, tzinfo=_UTC),
                    "avg_price_per_sqm": float(10000 + town_id * 100 + month * 10),
                }
            )

    store = FeatureStore()
    store.ingest(_GROUP, town_market_frame(rows))
    ctx["rows"] = rows


@given('the remote online store table prefix is "kitefs_"')
def _given_table_prefix(ctx: dict[str, Any]) -> None:
    """No-op — the prefix is already baked into the yaml_doc by the remote setup step."""


@given('remote offline data exists for "town_market_features"')
def _given_offline_data_remote(ctx: dict[str, Any]) -> None:
    """Seed the S3 registry and ingest a minimal offline dataset."""
    _seed_registry(ctx["s3_client"], _S3_BUCKET, _S3_PREFIX)

    rows = [
        {
            "town_id": i,
            "event_timestamp": datetime.datetime(2025, 7, 1, tzinfo=_UTC),
            "avg_price_per_sqm": float(10000 + i * 100),
        }
        for i in range(1, 4)
    ]
    FeatureStore().ingest(_GROUP, town_market_frame(rows))
    ctx["rows"] = rows


@given('the remote online table for "town_market_features" has partition key "city_id"')
def _given_wrong_partition_key(ctx: dict[str, Any]) -> None:
    """Create the DynamoDB table with a mismatched partition key name."""
    create_dynamodb_table(ctx["dynamodb_client"], table_name=_TABLE, hash_key="city_id", key_type="N")


@given("the remote online store has town_id 5, avg_price_per_sqm 15200.0, event_timestamp 2025-07-01T00:00:00.000000Z")
def _given_online_hit(ctx: dict[str, Any]) -> None:
    """Seed the S3 registry and a matching DynamoDB item for town_id 5."""
    _seed_registry(ctx["s3_client"], _S3_BUCKET, _S3_PREFIX)

    # Pre-create the table and insert an item in DynamoDB wire format.
    create_dynamodb_table(ctx["dynamodb_client"], table_name=_TABLE, hash_key="town_id", key_type="N")

    ts_str = datetime.datetime(2025, 7, 1, tzinfo=_UTC).strftime(DATETIME_FMT)
    ctx["dynamodb_client"].put_item(
        TableName=_TABLE,
        Item={
            "town_id": {"N": "5"},
            "event_timestamp": {"S": ts_str},
            "avg_price_per_sqm": {"N": "15200.0"},
        },
    )


@given("the remote online store has no item for town_id 999")
def _given_online_miss(ctx: dict[str, Any]) -> None:
    """Seed registry; create table but leave no item for town_id 999."""
    _seed_registry(ctx["s3_client"], _S3_BUCKET, _S3_PREFIX)
    create_dynamodb_table(ctx["dynamodb_client"], table_name=_TABLE, hash_key="town_id", key_type="N")


@given('"town_market_features" has never been materialized to the remote online store')
def _given_never_materialized(ctx: dict[str, Any]) -> None:
    """Seed registry but do NOT create the DynamoDB table."""
    _seed_registry(ctx["s3_client"], _S3_BUCKET, _S3_PREFIX)


@given("remote.online_store is absent")
def _given_no_online_config(ctx: dict[str, Any]) -> None:
    """Drop online_store from the yaml to trigger ConfigurationError."""
    ctx["yaml_doc"] = _make_remote_yaml(online_store=None)
    _write_yaml(ctx)
    _seed_registry(ctx["s3_client"], _S3_BUCKET, _S3_PREFIX)


@given('"town_market_features" is registered as online-capable')
def _given_registered_online_capable(ctx: dict[str, Any]) -> None:
    """Seed the S3 registry with town_market_features."""
    _seed_registry(ctx["s3_client"], _S3_BUCKET, _S3_PREFIX)


@given('the remote online read fails with "AccessDenied"')
def _given_read_fails_access_denied(ctx: dict[str, Any]) -> None:
    """Store a monkeypatch sentinel — the actual patch is applied in the When step."""
    ctx["inject_read_error"] = True


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when('the user calls store.materialize("town_market_features")')
def _when_materialize(ctx: dict[str, Any]) -> None:
    """Call FeatureStore.materialize and capture result or exception."""
    store = FeatureStore()
    try:
        ctx["result"] = store.materialize(_GROUP)
        ctx["exc"] = None
    except Exception as exc:
        ctx["exc"] = exc
        ctx["result"] = None


@when('the user gets online features from "town_market_features" with select ["avg_price_per_sqm"] where town_id is 5')
def _when_get_town_5(ctx: dict[str, Any]) -> None:
    """Call get_online_features for town_id=5 and capture result or exception."""
    store = FeatureStore()
    try:
        ctx["result"] = store.get_online_features(
            from_=_GROUP,
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 5}},
        )
        ctx["exc"] = None
    except Exception as exc:
        ctx["exc"] = exc
        ctx["result"] = None


@when('the user gets online features from "town_market_features" selecting ["avg_price_per_sqm"] where town_id is 999')
def _when_get_town_999(ctx: dict[str, Any]) -> None:
    """Call get_online_features for town_id=999 (expected miss)."""
    store = FeatureStore()
    try:
        ctx["result"] = store.get_online_features(
            from_=_GROUP,
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 999}},
        )
        ctx["exc"] = None
    except Exception as exc:
        ctx["exc"] = exc
        ctx["result"] = None


@when('the user gets online features from "town_market_features" with select ["avg_price_per_sqm"] where town_id is 1')
def _when_get_town_1(ctx: dict[str, Any]) -> None:
    """Call get_online_features for town_id=1; patches GetItem if ctx signals a read error."""
    store = FeatureStore()
    if ctx.get("inject_read_error"):
        # Monkeypatch the underlying boto3 client's get_item to raise AccessDenied.
        store._provider._dynamodb.get_item = MagicMock(side_effect=_make_client_error("AccessDenied"))

    try:
        ctx["result"] = store.get_online_features(
            from_=_GROUP,
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 1}},
        )
        ctx["exc"] = None
    except Exception as exc:
        ctx["exc"] = exc
        ctx["result"] = None


# ---------------------------------------------------------------------------
# Then — generic
# ---------------------------------------------------------------------------


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    """Assert that no exception was recorded in the when step."""
    assert ctx["exc"] is None, f"Expected no exception but got: {ctx['exc']}"


@then("ConfigurationError is raised")
def _then_config_error(ctx: dict[str, Any]) -> None:
    """Assert that a ConfigurationError was raised."""
    assert isinstance(ctx["exc"], ConfigurationError), f"Expected ConfigurationError, got: {ctx['exc']!r}"


@then("OnlineStoreReadError is raised")
def _then_read_error(ctx: dict[str, Any]) -> None:
    """Assert that an OnlineStoreReadError was raised."""
    assert isinstance(ctx["exc"], OnlineStoreReadError), f"Expected OnlineStoreReadError, got: {ctx['exc']!r}"


@then('the error message contains "remote online"')
def _then_error_contains_remote_online(ctx: dict[str, Any]) -> None:
    """Assert 'remote online' appears in the exception message."""
    assert "remote online" in str(ctx["exc"]).lower(), f"'remote online' not in: {ctx['exc']}"


@then('the error message contains "AccessDenied"')
def _then_error_contains_access_denied(ctx: dict[str, Any]) -> None:
    """Assert 'AccessDenied' appears in the exception message."""
    assert "AccessDenied" in str(ctx["exc"]), f"'AccessDenied' not in: {ctx['exc']}"


# ---------------------------------------------------------------------------
# Then — materialize result
# ---------------------------------------------------------------------------


@then('result.succeeded contains "town_market_features"')
def _then_succeeded_contains_group(ctx: dict[str, Any]) -> None:
    """Assert the group name appears in MaterializeResult.succeeded."""
    assert _GROUP in ctx["result"].succeeded, f"succeeded={ctx['result'].succeeded}"


@then("a later online lookup for each town returns that town's latest market row")
def _then_each_town_latest(ctx: dict[str, Any]) -> None:
    """Verify each of the 6 towns returns a row with the latest event_timestamp and price."""
    store = FeatureStore()
    for town_id in range(1, 7):
        result = store.get_online_features(
            from_=_GROUP,
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": town_id}},
        )
        assert result, f"Expected a hit for town_id={town_id}, got {{}}"
        assert result["town_id"] == town_id

        # The latest row for each town is from month=12 (December 2025).
        expected_ts = datetime.datetime(2025, 12, 1, tzinfo=_UTC)
        assert result["event_timestamp"] == expected_ts, (
            f"town_id={town_id}: expected {expected_ts}, got {result['event_timestamp']}"
        )


@then('result.failed contains a group named "town_market_features"')
def _then_failed_contains_group(ctx: dict[str, Any]) -> None:
    """Assert the group name appears in MaterializeResult.failed."""
    failed_names = [f.name for f in ctx["result"].failed]
    assert _GROUP in failed_names, f"failed={failed_names}"


@then('the failure message contains "partition key"')
def _then_failure_contains_partition_key(ctx: dict[str, Any]) -> None:
    """Assert 'partition key' appears in the FailedGroup error_message."""
    failed = next(f for f in ctx["result"].failed if f.name == _GROUP)
    assert "partition key" in failed.error_message, f"message={failed.error_message!r}"


@then('the failure message contains "town_id"')
def _then_failure_contains_town_id(ctx: dict[str, Any]) -> None:
    """Assert 'town_id' appears in the FailedGroup error_message."""
    failed = next(f for f in ctx["result"].failed if f.name == _GROUP)
    assert "town_id" in failed.error_message, f"message={failed.error_message!r}"


# ---------------------------------------------------------------------------
# Then — get_online_features result
# ---------------------------------------------------------------------------


@then("the result is {}")
def _then_result_is_empty(ctx: dict[str, Any]) -> None:
    """Assert the returned dict is empty."""
    assert ctx["result"] == {}, f"Expected {{}}, got {ctx['result']}"


@then("the result contains town_id 5")
def _then_result_town_id_5(ctx: dict[str, Any]) -> None:
    """Assert the result includes town_id=5."""
    assert ctx["result"].get("town_id") == 5, f"town_id not 5: {ctx['result']}"


@then("the result contains avg_price_per_sqm 15200.0")
def _then_result_price(ctx: dict[str, Any]) -> None:
    """Assert the result includes avg_price_per_sqm as a float equal to 15200.0."""
    price = ctx["result"].get("avg_price_per_sqm")
    assert isinstance(price, float), f"expected float, got {type(price).__name__}: {price!r}"
    assert price == 15200.0, f"avg_price_per_sqm not 15200.0: {ctx['result']}"


@then("the result contains event_timestamp 2025-07-01T00:00:00Z")
def _then_result_event_timestamp(ctx: dict[str, Any]) -> None:
    """Assert the result includes event_timestamp as a UTC-aware datetime for 2025-07-01."""
    ts = ctx["result"].get("event_timestamp")
    expected = datetime.datetime(2025, 7, 1, tzinfo=_UTC)
    assert ts == expected, f"event_timestamp mismatch: {ts!r} != {expected!r}"
