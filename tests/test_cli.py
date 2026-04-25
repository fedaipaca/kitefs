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
        """kitefs --help exits with code 0."""
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0

    def test_help_shows_init_command(self) -> None:
        """kitefs --help output includes the init command."""
        result = _runner().invoke(cli, ["--help"])

        assert "init" in result.output


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
        # A comment that mentions the path is not a real gitignore rule and must
        # not prevent the actual `feature_store/data/` line from being appended.
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
        # Click now exposes the user-visible terminal stream via result.output,
        # which includes both stdout and stderr. Using catch_exceptions=False also
        # ensures unexpected non-SystemExit exceptions fail the test directly.
        result = CliRunner(catch_exceptions=False).invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 1
        assert "KiteFS project already initialized at this location" in result.output
        assert "Traceback" not in result.output

    def test_error_goes_to_stderr(self, tmp_path: Path) -> None:
        """Re-init error is written to stderr."""
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
        """Removing kitefs.yaml and re-running init succeeds, proving it is written last."""
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
        """Init on a read-only directory exits 1 without a traceback."""
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
        """Init creates missing parent directories automatically."""
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
        """kitefs --help output includes the apply command."""
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "apply" in result.output


# ---------------------------------------------------------------------------
# kitefs apply --help
# ---------------------------------------------------------------------------


class TestApplyHelp:
    """``kitefs apply --help`` advertises no custom options or arguments."""

    def test_help_exits_zero(self) -> None:
        """apply --help exits with code 0."""
        result = _runner().invoke(cli, ["apply", "--help"])

        assert result.exit_code == 0

    def test_no_custom_options(self) -> None:
        """apply --help shows only the built-in --help option."""
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
        """Successful apply exits with code 0."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": _SIMPLE_DEF})
            result = runner.invoke(cli, ["apply"], catch_exceptions=False)

        assert result.exit_code == 0

    def test_prints_summary(self, tmp_path: Path) -> None:
        """Apply prints the number of registered groups in its summary."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": _SIMPLE_DEF})
            result = runner.invoke(cli, ["apply"], catch_exceptions=False)

        assert "1" in result.output
        assert "registered" in result.output.lower() or "applied" in result.output.lower()

    def test_registry_json_updated(self, tmp_path: Path) -> None:
        """Apply writes the registered group to registry.json on disk."""
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
        """Apply outside a project exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1

    def test_error_message_suggests_init(self, tmp_path: Path) -> None:
        """Apply outside a project suggests running kitefs init."""
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
        """Apply outside a project does not show a traceback."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["apply"])

        assert "Traceback" not in result.output


