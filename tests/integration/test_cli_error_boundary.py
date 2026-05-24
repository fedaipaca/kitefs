import subprocess
import sys

import click
import pytest

from kitefs.cli import cli, main
from kitefs.errors import (
    ConfigurationError,
    FeatureGroupNotFoundError,
    KiteFSError,
    OfflineStoreReadError,
)


@pytest.fixture()
def temp_command(monkeypatch):
    """Register a throwaway subcommand on main; remove it in teardown."""
    registered: list[str] = []

    def register(name: str, fn):
        cmd = click.command(name)(fn)
        main.add_command(cmd)
        registered.append(name)
        return cmd

    yield register

    for name in registered:
        main.commands.pop(name, None)


class TestKiteFSErrorBoundary:
    """Error boundary renders KiteFSError as a single stderr line, exits 1."""

    @pytest.mark.parametrize(
        ("exc_class", "msg"),
        [
            pytest.param(ConfigurationError, "bad config", id="ConfigurationError"),
            pytest.param(FeatureGroupNotFoundError, "group missing", id="FeatureGroupNotFoundError"),
            pytest.param(OfflineStoreReadError, "read failed", id="OfflineStoreReadError"),
        ],
    )
    def test_kitefs_error_exits_1_with_error_prefix(
        self,
        exc_class: type[KiteFSError],
        msg: str,
        monkeypatch,
        capsys,
        temp_command,
    ) -> None:
        """KiteFSError subclass → exit 1, 'Error: <msg>' on stderr, stdout empty, no traceback."""
        exc = exc_class(msg)

        def raise_it():
            raise exc

        temp_command("tmperr", raise_it)
        monkeypatch.setattr(sys, "argv", ["kitefs", "tmperr"])

        with pytest.raises(SystemExit) as ei:
            cli()

        assert ei.value.code == 1
        out, err = capsys.readouterr()
        assert out == ""
        assert err == f"Error: {msg}\n"
        assert "Traceback" not in err


class TestUnexpectedExceptionBoundary:
    """Unexpected exceptions fall through with a traceback and exit 2."""

    def test_runtime_error_exits_2_with_traceback(self) -> None:
        """RuntimeError below main → exit 2 with traceback in stderr, stdout empty."""
        # Drive via subprocess so traceback.print_exception renders to the real
        # stderr of a fresh process — isolates from CliRunner stream capture.
        script = (
            "import click, sys\n"
            "from kitefs.cli import cli, main\n"
            "@click.command('tmperr')\n"
            "def tmperr(): raise RuntimeError('boom')\n"
            "main.add_command(tmperr)\n"
            "sys.argv = ['kitefs', 'tmperr']\n"
            "cli()\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert result.stdout == ""
        assert "Traceback" in result.stderr
        assert result.stderr.rstrip().endswith("RuntimeError: boom")


class TestUsageErrorBoundary:
    """click.UsageError is rendered by Click itself; the wrapper must not interfere."""

    def test_usage_error_rendered_by_click(self, monkeypatch, capsys, temp_command) -> None:
        """click.UsageError raised in a subcommand renders via Click's default formatting."""

        def raise_usage():
            raise click.UsageError("bad")

        temp_command("tmpusage", raise_usage)
        monkeypatch.setattr(sys, "argv", ["kitefs", "tmpusage"])

        with pytest.raises(SystemExit) as ei:
            cli()

        # Click's default exit code for UsageError is 2
        assert ei.value.code == 2
        out, err = capsys.readouterr()
        assert out == ""
        # Click writes "Error: bad" (its own prefix), NOT our "Error: " double-prefix
        assert "Error: bad" in err
        # Must not be wrapped by our boundary (would produce "Error: Error: bad" pattern)
        assert err.count("Error:") == 1


class TestImportIsolation:
    """Importing kitefs.cli must not pull in forbidden heavy modules."""

    def test_forbidden_modules_absent_after_import(self) -> None:
        """Fresh import of kitefs.cli loads only the allowed kitefs.* subset."""
        script = "import kitefs.cli, sys; mods = sorted(k for k in sys.modules if k.startswith('kitefs')); print(mods)"
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        imported = result.stdout.strip()
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
            assert mod not in imported, f"Forbidden module imported: {mod}"
