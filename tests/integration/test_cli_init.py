"""Integration tests for `kitefs init` — producer scaffold CLI command."""

from __future__ import annotations

import subprocess
import sys

import pytest
from click.testing import CliRunner

from kitefs.cli import cli, main
from kitefs.errors import ConfigurationError


class TestInitHappyPath:
    """kitefs init creates the producer scaffold and exits 0."""

    def test_exits_zero(self, tmp_path, monkeypatch) -> None:
        """kitefs init in an empty directory exits with code 0."""
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init"])
        assert result.exit_code == 0

    def test_creates_all_expected_paths(self, tmp_path, monkeypatch) -> None:
        """kitefs init creates kitefs.yaml, registry, definitions, and data dirs."""
        monkeypatch.chdir(tmp_path)
        CliRunner().invoke(main, ["init"])

        assert (tmp_path / "kitefs.yaml").is_file()
        assert (tmp_path / "feature_store" / "definitions" / "town_market_features.py").is_file()
        assert (tmp_path / "feature_store" / "registry.json").is_file()
        assert (tmp_path / "feature_store" / "data" / "offline_store").is_dir()
        assert (tmp_path / "feature_store" / "data" / "online_store").is_dir()
        assert (tmp_path / ".gitignore").is_file()

    def test_stdout_summary_new_gitignore(self, tmp_path, monkeypatch) -> None:
        """Success summary goes to stdout and matches the AC-10 format (fresh .gitignore)."""
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init"])

        expected = (
            f"Created KiteFS producer scaffold in {tmp_path.resolve()}:\n"
            "  kitefs.yaml\n"
            "  feature_store/definitions/town_market_features.py\n"
            "  feature_store/registry.json\n"
            "  feature_store/data/offline_store/\n"
            "  feature_store/data/online_store/\n"
            "  .gitignore\n"
            "\n"
            "Next step: edit feature_store/definitions/, then run 'kitefs apply' to register them.\n"
        )
        assert result.stdout == expected
        assert result.stderr == ""


@pytest.mark.parametrize(
    ("pre_gitignore", "expected_gi_line"),
    [
        pytest.param(
            None,
            "  .gitignore",
            id="gitignore_absent",
        ),
        pytest.param(
            "# existing\n",
            "  .gitignore (appended 2 entries)",
            id="gitignore_present_neither_entry",
        ),
        pytest.param(
            "feature_store/data/\nfeature_store/registry.json\n",
            None,  # line omitted
            id="gitignore_present_both_entries",
        ),
    ],
)
class TestInitGitignoreSummaryVariants:
    """kitefs init stdout summary reflects .gitignore state correctly."""

    def test_gitignore_summary_line(
        self,
        tmp_path,
        monkeypatch,
        pre_gitignore: str | None,
        expected_gi_line: str | None,
    ) -> None:
        """Summary .gitignore line matches the pre-existing .gitignore state."""
        if pre_gitignore is not None:
            (tmp_path / ".gitignore").write_text(pre_gitignore, encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init"])

        assert result.exit_code == 0
        summary_lines = result.stdout.splitlines()
        gi_lines = [ln for ln in summary_lines if ".gitignore" in ln]
        if expected_gi_line is None:
            assert gi_lines == [], "Expected no .gitignore line in summary"
        else:
            assert any(expected_gi_line in ln for ln in gi_lines), (
                f"Expected '{expected_gi_line}' in summary; got lines: {gi_lines}"
            )


class TestInitAlreadyExists:
    """kitefs init aborts cleanly when kitefs.yaml already exists."""

    def test_exits_one(self, tmp_path, monkeypatch) -> None:
        """kitefs init exits 1 when kitefs.yaml already exists."""
        (tmp_path / "kitefs.yaml").write_text("existing", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init"])
        assert result.exit_code == 1

    def test_exception_is_configuration_error_with_path(self, tmp_path, monkeypatch) -> None:
        """ConfigurationError contains the config path and `kitefs init` command hint.

        CliRunner invokes `main` directly, bypassing the cli() error boundary.
        Stderr rendering is proven by test_cli_error_boundary.py::TestKiteFSErrorBoundary.
        """
        config_path = tmp_path / "kitefs.yaml"
        config_path.write_text("existing", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init"])

        assert isinstance(result.exception, ConfigurationError)
        msg = str(result.exception)
        assert str(config_path.resolve()) in msg
        assert "kitefs init" in msg

    def test_stdout_is_empty(self, tmp_path, monkeypatch) -> None:
        """No output on stdout when aborting due to existing config."""
        (tmp_path / "kitefs.yaml").write_text("existing", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init"])
        assert result.stdout == ""

    def test_writes_nothing_new(self, tmp_path, monkeypatch) -> None:
        """No new files or directories are created when aborting."""
        (tmp_path / "kitefs.yaml").write_text("existing", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        CliRunner().invoke(main, ["init"])

        # Only kitefs.yaml should exist (pre-existing); no feature_store/ etc.
        items = set(tmp_path.iterdir())
        assert items == {tmp_path / "kitefs.yaml"}


class TestInitImportIsolation:
    """Importing kitefs.cli after adding init does not load forbidden modules."""

    def test_scaffold_module_not_loaded_on_import(self) -> None:
        """kitefs.cli.scaffold is not imported at kitefs.cli import time (lazy import)."""
        script = "import kitefs.cli, sys; mods = sorted(k for k in sys.modules if k.startswith('kitefs')); print(mods)"
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "kitefs.cli.scaffold" not in result.stdout

    def test_forbidden_modules_absent(self) -> None:
        """Heavy kitefs.* submodules are not imported by importing kitefs.cli."""
        script = "import kitefs.cli, sys; mods = sorted(k for k in sys.modules if k.startswith('kitefs')); print(mods)"
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        forbidden = [
            "kitefs.sdk",
            "kitefs.config",
            "kitefs.providers",
            "kitefs.offline_store",
            "kitefs.online_store",
            "kitefs.registry",
            "kitefs.validation",
            "kitefs.join_engine",
        ]
        for mod in forbidden:
            assert mod not in result.stdout, f"Forbidden module imported: {mod}"


class TestInitIOFailure:
    """kitefs init classifies filesystem failures as ConfigurationError; cli() exits 1 without traceback."""

    def test_io_failure_exits_one_without_traceback(self, tmp_path, monkeypatch, capsys) -> None:
        """An OSError during scaffold is classified as ConfigurationError; cli() exits 1 without traceback."""
        from kitefs.cli import scaffold as scaffold_module

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["kitefs", "init"])

        def fail_all(path, content, created):
            raise OSError("simulated: no space left on device")

        monkeypatch.setattr(scaffold_module, "_atomic_write_text", fail_all)

        with pytest.raises(SystemExit) as ei:
            cli()

        assert ei.value.code == 1
        out, err = capsys.readouterr()
        assert out == ""
        assert "Traceback" not in err
        assert "Error:" in err
        assert not (tmp_path / "kitefs.yaml").exists()
        assert not (tmp_path / "feature_store").exists()