class TestApplyInvalidDefinitions:
    """``kitefs apply`` with broken definitions exits 1 with errors to stderr."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Apply with broken definitions exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"broken.py": "import nonexistent_module_xyz\n"})
            result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1

    def test_error_message_contains_filename(self, tmp_path: Path) -> None:
        """Error includes the broken definition filename for debugging."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"broken.py": "import nonexistent_module_xyz\n"})
            result = runner.invoke(cli, ["apply"])

        combined = result.output + (result.stderr or "")
        assert "broken.py" in combined

    def test_no_traceback(self, tmp_path: Path) -> None:
        """Apply with broken definitions does not show a traceback."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"broken.py": "import nonexistent_module_xyz\n"})
            result = runner.invoke(cli, ["apply"])

        assert "Traceback" not in result.output


class TestApplyNoDefinitions:
    """``kitefs apply`` with no definition files exits 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Apply with no definition files exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td))
            result = runner.invoke(cli, ["apply"])

        assert result.exit_code == 1

    def test_error_message_is_actionable(self, tmp_path: Path) -> None:
        """Error tells the user no definitions were found."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td))
            result = runner.invoke(cli, ["apply"])

        combined = result.output + (result.stderr or "")
        assert "No feature group definitions found" in combined


class TestApplyProviderError:
    """``kitefs apply`` handles ProviderError with exit 1."""

    def test_provider_error_exits_one(self, tmp_path: Path) -> None:
        """ProviderError during apply exits 1 with the error message."""
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


# ---------------------------------------------------------------------------
# kitefs --help — shows list and describe commands
# ---------------------------------------------------------------------------


class TestCLIHelpShowsListAndDescribe:
    """The top-level help lists the list and describe commands."""

    def test_help_shows_list_command(self) -> None:
        """kitefs --help output includes the list command."""
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "list" in result.output

    def test_help_shows_describe_command(self) -> None:
        """kitefs --help output includes the describe command."""
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "describe" in result.output


# ---------------------------------------------------------------------------
# kitefs list --help
# ---------------------------------------------------------------------------


class TestListHelp:
    """``kitefs list --help`` shows the format and target options."""

    def test_help_exits_zero(self) -> None:
        """list --help exits with code 0."""
        result = _runner().invoke(cli, ["list", "--help"])

        assert result.exit_code == 0

    def test_shows_format_option(self) -> None:
        """list --help shows the --format option."""
        result = _runner().invoke(cli, ["list", "--help"])

        assert "--format" in result.output

    def test_shows_target_option(self) -> None:
        """list --help shows the --target option."""
        result = _runner().invoke(cli, ["list", "--help"])

        assert "--target" in result.output


# ---------------------------------------------------------------------------
# kitefs describe --help
# ---------------------------------------------------------------------------


class TestDescribeHelp:
    """``kitefs describe --help`` shows the name argument and options."""

    def test_help_exits_zero(self) -> None:
        """describe --help exits with code 0."""
        result = _runner().invoke(cli, ["describe", "--help"])

        assert result.exit_code == 0

    def test_shows_name_argument(self) -> None:
        """describe --help shows the feature group name argument."""
        result = _runner().invoke(cli, ["describe", "--help"])

        assert "feature_group_name" in result.output.lower() or "name" in result.output.lower()

    def test_shows_format_option(self) -> None:
        """describe --help shows the --format option."""
        result = _runner().invoke(cli, ["describe", "--help"])

        assert "--format" in result.output

    def test_shows_target_option(self) -> None:
        """describe --help shows the --target option."""
        result = _runner().invoke(cli, ["describe", "--help"])

        assert "--target" in result.output


# ---------------------------------------------------------------------------
# kitefs list — success paths
# ---------------------------------------------------------------------------


class TestListSuccess:
    """Successful ``kitefs list`` renders feature group summaries."""

    def test_exit_code_is_zero(self, tmp_path: Path) -> None:
        """Successful list exits with code 0."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert result.exit_code == 0

    def test_output_contains_group_names(self, tmp_path: Path) -> None:
        """List output includes the names of all registered feature groups."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert "listing_features" in result.output
        assert "town_market_features" in result.output

    def test_output_contains_summary_values(self, tmp_path: Path) -> None:
        """List output includes owner and entity key summary values."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert "data-science-team" in result.output
        assert "listing_id" in result.output

    def test_empty_registry_prints_informational_message(self, tmp_path: Path) -> None:
        """An empty registry prints an informational message, not an error."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td))
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "No feature groups registered" in result.output

    def test_json_format_prints_json_to_stdout(self, tmp_path: Path) -> None:
        """list --format json prints parseable JSON array to stdout."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list", "--format", "json"], catch_exceptions=False)

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_target_writes_file_and_confirms_path(self, tmp_path: Path) -> None:
        """list --target writes JSON to a file and confirms the path."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            output_file = td_path / "list_output.json"
            result = runner.invoke(cli, ["list", "--target", str(output_file)], catch_exceptions=False)

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert "Output written to" in result.output


# ---------------------------------------------------------------------------
# kitefs list — error paths
# ---------------------------------------------------------------------------


class TestListOutsideProject:
    """``kitefs list`` outside a KiteFS project fails with exit 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """List outside a project exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 1

    def test_error_message_suggests_init(self, tmp_path: Path) -> None:
        """List outside a project suggests running kitefs init."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["list"])

        combined = result.output + (result.stderr or "")
        assert "kitefs init" in combined


# ---------------------------------------------------------------------------
# kitefs describe — success paths
# ---------------------------------------------------------------------------


