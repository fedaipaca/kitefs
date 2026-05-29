"""Step definitions for Feature 2: project scaffold and local configuration."""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from pytest_bdd import given, scenarios, then, when

from kitefs.cli import main

scenarios("../features/feature_2_scaffold.feature")


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Shared mutable context threaded through steps within a scenario."""
    return {}


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def stack() -> Generator[ExitStack, None, None]:
    """ExitStack that lives for the duration of a scenario."""
    with ExitStack() as s:
        yield s


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("an empty working directory")
def _given_empty_dir(ctx: dict[str, Any], runner: CliRunner, stack: ExitStack) -> None:
    stack.enter_context(runner.isolated_filesystem())
    ctx["root"] = Path.cwd()


@given('"kitefs.yaml" already exists with content "project: existing"')
def _given_yaml_exists(ctx: dict[str, Any], runner: CliRunner, stack: ExitStack) -> None:
    stack.enter_context(runner.isolated_filesystem())
    ctx["root"] = Path.cwd()
    (ctx["root"] / "kitefs.yaml").write_text("project: existing", encoding="utf-8")


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when('the user runs "kitefs init"')
def _when_run_init(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["init"])


@when('the user runs "kitefs init-config"')
def _when_run_init_config(ctx: dict[str, Any], runner: CliRunner) -> None:
    ctx["result"] = runner.invoke(main, ["init-config"])


# ---------------------------------------------------------------------------
# Then — exit codes
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
# Then — filesystem assertions
# ---------------------------------------------------------------------------


@then('"kitefs.yaml" exists')
def _then_yaml_exists(ctx: dict[str, Any]) -> None:
    assert (ctx["root"] / "kitefs.yaml").exists()


@then('"feature_store/definitions/" exists')
def _then_definitions_exists(ctx: dict[str, Any]) -> None:
    assert (ctx["root"] / "feature_store" / "definitions").is_dir()


@then('"feature_store/data/offline_store/" exists')
def _then_offline_store_exists(ctx: dict[str, Any]) -> None:
    assert (ctx["root"] / "feature_store" / "data" / "offline_store").is_dir()


@then('"feature_store/data/online_store/" exists')
def _then_online_store_exists(ctx: dict[str, Any]) -> None:
    assert (ctx["root"] / "feature_store" / "data" / "online_store").is_dir()


@then('"feature_store/registry.json" contains an empty registry')
def _then_registry_empty(ctx: dict[str, Any]) -> None:
    content = json.loads((ctx["root"] / "feature_store" / "registry.json").read_text(encoding="utf-8"))
    assert content == {"feature_groups": {}}


@then('".gitignore" contains entries for KiteFS data and registry files')
def _then_gitignore_entries(ctx: dict[str, Any]) -> None:
    text = (ctx["root"] / ".gitignore").read_text(encoding="utf-8")
    assert "feature_store/data/" in text
    assert "feature_store/registry.json" in text


@then('"feature_store/definitions/" contains a Python feature definition file')
def _then_definitions_has_py(ctx: dict[str, Any]) -> None:
    py_files = list((ctx["root"] / "feature_store" / "definitions").glob("*.py"))
    assert py_files, "Expected at least one .py file under feature_store/definitions/"
    ctx["definition_file"] = py_files[0]


@then('the example definition file contains "FeatureGroup"')
def _then_example_contains_feature_group(ctx: dict[str, Any]) -> None:
    text = ctx["definition_file"].read_text(encoding="utf-8")
    assert "FeatureGroup" in text


@then('"feature_store/" does not exist')
def _then_feature_store_absent(ctx: dict[str, Any]) -> None:
    assert not (ctx["root"] / "feature_store").exists()


# ---------------------------------------------------------------------------
# Then — error message assertions
#
# When invoked via `main`, ConfigurationError propagates to CliRunner rather
# than reaching the cli() error boundary. The exception message is the string
# that the error boundary would render to stderr in real CLI usage.
# ---------------------------------------------------------------------------


@then('stderr contains "kitefs.yaml"')
def _then_stderr_has_yaml(ctx: dict[str, Any]) -> None:
    err = str(ctx["result"].exception or "")
    assert "kitefs.yaml" in err, f"Expected 'kitefs.yaml' in error: {err!r}"


@then('stderr contains "already"')
def _then_stderr_has_already(ctx: dict[str, Any]) -> None:
    err = str(ctx["result"].exception or "")
    assert "already" in err, f"Expected 'already' in error: {err!r}"


@then('"kitefs.yaml" still contains "project: existing"')
def _then_yaml_unchanged(ctx: dict[str, Any]) -> None:
    text = (ctx["root"] / "kitefs.yaml").read_text(encoding="utf-8")
    assert "project: existing" in text
