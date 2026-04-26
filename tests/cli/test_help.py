"""Tests for CLI help output — top-level group and per-command help."""

from click.testing import CliRunner

from kitefs.cli import cli


def _runner() -> CliRunner:
    """Create a Click test runner with isolated filesystem disabled (we use tmp_path)."""
    return CliRunner()


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


class TestCLIHelpShowsApply:
    """The top-level help lists the apply command."""

    def test_help_shows_apply_command(self) -> None:
        """kitefs --help output includes the apply command."""
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "apply" in result.output


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


class TestCLIHelpShowsPlaceholderCommands:
    """The top-level help lists all placeholder commands."""

    def test_help_shows_ingest_command(self) -> None:
        """kitefs --help output includes the ingest command."""
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "ingest" in result.output

    def test_help_shows_materialize_command(self) -> None:
        """kitefs --help output includes the materialize command."""
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "materialize" in result.output

    def test_help_shows_registry_sync_command(self) -> None:
        """kitefs --help output includes the registry-sync command."""
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "registry-sync" in result.output

    def test_help_shows_registry_pull_command(self) -> None:
        """kitefs --help output includes the registry-pull command."""
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "registry-pull" in result.output

    def test_help_shows_mock_command(self) -> None:
        """kitefs --help output includes the mock command."""
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "mock" in result.output

    def test_help_shows_sample_command(self) -> None:
        """kitefs --help output includes the sample command."""
        result = _runner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "sample" in result.output
