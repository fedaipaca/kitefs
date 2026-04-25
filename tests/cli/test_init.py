"""Tests for the ``kitefs init`` command."""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from kitefs.cli import cli


def _runner() -> CliRunner:
    """Create a Click test runner with isolated filesystem disabled (we use tmp_path)."""
    return CliRunner()


# ---------------------------------------------------------------------------
# kitefs init — success paths
# ---------------------------------------------------------------------------


class TestInitSuccess:
    """Successful ``kitefs init`` creates the full project scaffold."""

    def test_exit_code_is_zero(self, tmp_path: Path) -> None:
        """Successful init exits with code 0."""
        result = _runner().invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 0

    def test_kitefs_yaml_created(self, tmp_path: Path) -> None:
        """Init creates kitefs.yaml with local provider and default storage root."""
        _runner().invoke(cli, ["init", str(tmp_path)])

        config_path = tmp_path / "kitefs.yaml"
        assert config_path.exists()
        content = config_path.read_text(encoding="utf-8")
        assert "provider: local" in content
        assert "storage_root: ./feature_store/" in content

    def test_definitions_directory_created(self, tmp_path: Path) -> None:
        """Init creates the definitions directory with __init__.py and example file."""
        _runner().invoke(cli, ["init", str(tmp_path)])

        definitions_dir = tmp_path / "feature_store" / "definitions"
        assert definitions_dir.is_dir()
        assert (definitions_dir / "__init__.py").exists()
        assert (definitions_dir / "example_features.py").exists()

    def test_example_features_contains_template(self, tmp_path: Path) -> None:
        """Init seeds example_features.py with a FeatureGroup template."""
        _runner().invoke(cli, ["init", str(tmp_path)])

        example = tmp_path / "feature_store" / "definitions" / "example_features.py"
        content = example.read_text(encoding="utf-8")
        assert "FeatureGroup" in content
        assert "EntityKey" in content

    def test_offline_store_directory_created(self, tmp_path: Path) -> None:
        """Init creates the offline_store data directory."""
        _runner().invoke(cli, ["init", str(tmp_path)])

        assert (tmp_path / "feature_store" / "data" / "offline_store").is_dir()

    def test_online_store_directory_created(self, tmp_path: Path) -> None:
        """Init creates the online_store data directory."""
        _runner().invoke(cli, ["init", str(tmp_path)])

        assert (tmp_path / "feature_store" / "data" / "online_store").is_dir()

    def test_registry_json_seeded(self, tmp_path: Path) -> None:
        """Init seeds an empty registry.json with version 1.0."""
        _runner().invoke(cli, ["init", str(tmp_path)])

        registry_path = tmp_path / "feature_store" / "registry.json"
        assert registry_path.exists()
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        assert data == {"version": "1.0", "feature_groups": {}}

    def test_registry_json_is_deterministic(self, tmp_path: Path) -> None:
        """Seeded registry.json uses sorted keys and indent 2 for Git-friendly diffs."""
        _runner().invoke(cli, ["init", str(tmp_path)])

        registry_path = tmp_path / "feature_store" / "registry.json"
        content = registry_path.read_text(encoding="utf-8")
        expected = json.dumps({"version": "1.0", "feature_groups": {}}, sort_keys=True, indent=2) + "\n"
        assert content == expected

    def test_gitignore_created(self, tmp_path: Path) -> None:
        """Init creates .gitignore with feature_store/data/ entry."""
        _runner().invoke(cli, ["init", str(tmp_path)])

        gitignore_path = tmp_path / ".gitignore"
        assert gitignore_path.exists()
        assert "feature_store/data/" in gitignore_path.read_text(encoding="utf-8")

    def test_confirmation_message(self, tmp_path: Path) -> None:
        """Init prints a confirmation message with project path and provider."""
        result = _runner().invoke(cli, ["init", str(tmp_path)])

        assert "Project initialized at" in result.output
        assert "Provider: local" in result.output
        assert "Config:" in result.output


