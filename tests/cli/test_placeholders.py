"""Tests for placeholder CLI commands that are not yet implemented."""

from click.testing import CliRunner

from kitefs.cli import cli

_MSG = "Not implemented yet, in development."


def _runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


class TestIngestPlaceholder:
    """``kitefs ingest`` shows a not-implemented message."""

    def test_ingest_shows_not_implemented_message(self) -> None:
        """ingest echoes the placeholder message and exits 0."""
        result = _runner().invoke(cli, ["ingest", "my_group", "data.csv"])

        assert result.exit_code == 0
        assert _MSG in result.output

    def test_ingest_help_exits_zero(self) -> None:
        """ingest --help exits with code 0."""
        result = _runner().invoke(cli, ["ingest", "--help"])

        assert result.exit_code == 0


class TestMaterializePlaceholder:
    """``kitefs materialize`` shows a not-implemented message."""

    def test_materialize_shows_not_implemented_message(self) -> None:
        """materialize echoes the placeholder message and exits 0."""
        result = _runner().invoke(cli, ["materialize"])

        assert result.exit_code == 0
        assert _MSG in result.output

    def test_materialize_with_group_shows_not_implemented_message(self) -> None:
        """materialize with a group name echoes the placeholder message."""
        result = _runner().invoke(cli, ["materialize", "my_group"])

        assert result.exit_code == 0
        assert _MSG in result.output

    def test_materialize_help_exits_zero(self) -> None:
        """materialize --help exits with code 0."""
        result = _runner().invoke(cli, ["materialize", "--help"])

        assert result.exit_code == 0


class TestRegistrySyncPlaceholder:
    """``kitefs registry-sync`` shows a not-implemented message."""

    def test_registry_sync_shows_not_implemented_message(self) -> None:
        """registry-sync echoes the placeholder message and exits 0."""
        result = _runner().invoke(cli, ["registry-sync"])

        assert result.exit_code == 0
        assert _MSG in result.output

    def test_registry_sync_help_exits_zero(self) -> None:
        """registry-sync --help exits with code 0."""
        result = _runner().invoke(cli, ["registry-sync", "--help"])

        assert result.exit_code == 0


class TestRegistryPullPlaceholder:
    """``kitefs registry-pull`` shows a not-implemented message."""

    def test_registry_pull_shows_not_implemented_message(self) -> None:
        """registry-pull echoes the placeholder message and exits 0."""
        result = _runner().invoke(cli, ["registry-pull"])

        assert result.exit_code == 0
        assert _MSG in result.output

    def test_registry_pull_help_exits_zero(self) -> None:
        """registry-pull --help exits with code 0."""
        result = _runner().invoke(cli, ["registry-pull", "--help"])

        assert result.exit_code == 0


class TestMockPlaceholder:
    """``kitefs mock`` shows a not-implemented message."""

    def test_mock_shows_not_implemented_message(self) -> None:
        """mock echoes the placeholder message and exits 0."""
        result = _runner().invoke(cli, ["mock"])

        assert result.exit_code == 0
        assert _MSG in result.output

    def test_mock_with_group_shows_not_implemented_message(self) -> None:
        """mock with a group name echoes the placeholder message."""
        result = _runner().invoke(cli, ["mock", "my_group"])

        assert result.exit_code == 0
        assert _MSG in result.output

    def test_mock_help_exits_zero(self) -> None:
        """mock --help exits with code 0."""
        result = _runner().invoke(cli, ["mock", "--help"])

        assert result.exit_code == 0


class TestSamplePlaceholder:
    """``kitefs sample`` shows a not-implemented message."""

    def test_sample_shows_not_implemented_message(self) -> None:
        """sample echoes the placeholder message and exits 0."""
        result = _runner().invoke(cli, ["sample", "my_group"])

        assert result.exit_code == 0
        assert _MSG in result.output

    def test_sample_help_exits_zero(self) -> None:
        """sample --help exits with code 0."""
        result = _runner().invoke(cli, ["sample", "--help"])

        assert result.exit_code == 0
