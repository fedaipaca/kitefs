from click.testing import CliRunner

from kitefs.cli import main


class TestCliEntry:
    """Asserts the kitefs CLI entry point is wired and responsive."""

    def test_help_exits_zero(self) -> None:
        """kitefs --help exits with code 0."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0

    def test_help_produces_output(self) -> None:
        """kitefs --help prints non-empty usage text."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.output.strip()