class TestDescribeSuccess:
    """Successful ``kitefs describe`` renders the full feature group definition."""

    def test_exit_code_is_zero(self, tmp_path: Path) -> None:
        """Successful describe exits with code 0."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert result.exit_code == 0

    def test_output_contains_group_name(self, tmp_path: Path) -> None:
        """Describe output includes the feature group name."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert "listing_features" in result.output

    def test_output_contains_structural_fields(self, tmp_path: Path) -> None:
        """Describe output shows entity key, event timestamp, and storage target."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert "listing_id" in result.output
        assert "event_timestamp" in result.output
        assert "OFFLINE" in result.output

    def test_output_contains_features(self, tmp_path: Path) -> None:
        """Describe output lists the feature names."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert "net_area" in result.output
        assert "sold_price" in result.output

    def test_output_contains_validation_modes(self, tmp_path: Path) -> None:
        """Describe output shows the ingestion validation mode."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert "ERROR" in result.output

    def test_json_format_prints_json_to_stdout(self, tmp_path: Path) -> None:
        """describe --format json prints parseable JSON to stdout."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features", "--format", "json"], catch_exceptions=False)

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["name"] == "listing_features"

    def test_target_writes_file_and_confirms_path(self, tmp_path: Path) -> None:
        """describe --target writes JSON to a file and confirms the path."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            output_file = td_path / "describe_output.json"
            result = runner.invoke(
                cli, ["describe", "listing_features", "--target", str(output_file)], catch_exceptions=False
            )

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert data["name"] == "listing_features"
        assert "Output written to" in result.output


# ---------------------------------------------------------------------------
# kitefs describe — error paths
# ---------------------------------------------------------------------------


class TestDescribeOutsideProject:
    """``kitefs describe`` outside a KiteFS project fails with exit 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Describe outside a project exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["describe", "anything"])

        assert result.exit_code == 1

    def test_error_message_suggests_init(self, tmp_path: Path) -> None:
        """Describe outside a project suggests running kitefs init."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["describe", "anything"])

        combined = result.output + (result.stderr or "")
        assert "kitefs init" in combined


class TestDescribeUnknownGroup:
    """``kitefs describe`` with unknown group name exits 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Describing a non-existent group exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "missing_group"])

        assert result.exit_code == 1

    def test_error_message_includes_group_name(self, tmp_path: Path) -> None:
        """Error includes the requested group name for debugging."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "missing_group"])

        combined = result.output + (result.stderr or "")
        assert "missing_group" in combined

    def test_error_suggests_kitefs_list(self, tmp_path: Path) -> None:
        """Error suggests running kitefs list to see available groups."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "missing_group"])

        combined = result.output + (result.stderr or "")
        assert "kitefs list" in combined

    def test_no_traceback(self, tmp_path: Path) -> None:
        """Describe error does not show a traceback."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "missing_group"])

        assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# kitefs list — None owner renders cleanly (no literal "None" in output)
# ---------------------------------------------------------------------------


class TestListOwnerNoneRenders:
    """A feature group with no owner shows an empty cell, not the string 'None'."""

    def test_none_owner_does_not_appear_as_string(self, tmp_path: Path) -> None:
        """A None owner renders as an empty cell, not the literal string 'None'."""
        # MINIMAL_DEF has no Metadata, so owner is None.
        minimal = MINIMAL_DEF.format(varname="no_owner_group", name="no_owner_group")
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"minimal.py": minimal})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "None" not in result.output

    def test_none_owner_json_format_contains_null(self, tmp_path: Path) -> None:
        """JSON output serializes None owner as JSON null."""
        minimal = MINIMAL_DEF.format(varname="no_owner_group", name="no_owner_group")
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"minimal.py": minimal})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["list", "--format", "json"], catch_exceptions=False)

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["owner"] is None


# ---------------------------------------------------------------------------
# kitefs describe — join keys section appears in output
# ---------------------------------------------------------------------------


class TestDescribeJoinKeysShown:
    """``kitefs describe`` renders the join keys section when present."""

    def test_join_key_field_and_target_group_shown(self, tmp_path: Path) -> None:
        """Describe shows join key field name and referenced group."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "listing_features"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "town_id" in result.output
        assert "town_market_features" in result.output

    def test_no_join_keys_section_absent_for_group_without_joins(self, tmp_path: Path) -> None:
        """Describe omits the Join Keys section when the group has no join keys."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            setup_project(Path(td), {"town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            result = runner.invoke(cli, ["describe", "town_market_features"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "Join Keys" not in result.output
