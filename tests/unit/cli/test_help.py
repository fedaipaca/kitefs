import pytest
from click.testing import CliRunner

from kitefs.cli import main


class TestCliHelp:
    """Unit tests for --help output and no-subcommand behavior."""

    def test_help_exits_zero(self) -> None:
        """kitefs --help exits with code 0."""
        result = CliRunner().invoke(main, ["--help"])
        assert result.exit_code == 0

    def test_help_prints_usage_to_stdout(self) -> None:
        """kitefs --help prints usage block to stdout."""
        result = CliRunner().invoke(main, ["--help"])
        assert "Usage:" in result.stdout

    def test_no_subcommand_exits_nonzero(self) -> None:
        """kitefs with no arguments exits with a non-zero code."""
        result = CliRunner().invoke(main, [])
        assert result.exit_code != 0

    def test_no_subcommand_stdout_is_empty(self) -> None:
        """kitefs with no arguments produces no stdout output."""
        result = CliRunner().invoke(main, [])
        assert result.stdout == ""

    def test_no_subcommand_stderr_is_nonempty(self) -> None:
        """kitefs with no arguments writes usage information to stderr."""
        result = CliRunner().invoke(main, [])
        assert result.stderr


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["apply", "--help"], id="apply"),
        pytest.param(["ingest", "--help"], id="ingest"),
        pytest.param(["materialize", "--help"], id="materialize"),
    ],
)
class TestNewCommandHelp:
    """New CLI commands expose --help and document key options."""

    def test_help_exits_zero(self, args: list[str]) -> None:
        """--help exits with code 0 for each new command."""
        result = CliRunner().invoke(main, args)
        assert result.exit_code == 0

    def test_help_mentions_format_option(self, args: list[str]) -> None:
        """--format option is advertised in --help output."""
        result = CliRunner().invoke(main, args)
        assert "--format" in result.output


class TestApplyHelpOptions:
    """kitefs apply --help documents publish and no-confirm options."""

    def test_help_mentions_publish(self) -> None:
        """--publish option is documented."""
        result = CliRunner().invoke(main, ["apply", "--help"])
        assert "--publish" in result.output

    def test_help_mentions_no_confirm(self) -> None:
        """--no-confirm option is documented."""
        result = CliRunner().invoke(main, ["apply", "--help"])
        assert "--no-confirm" in result.output
