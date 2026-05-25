"""Integration tests for `kitefs init-config` — consumer scaffold CLI command."""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from kitefs.cli import main
from kitefs.errors import ConfigurationError


class TestInitConfigHappyPath:
    """kitefs init-config creates only kitefs.yaml and exits 0."""

    def test_exits_zero(self, tmp_path, monkeypatch) -> None:
        """kitefs init-config in an empty directory exits with code 0."""
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init-config"])
        assert result.exit_code == 0

    def test_creates_only_kitefs_yaml(self, tmp_path, monkeypatch) -> None:
        """Only kitefs.yaml is created; no feature_store/ dir or .gitignore."""
        monkeypatch.chdir(tmp_path)
        CliRunner().invoke(main, ["init-config"])

        assert (tmp_path / "kitefs.yaml").is_file()
        assert not (tmp_path / "feature_store").exists()
        assert not (tmp_path / ".gitignore").exists()

    def test_consumer_yaml_valid_yaml_with_project_name(self, tmp_path, monkeypatch) -> None:
        """Generated kitefs.yaml is valid YAML with the hardcoded project name."""
        monkeypatch.chdir(tmp_path)
        CliRunner().invoke(main, ["init-config"])

        data = yaml.safe_load((tmp_path / "kitefs.yaml").read_text(encoding="utf-8"))
        assert data["project"]["name"] == "kitefs_featurestore_project"
        assert data["version"] == 1

    def test_consumer_yaml_has_no_offline_store(self, tmp_path, monkeypatch) -> None:
        """Generated consumer kitefs.yaml omits remote.offline_store."""
        monkeypatch.chdir(tmp_path)
        CliRunner().invoke(main, ["init-config"])

        data = yaml.safe_load((tmp_path / "kitefs.yaml").read_text(encoding="utf-8"))
        assert "offline_store" not in data["remote"]
        assert "registry" in data["remote"]
        assert "online_store" in data["remote"]

    def test_stdout_summary_mentions_yaml_and_next_step(self, tmp_path, monkeypatch) -> None:
        """Success summary on stdout names kitefs.yaml and states the placeholder next step."""
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init-config"])

        assert result.stderr == ""
        assert "kitefs.yaml" in result.stdout
        # The summary must reference the placeholder fields that need editing.
        assert "bucket" in result.stdout or "dynamodb_table_prefix" in result.stdout


class TestInitConfigAlreadyExists:
    """kitefs init-config aborts cleanly when kitefs.yaml already exists."""

    def test_exits_one(self, tmp_path, monkeypatch) -> None:
        """kitefs init-config exits 1 when kitefs.yaml already exists."""
        (tmp_path / "kitefs.yaml").write_text("existing", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init-config"])
        assert result.exit_code == 1

    def test_exception_is_configuration_error_with_path(self, tmp_path, monkeypatch) -> None:
        """ConfigurationError contains the config path and `kitefs init-config` command hint.

        CliRunner invokes `main` directly, bypassing the cli() error boundary.
        Stderr rendering is proven by test_cli_error_boundary.py::TestKiteFSErrorBoundary.
        """
        config_path = tmp_path / "kitefs.yaml"
        config_path.write_text("existing", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init-config"])

        assert isinstance(result.exception, ConfigurationError)
        msg = str(result.exception)
        assert str(config_path.resolve()) in msg
        assert "kitefs init-config" in msg

    def test_stdout_is_empty(self, tmp_path, monkeypatch) -> None:
        """No output on stdout when aborting due to existing config."""
        (tmp_path / "kitefs.yaml").write_text("existing", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init-config"])
        assert result.stdout == ""

    def test_existing_file_unchanged(self, tmp_path, monkeypatch) -> None:
        """The pre-existing kitefs.yaml is not modified when aborting."""
        original_content = "existing content"
        (tmp_path / "kitefs.yaml").write_text(original_content, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        CliRunner().invoke(main, ["init-config"])
        assert (tmp_path / "kitefs.yaml").read_text(encoding="utf-8") == original_content