class TestInitDefaultPath:
    """``kitefs init`` (no argument) creates the scaffold in the current directory."""

    def test_default_to_cwd(self, tmp_path: Path) -> None:
        """Init with no argument scaffolds the project in the current directory."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init"])

            assert result.exit_code == 0
            assert Path("kitefs.yaml").exists()
            assert Path("feature_store", "registry.json").exists()
            assert Path("feature_store", "definitions", "__init__.py").exists()


class TestInitCustomPath:
    """``kitefs init <path>`` creates the scaffold at a custom path."""

    def test_scaffold_at_subdirectory(self, tmp_path: Path) -> None:
        """Init at a custom subdirectory creates the full scaffold there."""
        target = tmp_path / "my_project"
        target.mkdir()
        result = _runner().invoke(cli, ["init", str(target)])

        assert result.exit_code == 0
        assert (target / "kitefs.yaml").exists()
        assert (target / "feature_store" / "registry.json").exists()
        assert (target / "feature_store" / "definitions" / "__init__.py").exists()

    def test_scaffold_at_nested_path(self, tmp_path: Path) -> None:
        """Init at a deeply nested path creates kitefs.yaml there."""
        target = tmp_path / "deep" / "nested" / "project"
        target.mkdir(parents=True)
        result = _runner().invoke(cli, ["init", str(target)])

        assert result.exit_code == 0
        assert (target / "kitefs.yaml").exists()


# ---------------------------------------------------------------------------
# kitefs init — .gitignore handling
# ---------------------------------------------------------------------------


class TestInitGitignore:
    """The init command creates or appends .gitignore correctly."""

    def test_appends_to_existing_gitignore(self, tmp_path: Path) -> None:
        """Init appends feature_store/data/ to an existing .gitignore."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")

        _runner().invoke(cli, ["init", str(tmp_path)])

        content = gitignore.read_text(encoding="utf-8")
        assert "*.pyc" in content
        assert "feature_store/data/" in content

    def test_no_duplicate_if_entry_already_present(self, tmp_path: Path) -> None:
        """Init does not duplicate feature_store/data/ if already present."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("feature_store/data/\n", encoding="utf-8")

        _runner().invoke(cli, ["init", str(tmp_path)])

        content = gitignore.read_text(encoding="utf-8")
        assert content.count("feature_store/data/") == 1

    def test_comment_containing_entry_does_not_suppress_real_entry(self, tmp_path: Path) -> None:
        """A commented-out gitignore entry does not suppress the real entry."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("# do not add feature_store/data/ yourself\n", encoding="utf-8")

        _runner().invoke(cli, ["init", str(tmp_path)])

        lines = [line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()]
        assert "feature_store/data/" in lines

    def test_handles_gitignore_without_trailing_newline(self, tmp_path: Path) -> None:
        """Init handles a .gitignore that does not end with a newline."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc", encoding="utf-8")

        _runner().invoke(cli, ["init", str(tmp_path)])

        content = gitignore.read_text(encoding="utf-8")
        assert "*.pyc\nfeature_store/data/" in content


# ---------------------------------------------------------------------------
# kitefs init — error paths
# ---------------------------------------------------------------------------


class TestInitAlreadyInitialized:
    """Re-initializing an existing project fails with a clear error."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Re-initializing exits with code 1."""
        _runner().invoke(cli, ["init", str(tmp_path)])
        result = _runner().invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 1

    def test_error_message(self, tmp_path: Path) -> None:
        """Re-init error message says the project is already initialized."""
        _runner().invoke(cli, ["init", str(tmp_path)])
        result = _runner().invoke(cli, ["init", str(tmp_path)])

        assert "KiteFS project already initialized at this location" in result.output

    def test_error_has_no_traceback(self, tmp_path: Path) -> None:
        """Re-init error does not include a Python traceback."""
        _runner().invoke(cli, ["init", str(tmp_path)])
        result = CliRunner(catch_exceptions=False).invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 1
        assert "KiteFS project already initialized at this location" in result.output
        assert "Traceback" not in result.output

    def test_error_goes_to_stderr(self, tmp_path: Path) -> None:
        """Re-init error is written to stderr."""
        _runner().invoke(cli, ["init", str(tmp_path)])

        result = _runner().invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 1
        assert "KiteFS project already initialized" in result.stderr


# ---------------------------------------------------------------------------
# kitefs init — atomicity: kitefs.yaml written last
# ---------------------------------------------------------------------------


class TestInitAtomicity:
    """kitefs.yaml is the sentinel file and is written last."""

    def test_kitefs_yaml_is_last_file_written(self, tmp_path: Path) -> None:
        """Removing kitefs.yaml and re-running init succeeds, proving it is written last."""
        _runner().invoke(cli, ["init", str(tmp_path)])

        (tmp_path / "kitefs.yaml").unlink()

        result = _runner().invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 0
        assert (tmp_path / "kitefs.yaml").exists()


# ---------------------------------------------------------------------------
# kitefs init — OS error paths
# ---------------------------------------------------------------------------


class TestInitOSErrors:
    """Filesystem errors produce exit code 1 without tracebacks."""

    @pytest.mark.skipif(os.getuid() == 0, reason="root ignores filesystem permissions")
    def test_readonly_directory(self, tmp_path: Path) -> None:
        """Init on a read-only directory exits 1 without a traceback."""
        import stat

        target = tmp_path / "readonly_project"
        target.mkdir()
        target.chmod(stat.S_IRUSR | stat.S_IXUSR)

        try:
            result = _runner().invoke(cli, ["init", str(target)])
            assert result.exit_code == 1
            assert "Traceback" not in result.output
        finally:
            target.chmod(stat.S_IRWXU)


# ---------------------------------------------------------------------------
# kitefs init — nonexistent target path
# ---------------------------------------------------------------------------


class TestInitNonexistentPath:
    """``kitefs init <path>`` where the path does not yet exist."""

    def test_parent_does_not_exist(self, tmp_path: Path) -> None:
        """Init creates missing parent directories automatically."""
        target = tmp_path / "deep" / "nested" / "project"
        assert not target.exists()

        result = _runner().invoke(cli, ["init", str(target)])

        assert result.exit_code == 0
        assert (target / "kitefs.yaml").exists()
        assert (target / "feature_store" / "registry.json").exists()
