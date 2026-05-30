"""Step definitions for Feature 13: remote configuration and AWS provider."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml
from pytest_bdd import given, scenarios, then, when

from kitefs.errors import ConfigurationError, ProviderError

scenarios("../features/feature_13_remote_provider.feature")


@pytest.fixture(autouse=True)
def _use_fake_boto3(fake_boto3: None) -> None:
    """Use fake boto3 for all Feature 13 scenarios by default."""


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


# ---------------------------------------------------------------------------
# Helper — default remote sections used across scenarios
# ---------------------------------------------------------------------------

_DEFAULT_REGISTRY = {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"}
_DEFAULT_ONLINE = {"type": "aws_dynamodb", "dynamodb_table_prefix": "kitefs_"}
_DEFAULT_OFFLINE = {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"}


def _write_yaml(ctx: dict[str, Any]) -> None:
    """Write ctx['yaml_doc'] to <root>/kitefs.yaml."""
    (ctx["root"] / "kitefs.yaml").write_text(yaml.dump(ctx["yaml_doc"]), encoding="utf-8")


def _remote(ctx: dict[str, Any]) -> dict[str, Any]:
    """Return the remote sub-dict, creating it if absent."""
    ctx["yaml_doc"].setdefault("remote", {})
    return ctx["yaml_doc"]["remote"]


# ---------------------------------------------------------------------------
# Given — primary setup (each starts a scenario; chdir + initial YAML)
# ---------------------------------------------------------------------------


@given('runtime.target resolves to "remote"')
def _given_target_resolves_remote(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up an empty remote config; subsequent And steps fill in the fields."""
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    ctx["yaml_doc"] = {
        "version": 1,
        "project": {"name": "testproject"},
        "runtime": {"target": "remote"},
        "remote": {},
    }
    _write_yaml(ctx)


