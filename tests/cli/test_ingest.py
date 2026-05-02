"""Tests for the ``kitefs ingest`` CLI command."""

from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from kitefs.cli import cli
from tests.helpers import LISTING_DEF, MINIMAL_DEF, TOWN_DEF, setup_project


def _runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


# Simple definition with no expectations for basic success tests.
_SIMPLE_DEF = MINIMAL_DEF.format(varname="simple_group", name="simple_group")

# Definition with a missing-column scenario for schema validation tests.
_STRICT_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup,
    FeatureType, StorageTarget, ValidationMode,
)

strict_group = FeatureGroup(
    name="strict_group",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[Feature(name="value", dtype=FeatureType.FLOAT)],
    ingestion_validation=ValidationMode.ERROR,
)
"""


def _make_simple_csv(tmp_path: Path, filename: str = "data.csv") -> Path:
    """Write a minimal CSV matching the simple_group schema and return its path."""
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "ts": ["2024-03-15", "2024-03-20"],
            "value": [10.0, 20.0],
        }
    )
    path = tmp_path / filename
    df.to_csv(path, index=False)
    return path


class TestIngestHelp:
    """``kitefs ingest --help`` shows command usage."""

    def test_help_exits_zero(self) -> None:
        """ingest --help exits with code 0."""
        result = _runner().invoke(cli, ["ingest", "--help"])

        assert result.exit_code == 0

    def test_help_shows_feature_group_name_argument(self) -> None:
        """ingest --help mentions FEATURE_GROUP_NAME."""
        result = _runner().invoke(cli, ["ingest", "--help"])

        assert "FEATURE_GROUP_NAME" in result.output

    def test_help_shows_file_path_argument(self) -> None:
        """ingest --help mentions FILE_PATH."""
        result = _runner().invoke(cli, ["ingest", "--help"])

        assert "FILE_PATH" in result.output


class TestIngestSuccess:
    """Successful ``kitefs ingest`` exits 0 and prints a summary."""

    def test_exit_code_is_zero(self, tmp_path: Path) -> None:
        """Successful ingest exits with code 0."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"simple.py": _SIMPLE_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            csv_path = _make_simple_csv(td_path)

            result = runner.invoke(cli, ["ingest", "simple_group", str(csv_path)], catch_exceptions=False)

        assert result.exit_code == 0

    def test_prints_row_count(self, tmp_path: Path) -> None:
        """Successful ingest prints the number of rows written."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"simple.py": _SIMPLE_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            csv_path = _make_simple_csv(td_path)

            result = runner.invoke(cli, ["ingest", "simple_group", str(csv_path)], catch_exceptions=False)

        assert "2" in result.output

    def test_prints_partition_info(self, tmp_path: Path) -> None:
        """Successful ingest prints the partitions affected."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"simple.py": _SIMPLE_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            csv_path = _make_simple_csv(td_path)

            result = runner.invoke(cli, ["ingest", "simple_group", str(csv_path)], catch_exceptions=False)

        assert "year=2024/month=03" in result.output

    def test_parquet_files_written_to_offline_store(self, tmp_path: Path) -> None:
        """Ingest via CSV writes Parquet files to the offline store directory."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"simple.py": _SIMPLE_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            csv_path = _make_simple_csv(td_path)

            runner.invoke(cli, ["ingest", "simple_group", str(csv_path)], catch_exceptions=False)

            offline_dir = td_path / "feature_store" / "data" / "offline_store" / "simple_group"
            parquet_files = list(offline_dir.rglob("*.parquet"))

        assert len(parquet_files) >= 1

    def test_listing_features_end_to_end(self, tmp_path: Path) -> None:
        """Full init→apply→ingest flow with listing_features definition exits 0."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            # listing_features references town_market_features via join key,
            # so both definitions must be applied together.
            setup_project(td_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)

            # Build a CSV matching the listing_features schema.
            df = pd.DataFrame(
                {
                    "listing_id": [1, 2],
                    "event_timestamp": ["2024-03-15", "2024-04-10"],
                    "net_area": [80, 120],
                    "number_of_rooms": [3, 5],
                    "build_year": [2010, 1985],
                    "sold_price": [500000.0, 750000.0],
                    "town_id": [1, 2],
                }
            )
            csv_path = td_path / "listings.csv"
            df.to_csv(csv_path, index=False)

            result = runner.invoke(cli, ["ingest", "listing_features", str(csv_path)], catch_exceptions=False)

        assert result.exit_code == 0
        assert "2" in result.output


