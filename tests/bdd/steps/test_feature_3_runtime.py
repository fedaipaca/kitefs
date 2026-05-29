"""Step definitions for Feature 3: configuration runtime and local provider boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_bdd import given, scenarios, then, when

from kitefs.errors import ConfigurationError
from tests.helpers.tmp_store import make_initialized_project

scenarios("../features/feature_3_runtime.feature")


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


# ---------------------------------------------------------------------------
# Minimal valid remote section used in the override scenario.
# ---------------------------------------------------------------------------

_VALID_REMOTE = {
    "region": "eu-central-1",
    "registry": {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"},
    "offline_store": {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"},
    "online_store": {"type": "aws_dynamodb", "dynamodb_table_prefix": "kitefs_"},
}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("an initialized local project for the reference use case")
def _given_initialized_project(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_initialized_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path


@given('no "kitefs.yaml" exists in the current directory')
def _given_no_yaml(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path


@given('"kitefs.yaml" has runtime.target "staging"')
def _given_yaml_staging_target(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    doc: dict[str, Any] = {
        "version": 1,
        "project": {"name": "testproject"},
        "runtime": {"target": "staging"},
    }
    (tmp_path / "kitefs.yaml").write_text(yaml.dump(doc), encoding="utf-8")


@given('"kitefs.yaml" has runtime.target "local"')
def _given_yaml_local_target(ctx: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ctx["root"] = tmp_path
    ctx["yaml_doc"] = {
        "version": 1,
        "project": {"name": "testproject"},
        "runtime": {"target": "local"},
    }
    (tmp_path / "kitefs.yaml").write_text(yaml.dump(ctx["yaml_doc"]), encoding="utf-8")


@given('the environment variable KITEFS_RUNTIME_TARGET is "remote"')
def _given_env_runtime_target_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITEFS_RUNTIME_TARGET", "remote")


@given("a valid remote section is configured")
def _given_valid_remote(ctx: dict[str, Any]) -> None:
    doc = ctx["yaml_doc"]
    doc["remote"] = _VALID_REMOTE
    (ctx["root"] / "kitefs.yaml").write_text(yaml.dump(doc), encoding="utf-8")


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


@then('the active runtime target is "local"')
def _then_target_local(ctx: dict[str, Any]) -> None:
    assert ctx["instance"].runtime_target == "local"


@then('the active runtime target is "remote"')
def _then_target_remote(ctx: dict[str, Any]) -> None:
    assert ctx["instance"].runtime_target == "remote"


@then('the error message contains "kitefs.yaml"')
def _then_error_has_yaml(ctx: dict[str, Any]) -> None:
    assert "kitefs.yaml" in str(ctx["exception"])


@then('the error message contains "kitefs init"')
def _then_error_has_init(ctx: dict[str, Any]) -> None:
    assert "kitefs init" in str(ctx["exception"])


@then('the error message contains "staging"')
def _then_error_has_staging(ctx: dict[str, Any]) -> None:
    assert "staging" in str(ctx["exception"])


@then('the error message contains "local"')
def _then_error_has_local(ctx: dict[str, Any]) -> None:
    assert "local" in str(ctx["exception"])


@then('the error message contains "remote"')
def _then_error_has_remote(ctx: dict[str, Any]) -> None:
    assert "remote" in str(ctx["exception"])
