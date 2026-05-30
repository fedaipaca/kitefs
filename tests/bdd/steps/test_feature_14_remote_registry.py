"""Step definitions for Feature 14: remote registry publish, list, and describe (S3)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
import pytest
import yaml
from click.testing import CliRunner
from pytest_bdd import given, scenarios, then, when

from kitefs.cli import main
from tests.helpers.aws import create_s3_bucket
from tests.helpers.tmp_store import make_initialized_project

scenarios("../features/feature_14_remote_registry.feature")

# ---------------------------------------------------------------------------
# Inline definition sources (identical to integration tests)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Default remote config sections
# ---------------------------------------------------------------------------

_REMOTE_REGION = "eu-central-1"
_DEFAULT_REGISTRY = {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"}
_DEFAULT_OFFLINE = {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"}
_DEFAULT_ONLINE = {"type": "aws_dynamodb", "dynamodb_table_prefix": "kitefs_"}


def _write_yaml(ctx: dict[str, Any]) -> None:
    """Write ctx['yaml_doc'] to <root>/kitefs.yaml."""
    (ctx["root"] / "kitefs.yaml").write_text(yaml.dump(ctx["yaml_doc"]), encoding="utf-8")


def _remote(ctx: dict[str, Any]) -> dict[str, Any]:
    """Return the remote sub-dict from ctx['yaml_doc'], creating it if absent."""
    ctx["yaml_doc"].setdefault("remote", {})
    return ctx["yaml_doc"]["remote"]


def _seed_s3_registry(s3_client: Any, bucket: str, prefix: str, groups: list[str]) -> None:
    """Upload a minimal registry.json to S3 containing the named groups."""
    from kitefs.registry.serializer import serialize_registry_document
    from tests.fixtures.definitions import build_listing_features, build_town_market_features

    builders = {
        "listing_features": build_listing_features,
        "town_market_features": build_town_market_features,
    }
    feature_groups = [builders[g]() for g in groups]

    from kitefs.registry.serializer import build_registry_document

    doc = build_registry_document(
        feature_groups,
        prior_document={"feature_groups": {}},
        now=datetime(2024, 1, 1, tzinfo=UTC),
    )
    body = serialize_registry_document(doc).encode("utf-8")
    s3_client.put_object(Bucket=bucket, Key=f"{prefix}/registry.json", Body=body)


# ---------------------------------------------------------------------------
# Module-level autouse fixture — all Feature 14 scenarios run under moto
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_mocked_aws(mocked_aws: None) -> None:
    """Use moto-backed AWS clients for all Feature 14 scenarios."""


# ---------------------------------------------------------------------------
# Shared context and runner fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Given — publish scenario
# ---------------------------------------------------------------------------


@given('valid local definitions for "listing_features" and "town_market_features"')
def _given_local_definitions(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold a producer project with both definition files."""
    make_initialized_project(tmp_path)
    defs = tmp_path / "feature_store" / "definitions"
    (defs / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path


@given('the remote registry is configured at "s3://company-ml/kitefs/registry.json"')
def _given_remote_registry_at_company_ml(ctx: dict[str, Any]) -> None:
    """Write kitefs.yaml pointing at s3://company-ml/kitefs; create the moto bucket."""
    bucket = "company-ml"
    prefix = "kitefs"
    ctx["s3_bucket"] = bucket
    ctx["s3_prefix"] = prefix

    yaml_doc = {
        "version": 1,
        "project": {"name": "kitefs_featurestore_project"},
        "runtime": {"target": "local"},
        "remote": {
            "region": _REMOTE_REGION,
            "registry": {"type": "aws_s3", "bucket": bucket, "s3_prefix": prefix},
            "offline_store": {"type": "aws_s3", "bucket": bucket, "s3_prefix": prefix},
            "online_store": {"type": "aws_dynamodb", "dynamodb_table_prefix": "kitefs_"},
        },
    }
    (ctx["root"] / "kitefs.yaml").write_text(yaml.dump(yaml_doc), encoding="utf-8")

    client = boto3.client("s3", region_name=_REMOTE_REGION)
    create_s3_bucket(client, bucket=bucket, region=_REMOTE_REGION)
    ctx["s3_client"] = client


# ---------------------------------------------------------------------------
# Given — consumer scenarios (runtime.target: remote)
# ---------------------------------------------------------------------------


@given('runtime.target resolves to "remote"')
def _given_target_resolves_remote(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up a remote-target project with the default test-bucket; create the moto bucket."""
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
            "registry": dict(_DEFAULT_REGISTRY),
            "offline_store": dict(_DEFAULT_OFFLINE),
            "online_store": dict(_DEFAULT_ONLINE),
        },
    }
    _write_yaml(ctx)

    client = boto3.client("s3", region_name=_REMOTE_REGION)
    create_s3_bucket(client, bucket="test-bucket", region=_REMOTE_REGION)
    ctx["s3_client"] = client


@given('the S3 registry contains "listing_features" and "town_market_features"')
def _given_s3_has_both_groups(ctx: dict[str, Any]) -> None:
    """Seed both groups into the S3 registry."""
    _seed_s3_registry(
        ctx["s3_client"], ctx["s3_bucket"], ctx["s3_prefix"], ["listing_features", "town_market_features"]
    )


@given('the S3 registry contains "town_market_features"')
def _given_s3_has_town_market(ctx: dict[str, Any]) -> None:
    """Seed only town_market_features into the S3 registry."""
    _seed_s3_registry(ctx["s3_client"], ctx["s3_bucket"], ctx["s3_prefix"], ["town_market_features"])


@given("the S3 registry object does not exist")
def _given_s3_registry_absent(ctx: dict[str, Any]) -> None:
    """Leave the S3 bucket empty — no registry.json object."""
    # Bucket was created in the given("runtime.target resolves to remote") step.
    # Nothing to do; the object simply doesn't exist.


@given('the S3 registry contains only "listing_features" and "town_market_features"')
def _given_s3_has_only_both(ctx: dict[str, Any]) -> None:
    """Seed both groups (and nothing else) into the S3 registry."""
    _seed_s3_registry(
        ctx["s3_client"], ctx["s3_bucket"], ctx["s3_prefix"], ["listing_features", "town_market_features"]
    )


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("the user calls FeatureStore().apply(publish=True)")
def _when_apply_publish(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    try:
        ctx["result_obj"] = FeatureStore().apply(publish=True)
        ctx["exception"] = None
    except Exception as exc:
        ctx["result_obj"] = None
        ctx["exception"] = exc


@when('the user runs "kitefs list"')
def _when_list(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["list"])


@when('the user runs "kitefs describe town_market_features --format json"')
def _when_describe_json(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["describe", "town_market_features", "--format", "json"])


@when('the user runs "kitefs describe neighborhood_features"')
def _when_describe_unknown(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["describe", "neighborhood_features"])


# ---------------------------------------------------------------------------
# Then — apply result assertions
# ---------------------------------------------------------------------------


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    assert ctx["exception"] is None, f"Unexpected exception: {ctx['exception']}"


@then('result.registered_groups equals ["listing_features", "town_market_features"]')
def _then_registered_groups(ctx: dict[str, Any]) -> None:
    assert ctx["result_obj"].registered_groups == ["listing_features", "town_market_features"]


@then("result.published is True")
def _then_published_true(ctx: dict[str, Any]) -> None:
    assert ctx["result_obj"].published is True


@then('the S3 registry object contains "listing_features"')
def _then_s3_has_listing(ctx: dict[str, Any]) -> None:
    body = ctx["s3_client"].get_object(Bucket=ctx["s3_bucket"], Key=f"{ctx['s3_prefix']}/registry.json")["Body"].read()
    assert b"listing_features" in body


@then('the S3 registry object contains "town_market_features"')
def _then_s3_has_town_market(ctx: dict[str, Any]) -> None:
    body = ctx["s3_client"].get_object(Bucket=ctx["s3_bucket"], Key=f"{ctx['s3_prefix']}/registry.json")["Body"].read()
    assert b"town_market_features" in body


# ---------------------------------------------------------------------------
# Then — CLI exit codes
# ---------------------------------------------------------------------------


@then("the command exits 0")
def _then_exits_0(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}.\nOutput: {result.output}"


@then("the command exits non-zero")
def _then_exits_nonzero(ctx: dict[str, Any]) -> None:
    result = ctx["result"]
    assert result.exit_code != 0, f"Expected non-zero exit, got 0.\nOutput: {result.output}"


# ---------------------------------------------------------------------------
# Then — stdout assertions
# ---------------------------------------------------------------------------


@then('stdout contains "listing_features"')
def _then_stdout_has_listing(ctx: dict[str, Any]) -> None:
    assert "listing_features" in ctx["result"].output


@then('stdout contains "town_market_features"')
def _then_stdout_has_town_market(ctx: dict[str, Any]) -> None:
    assert "town_market_features" in ctx["result"].output


@then("stdout is a JSON object")
def _then_stdout_is_json_object(ctx: dict[str, Any]) -> None:
    data = json.loads(ctx["result"].output.strip())
    assert isinstance(data, dict), f"Expected a JSON object, got: {type(data)}"
    ctx["json_output"] = data


@then('the JSON output has entity_key.name "town_id"')
def _then_json_entity_key_name(ctx: dict[str, Any]) -> None:
    data = ctx.get("json_output") or json.loads(ctx["result"].output.strip())
    assert data["entity_key"]["name"] == "town_id"


@then('the JSON output has storage_target "OFFLINE_AND_ONLINE"')
def _then_json_storage_target(ctx: dict[str, Any]) -> None:
    data = ctx.get("json_output") or json.loads(ctx["result"].output.strip())
    assert data["storage_target"] == "OFFLINE_AND_ONLINE"


# ---------------------------------------------------------------------------
# Then — stderr assertions
#
# When invoked via CliRunner.invoke(main, ...), KiteFSError propagates as
# result.exception rather than reaching the cli() boundary.  The exception type
# carries the class name and str(exception) carries the message text — both are
# checked here to mirror what the cli() boundary would render to stderr.
# ---------------------------------------------------------------------------


@then('stderr contains "RegistryReadError"')
def _then_stderr_has_registry_read_error(ctx: dict[str, Any]) -> None:
    exc = ctx["result"].exception
    assert exc is not None, "Expected an exception but none was raised"
    assert type(exc).__name__ == "RegistryReadError", f"Expected RegistryReadError, got {type(exc).__name__}: {exc}"


@then('stderr contains "apply --publish"')
def _then_stderr_has_apply_publish(ctx: dict[str, Any]) -> None:
    exc = ctx["result"].exception
    assert exc is not None, "Expected an exception but none was raised"
    assert "apply --publish" in str(exc), f"Expected 'apply --publish' in: {str(exc)!r}"


@then('stderr contains "FeatureGroupNotFoundError"')
def _then_stderr_has_feature_group_not_found(ctx: dict[str, Any]) -> None:
    exc = ctx["result"].exception
    assert exc is not None, "Expected an exception but none was raised"
    assert type(exc).__name__ == "FeatureGroupNotFoundError", (
        f"Expected FeatureGroupNotFoundError, got {type(exc).__name__}: {exc}"
    )


@then('stderr contains "neighborhood_features"')
def _then_stderr_has_neighborhood(ctx: dict[str, Any]) -> None:
    exc = ctx["result"].exception
    assert exc is not None
    assert "neighborhood_features" in str(exc), f"Expected 'neighborhood_features' in: {str(exc)!r}"


@then('stderr contains "listing_features"')
def _then_stderr_has_listing_err(ctx: dict[str, Any]) -> None:
    exc = ctx["result"].exception
    assert exc is not None
    assert "listing_features" in str(exc), f"Expected 'listing_features' in: {str(exc)!r}"
