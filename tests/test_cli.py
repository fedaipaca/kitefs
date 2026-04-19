"""Tests for the CLI entry point, ``kitefs init``, and ``kitefs apply`` commands."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from kitefs.cli import cli
from kitefs.exceptions import ProviderError
from tests.helpers import LISTING_DEF, MINIMAL_DEF, TOWN_DEF, setup_project


def _runner() -> CliRunner:
    """Create a Click test runner with isolated filesystem disabled (we use tmp_path)."""
    return CliRunner()


# ---------------------------------------------------------------------------
# kitefs --help
# ---------------------------------------------------------------------------


class TestCLIHelp:
    """The top-level group exposes help and lists commands."""

    def test_help_exits_zero(self) -> None:
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0

    def test_help_shows_init_command(self) -> None:
        result = _runner().invoke(cli, ["--help"])

        assert "init" in result.output


# ---------------------------------------------------------------------------
# kitefs init — success paths
# ---------------------------------------------------------------------------


class TestInitSuccess:
    """Successful ``kitefs init`` creates the full project scaffold."""

    def test_exit_code_is_zero(self, tmp_path: Path) -> None:
        result = _runner().invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 0

    def test_kitefs_yaml_created(self, tmp_path: Path) -> None:
        _runner().invoke(cli, ["init", str(tmp_path)])

        config_path = tmp_path / "kitefs.yaml"
        assert config_path.exists()
        content = config_path.read_text(encoding="utf-8")
        assert "provider: local" in content
        assert "storage_root: ./feature_store/" in content

    def test_definitions_directory_created(self, tmp_path: Path) -> None:
        _runner().invoke(cli, ["init", str(tmp_path)])

        definitions_dir = tmp_path / "feature_store" / "definitions"
        assert definitions_dir.is_dir()
        assert (definitions_dir / "__init__.py").exists()
        assert (definitions_dir / "example_features.py").exists()

    def test_example_features_contains_template(self, tmp_path: Path) -> None:
        _runner().invoke(cli, ["init", str(tmp_path)])

        example = tmp_path / "feature_store" / "definitions" / "example_features.py"
        content = example.read_text(encoding="utf-8")
        assert "FeatureGroup" in content
        assert "EntityKey" in content

    def test_offline_store_directory_created(self, tmp_path: Path) -> None:
        _runner().invoke(cli, ["init", str(tmp_path)])

        assert (tmp_path / "feature_store" / "data" / "offline_store").is_dir()

    def test_online_store_directory_created(self, tmp_path: Path) -> None:
        _runner().invoke(cli, ["init", str(tmp_path)])

        assert (tmp_path / "feature_store" / "data" / "online_store").is_dir()

    def test_registry_json_seeded(self, tmp_path: Path) -> None:
        _runner().invoke(cli, ["init", str(tmp_path)])

        registry_path = tmp_path / "feature_store" / "registry.json"
        assert registry_path.exists()
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        assert data == {"version": "1.0", "feature_groups": {}}

    def test_registry_json_is_deterministic(self, tmp_path: Path) -> None:
        _runner().invoke(cli, ["init", str(tmp_path)])

        registry_path = tmp_path / "feature_store" / "registry.json"
        content = registry_path.read_text(encoding="utf-8")
        expected = json.dumps({"version": "1.0", "feature_groups": {}}, sort_keys=True, indent=2) + "\n"
        assert content == expected

    def test_gitignore_created(self, tmp_path: Path) -> None:
        _runner().invoke(cli, ["init", str(tmp_path)])

        gitignore_path = tmp_path / ".gitignore"
        assert gitignore_path.exists()
        assert "feature_store/data/" in gitignore_path.read_text(encoding="utf-8")

    def test_confirmation_message(self, tmp_path: Path) -> None:
        result = _runner().invoke(cli, ["init", str(tmp_path)])

        assert "Project initialized at" in result.output
        assert "Provider: local" in result.output
        assert "Config:" in result.output


class TestInitDefaultPath:
    """``kitefs init`` (no argument) creates the scaffold in the current directory."""

    def test_default_to_cwd(self, tmp_path: Path) -> None:
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
        target = tmp_path / "my_project"
        target.mkdir()
        result = _runner().invoke(cli, ["init", str(target)])

        assert result.exit_code == 0
        assert (target / "kitefs.yaml").exists()
        assert (target / "feature_store" / "registry.json").exists()
        assert (target / "feature_store" / "definitions" / "__init__.py").exists()

    def test_scaffold_at_nested_path(self, tmp_path: Path) -> None:
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
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")

        _runner().invoke(cli, ["init", str(tmp_path)])

        content = gitignore.read_text(encoding="utf-8")
        assert "*.pyc" in content
        assert "feature_store/data/" in content

    def test_no_duplicate_if_entry_already_present(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("feature_store/data/\n", encoding="utf-8")

        _runner().invoke(cli, ["init", str(tmp_path)])

        content = gitignore.read_text(encoding="utf-8")
        assert content.count("feature_store/data/") == 1

    def test_comment_containing_entry_does_not_suppress_real_entry(self, tmp_path: Path) -> None:
        # A comment that mentions the path is not a real gitignore rule and must
        # not prevent the actual `feature_store/data/` line from being appended.
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("# do not add feature_store/data/ yourself\n", encoding="utf-8")

        _runner().invoke(cli, ["init", str(tmp_path)])

        lines = [line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()]
        assert "feature_store/data/" in lines

    def test_handles_gitignore_without_trailing_newline(self, tmp_path: Path) -> None:
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
        _runner().invoke(cli, ["init", str(tmp_path)])
        result = _runner().invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 1

    def test_error_message(self, tmp_path: Path) -> None:
        _runner().invoke(cli, ["init", str(tmp_path)])
        result = _runner().invoke(cli, ["init", str(tmp_path)])

        assert "KiteFS project already initialized at this location" in result.output

    def test_error_has_no_traceback(self, tmp_path: Path) -> None:
        _runner().invoke(cli, ["init", str(tmp_path)])
        # Click now exposes the user-visible terminal stream via result.output,
        # which includes both stdout and stderr. Using catch_exceptions=False also
        # ensures unexpected non-SystemExit exceptions fail the test directly.
        result = CliRunner(catch_exceptions=False).invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 1
        assert "KiteFS project already initialized at this location" in result.output
        assert "Traceback" not in result.output

    def test_error_goes_to_stderr(self, tmp_path: Path) -> None:
        _runner().invoke(cli, ["init", str(tmp_path)])

        # Click (stable) removed mix_stderr; Result now natively exposes .stderr.
        result = _runner().invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 1
        assert "KiteFS project already initialized" in result.stderr


# ---------------------------------------------------------------------------
# kitefs init — atomicity: kitefs.yaml written last
# ---------------------------------------------------------------------------


class TestInitAtomicity:
    """kitefs.yaml is the sentinel file and is written last."""

    def test_kitefs_yaml_is_last_file_written(self, tmp_path: Path) -> None:
        # If kitefs.yaml is missing but all other scaffold files exist, a retry
        # of `kitefs init` must succeed — proving the sentinel is written last.
        _runner().invoke(cli, ["init", str(tmp_path)])

        # Simulate a crash that left everything except the sentinel
        (tmp_path / "kitefs.yaml").unlink()

        # Re-running init should succeed, not raise "already initialized"
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
        import stat

        target = tmp_path / "readonly_project"
        target.mkdir()
        target.chmod(stat.S_IRUSR | stat.S_IXUSR)  # read + execute only, no write

        try:
            result = _runner().invoke(cli, ["init", str(target)])
            assert result.exit_code == 1
            assert "Traceback" not in result.output
        finally:
            # Restore write permission so tmp_path cleanup can delete the directory
            target.chmod(stat.S_IRWXU)


# ---------------------------------------------------------------------------
# kitefs init — nonexistent target path
# ---------------------------------------------------------------------------


class TestInitNonexistentPath:
    """``kitefs init <path>`` where the path does not yet exist."""

    def test_parent_does_not_exist(self, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "nested" / "project"
        # target and its parents do not exist yet
        assert not target.exists()

        result = _runner().invoke(cli, ["init", str(target)])

        assert result.exit_code == 0
        assert (target / "kitefs.yaml").exists()
        assert (target / "feature_store" / "registry.json").exists()


# ---------------------------------------------------------------------------
# kitefs --help — shows apply command
# ---------------------------------------------------------------------------


class TestCLIHelpShowsApply:
    """The top-level help lists the apply command."""

    def test_help_shows_apply_command(self) -> None:
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "apply" in result.output


# ---------------------------------------------------------------------------
# kitefs apply --help
# ---------------------------------------------------------------------------


class TestApplyHelp:
    """``kitefs apply --help`` advertises no custom options or arguments."""

    def test_help_exits_zero(self) -> None:
        result = _runner().invoke(cli, ["apply", "--help"])

        assert result.exit_code == 0

    def test_no_custom_options(self) -> None:
        result = _runner().invoke(cli, ["apply", "--help"])

        # Only Click's built-in --help should appear; no custom arguments or options.
        lines = result.output.strip().splitlines()
        option_lines = [line.strip() for line in lines if line.strip().startswith("--")]
        assert all("--help" in line for line in option_lines)


# ---------------------------------------------------------------------------
# kitefs apply — success paths
# ---------------------------------------------------------------------------

# A concrete definition for CLI tests.
_SIMPLE_DEF = MINIMAL_DEF.format(varname="listing_features", name="listing_features")


class TestApplySuccess:
    """Successful ``kitefs apply`` exits 0 and prints a summary."""

    def test_exit_code_is_zero(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": _SIMPLE_DEF})
            result = runner.invoke(cli, ["apply"], catch_exceptions=False)

        assert result.exit_code == 0

    def test_prints_summary(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": _SIMPLE_DEF})
            result = runner.invoke(cli, ["apply"], catch_exceptions=False)

        assert "1" in result.output
        assert "registered" in result.output.lower() or "applied" in result.output.lower()

    def test_registry_json_updated(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"listing.py": _SIMPLE_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)

            registry = json.loads((td_path / "feature_store" / "registry.json").read_text(encoding="utf-8"))

        assert "listing_features" in registry["feature_groups"]

    def test_multiple_groups_summary(self, tmp_path: Path) -> None:
        """Applying two groups prints count '2' in the summary."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(
                Path(td),
                {"listing.py": LISTING_DEF, "town.py": TOWN_DEF},
            )
            result = runner.invoke(cli, ["apply"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "2" in result.output


# ---------------------------------------------------------------------------
# kitefs apply — error paths
# ---------------------------------------------------------------------------


class TestApplyOutsideProject:
    """``kitefs apply`` outside a KiteFS project fails with exit 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1

    def test_error_message_suggests_init(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["apply"])

        assert "kitefs init" in result.output or "kitefs init" in (result.stderr or "")

    def test_error_goes_to_stderr(self, tmp_path: Path) -> None:
        """Error output is written to stderr, not stdout."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1
        assert "No KiteFS project found" in result.stderr

    def test_no_traceback(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["apply"])

        assert "Traceback" not in result.output


class TestApplyInvalidDefinitions:
    """``kitefs apply`` with broken definitions exits 1 with errors to stderr."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"broken.py": "import nonexistent_module_xyz\n"})
            result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1

    def test_error_message_contains_filename(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"broken.py": "import nonexistent_module_xyz\n"})
            result = runner.invoke(cli, ["apply"])

        combined = result.output + (result.stderr or "")
        assert "broken.py" in combined

    def test_no_traceback(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"broken.py": "import nonexistent_module_xyz\n"})
            result = runner.invoke(cli, ["apply"])

        assert "Traceback" not in result.output


class TestApplyNoDefinitions:
    """``kitefs apply`` with no definition files exits 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td))
            result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1

    def test_error_message_is_actionable(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td))
            result = runner.invoke(cli, ["apply"])

        combined = result.output + (result.stderr or "")
        assert "No feature group definitions found" in combined


class TestApplyProviderError:
    """``kitefs apply`` handles ProviderError with exit 1."""

    def test_provider_error_exits_one(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": _SIMPLE_DEF})

            with patch(
                "kitefs.feature_store.FeatureStore.apply",
                side_effect=ProviderError("Disk full"),
            ):
                result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1
        combined = result.output + (result.stderr or "")
        assert "Disk full" in combined