@given('runtime.target is "remote"')
def _given_target_remote(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up a default remote config (region + registry + online, no offline)."""
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    ctx["yaml_doc"] = {
        "version": 1,
        "project": {"name": "testproject"},
        "runtime": {"target": "remote"},
        "remote": {
            "region": "eu-central-1",
            "registry": dict(_DEFAULT_REGISTRY),
            "online_store": dict(_DEFAULT_ONLINE),
        },
    }
    _write_yaml(ctx)


# ---------------------------------------------------------------------------
# Given — field modifiers (build up or adjust the YAML for a scenario)
# ---------------------------------------------------------------------------


@given('remote.region is "eu-central-1"')
def _given_remote_region(ctx: dict[str, Any]) -> None:
    _remote(ctx)["region"] = "eu-central-1"
    _write_yaml(ctx)


@given('remote.registry.type is "aws_s3"')
def _given_registry_type_s3(ctx: dict[str, Any]) -> None:
    _remote(ctx).setdefault("registry", {})["type"] = "aws_s3"
    _write_yaml(ctx)


@given('remote.registry.bucket is "company-ml"')
def _given_registry_bucket(ctx: dict[str, Any]) -> None:
    _remote(ctx).setdefault("registry", {})["bucket"] = "company-ml"
    _write_yaml(ctx)


@given('remote.registry.s3_prefix is "kitefs"')
def _given_registry_prefix(ctx: dict[str, Any]) -> None:
    _remote(ctx).setdefault("registry", {})["s3_prefix"] = "kitefs"
    _write_yaml(ctx)


@given('"kitefs.yaml" has no remote section')
def _given_no_remote_section(ctx: dict[str, Any]) -> None:
    ctx["yaml_doc"].pop("remote", None)
    _write_yaml(ctx)


@given('the remote registry contains "town_market_features"')
def _given_registry_has_group(ctx: dict[str, Any]) -> None:
    """Record the group name; at Feature 13 the registry read is a stub."""
    ctx["feature_group"] = "town_market_features"


@given('remote.online_store.type is "aws_dynamodb"')
def _given_online_type_dynamodb(ctx: dict[str, Any]) -> None:
    _remote(ctx).setdefault("online_store", {})["type"] = "aws_dynamodb"
    _write_yaml(ctx)


@given('remote.online_store.dynamodb_table_prefix is "kitefs_"')
def _given_online_table_prefix(ctx: dict[str, Any]) -> None:
    _remote(ctx).setdefault("online_store", {})["dynamodb_table_prefix"] = "kitefs_"
    _write_yaml(ctx)


@given("remote.offline_store is absent")
def _given_offline_absent(ctx: dict[str, Any]) -> None:
    _remote(ctx).pop("offline_store", None)
    _write_yaml(ctx)


@given('remote.registry.type is "${KITEFS_REMOTE_REGISTRY_TYPE:-aws_s3}"')
def _given_registry_type_interpolated(ctx: dict[str, Any]) -> None:
    # Write the interpolation expression as a plain string; the config loader
    # must reject it before any interpolation takes place.
    _remote(ctx).setdefault("registry", {})["type"] = "${KITEFS_REMOTE_REGISTRY_TYPE:-aws_s3}"
    _write_yaml(ctx)


@given("the AWS extra is not installed")
def _given_no_aws_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block boto3 import so AWSProvider raises ProviderError on construction."""
    monkeypatch.setitem(sys.modules, "boto3", None)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("the user creates FeatureStore()")
def _when_create_feature_store(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    try:
        ctx["instance"] = FeatureStore()
        ctx["exception"] = None
    except Exception as exc:
        ctx["instance"] = None
        ctx["exception"] = exc


@when('the user calls get_online_features for "town_market_features" where town_id equals 1')
def _when_get_online_features(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    store = FeatureStore()
    try:
        ctx["result"] = store.get_online_features(
            from_="town_market_features",
            select=["*"],
            where={"town_id": {"eq": 1}},
        )
        ctx["exception"] = None
    except Exception as exc:
        ctx["result"] = None
        ctx["exception"] = exc


@when('the user calls store.ingest("town_market_features", df)')
def _when_ingest(ctx: dict[str, Any]) -> None:
    from kitefs.sdk.feature_store import FeatureStore

    store = FeatureStore()
    df = pd.DataFrame({"col": [1, 2, 3]})
    try:
        store.ingest("town_market_features", df)
        ctx["exception"] = None
    except Exception as exc:
        ctx["exception"] = exc


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("no exception is raised")
def _then_no_exception(ctx: dict[str, Any]) -> None:
    assert ctx["exception"] is None, f"Unexpected exception: {ctx['exception']}"


@then("ConfigurationError is raised")
def _then_config_error_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exception"], ConfigurationError), (
        f"Expected ConfigurationError, got: {type(ctx['exception'])}: {ctx['exception']}"
    )


@then("ProviderError is raised")
def _then_provider_error_raised(ctx: dict[str, Any]) -> None:
    assert isinstance(ctx["exception"], ProviderError), (
        f"Expected ProviderError, got: {type(ctx['exception'])}: {ctx['exception']}"
    )


@then('the active runtime target is "remote"')
def _then_target_remote(ctx: dict[str, Any]) -> None:
    assert ctx["instance"].runtime_target == "remote"


@then("the active provider is the AWS provider")
def _then_provider_is_aws(ctx: dict[str, Any]) -> None:
    from kitefs.providers.aws import AWSProvider

    assert isinstance(ctx["instance"]._provider, AWSProvider), (
        f"Expected AWSProvider, got: {type(ctx['instance']._provider)}"
    )


@then('the error message contains "remote"')
def _then_error_contains_remote(ctx: dict[str, Any]) -> None:
    assert "remote" in str(ctx["exception"])


@then('the error message contains "remote offline"')
def _then_error_contains_remote_offline(ctx: dict[str, Any]) -> None:
    assert "remote offline" in str(ctx["exception"]), f"Expected 'remote offline' in error, got: {ctx['exception']}"


@then('the error message contains "remote.registry.type"')
def _then_error_contains_registry_type(ctx: dict[str, Any]) -> None:
    assert "remote.registry.type" in str(ctx["exception"]), (
        f"Expected 'remote.registry.type' in error, got: {ctx['exception']}"
    )


@then('the error message contains "literal"')
def _then_error_contains_literal(ctx: dict[str, Any]) -> None:
    assert "literal" in str(ctx["exception"]), f"Expected 'literal' in error, got: {ctx['exception']}"


@then('the error message contains "boto3"')
def _then_error_contains_boto3(ctx: dict[str, Any]) -> None:
    assert "boto3" in str(ctx["exception"]), f"Expected 'boto3' in error, got: {ctx['exception']}"


@then('the error message contains "kitefs[aws]"')
def _then_error_contains_kitefs_aws(ctx: dict[str, Any]) -> None:
    assert "kitefs[aws]" in str(ctx["exception"]), f"Expected 'kitefs[aws]' in error, got: {ctx['exception']}"


@then("no ConfigurationError about offline storage is raised")
def _then_no_offline_config_error(ctx: dict[str, Any]) -> None:
    exc = ctx.get("exception")
    if isinstance(exc, ConfigurationError):
        assert "offline" not in str(exc).lower(), f"Unexpected ConfigurationError about offline storage: {exc}"