class TestIngestOutsideProject:
    """``kitefs ingest`` outside a KiteFS project fails with exit 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Ingest outside a project exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            csv_path = Path(td) / "data.csv"
            csv_path.write_text("id,ts,value\n1,2024-01-01,1.0\n")

            result = runner.invoke(cli, ["ingest", "simple_group", str(csv_path)])

        assert result.exit_code == 1

    def test_error_message_mentions_init(self, tmp_path: Path) -> None:
        """Error message suggests running kitefs init."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            csv_path = Path(td) / "data.csv"
            csv_path.write_text("id,ts,value\n1,2024-01-01,1.0\n")

            result = runner.invoke(cli, ["ingest", "simple_group", str(csv_path)])

        combined = result.output + (result.stderr or "")
        assert "kitefs init" in combined.lower() or "no kitefs project" in combined.lower()


class TestIngestUnknownGroup:
    """``kitefs ingest`` with an unregistered feature group fails with exit 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Unknown feature group exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"simple.py": _SIMPLE_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            csv_path = _make_simple_csv(td_path)

            result = runner.invoke(cli, ["ingest", "nonexistent_group", str(csv_path)])

        assert result.exit_code == 1

    def test_error_mentions_group_name(self, tmp_path: Path) -> None:
        """Error message includes the unknown group name."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"simple.py": _SIMPLE_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)
            csv_path = _make_simple_csv(td_path)

            result = runner.invoke(cli, ["ingest", "nonexistent_group", str(csv_path)])

        combined = result.output + (result.stderr or "")
        assert "nonexistent_group" in combined


class TestIngestNonexistentFile:
    """``kitefs ingest`` with a nonexistent file path fails with exit 1."""

    def test_exit_code_is_one(self, tmp_path: Path) -> None:
        """Nonexistent file path exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"simple.py": _SIMPLE_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)

            result = runner.invoke(cli, ["ingest", "simple_group", str(td_path / "missing.csv")])

        assert result.exit_code == 1

    def test_error_mentions_file_path(self, tmp_path: Path) -> None:
        """Error message mentions the missing file path."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"simple.py": _SIMPLE_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)

            result = runner.invoke(cli, ["ingest", "simple_group", str(td_path / "missing.csv")])

        combined = result.output + (result.stderr or "")
        assert "missing.csv" in combined


class TestIngestSchemaValidationFailure:
    """``kitefs ingest`` with schema errors fails with exit 1."""

    def test_exit_code_is_one_on_missing_column(self, tmp_path: Path) -> None:
        """CSV missing a required column exits with code 1."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"strict.py": _STRICT_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)

            # CSV is missing the 'value' column.
            bad_csv = td_path / "bad.csv"
            bad_csv.write_text("id,ts\n1,2024-03-15\n")

            result = runner.invoke(cli, ["ingest", "strict_group", str(bad_csv)])

        assert result.exit_code == 1

    def test_error_message_on_missing_column(self, tmp_path: Path) -> None:
        """Error message for schema failure mentions the missing column."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            setup_project(td_path, {"strict.py": _STRICT_DEF})
            runner.invoke(cli, ["apply"], catch_exceptions=False)

            bad_csv = td_path / "bad.csv"
            bad_csv.write_text("id,ts\n1,2024-03-15\n")

            result = runner.invoke(cli, ["ingest", "strict_group", str(bad_csv)])

        combined = result.output + (result.stderr or "")
        assert "value" in combined
