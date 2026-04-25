"""Tests for registry definition discovery."""

from pathlib import Path
from textwrap import dedent

import pytest
from helpers import MINIMAL_GROUP, write_definition

from kitefs.exceptions import DefinitionError
from kitefs.registry import _discover_definitions


class TestDiscoverDefinitionsSuccess:
    """Happy-path tests for _discover_definitions."""

    def test_discover_single_group(self, tmp_path: Path) -> None:
        """A single .py file with a FeatureGroup is discovered."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        write_definition(defs, "my_group.py", MINIMAL_GROUP.format(name="my_group"))

        result = _discover_definitions(defs)

        assert len(result) == 1
        assert result[0].name == "my_group"

    def test_discover_multiple_groups_across_files(self, tmp_path: Path) -> None:
        """Multiple .py files each with a FeatureGroup are all discovered."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        write_definition(defs, "alpha.py", MINIMAL_GROUP.format(name="alpha"))
        write_definition(defs, "beta.py", MINIMAL_GROUP.format(name="beta"))

        result = _discover_definitions(defs)

        assert len(result) == 2
        names = {g.name for g in result}
        assert names == {"alpha", "beta"}

    def test_discover_multiple_groups_in_single_file(self, tmp_path: Path) -> None:
        """Two FeatureGroup instances in one file are both discovered."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        content = dedent("""\
            from kitefs import (
                EntityKey, EventTimestamp, Feature, FeatureGroup,
                FeatureType, StorageTarget,
            )

            first = FeatureGroup(
                name="first",
                storage_target=StorageTarget.OFFLINE,
                entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
                event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
                features=[Feature(name="v", dtype=FeatureType.FLOAT)],
            )

            second = FeatureGroup(
                name="second",
                storage_target=StorageTarget.OFFLINE,
                entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
                event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
                features=[Feature(name="v", dtype=FeatureType.FLOAT)],
            )
        """)
        write_definition(defs, "two_groups.py", content)

        result = _discover_definitions(defs)

        assert len(result) == 2
        names = {g.name for g in result}
        assert names == {"first", "second"}

    def test_init_py_skipped(self, tmp_path: Path) -> None:
        """__init__.py files are skipped during discovery."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        # __init__.py with a FeatureGroup that should be ignored
        write_definition(defs, "__init__.py", MINIMAL_GROUP.format(name="should_skip"))
        write_definition(defs, "real.py", MINIMAL_GROUP.format(name="real"))

        result = _discover_definitions(defs)

        assert len(result) == 1
        assert result[0].name == "real"

    def test_non_featuregroup_attributes_ignored(self, tmp_path: Path) -> None:
        """Non-FeatureGroup module attributes are ignored."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        content = dedent("""\
            from kitefs import (
                EntityKey, EventTimestamp, Feature, FeatureGroup,
                FeatureType, StorageTarget,
            )

            SOME_STRING = "hello"
            SOME_INT = 42
            SOME_LIST = [1, 2, 3]

            group = FeatureGroup(
                name="the_group",
                storage_target=StorageTarget.OFFLINE,
                entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
                event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
                features=[Feature(name="v", dtype=FeatureType.FLOAT)],
            )
        """)
        write_definition(defs, "mixed.py", content)

        result = _discover_definitions(defs)

        assert len(result) == 1
        assert result[0].name == "the_group"

    def test_non_py_files_ignored(self, tmp_path: Path) -> None:
        """Non-.py files are ignored during discovery."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        (defs / "notes.txt").write_text("some notes")
        (defs / "config.yaml").write_text("key: value")
        (defs / "README.md").write_text("# Readme")
        write_definition(defs, "valid.py", MINIMAL_GROUP.format(name="valid"))

        result = _discover_definitions(defs)

        assert len(result) == 1
        assert result[0].name == "valid"

    def test_discovery_order_deterministic(self, tmp_path: Path) -> None:
        """Groups are discovered in sorted filename order."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        # Write in reverse alphabetical order
        write_definition(defs, "z_group.py", MINIMAL_GROUP.format(name="z_group"))
        write_definition(defs, "a_group.py", MINIMAL_GROUP.format(name="a_group"))
        write_definition(defs, "m_group.py", MINIMAL_GROUP.format(name="m_group"))

        result = _discover_definitions(defs)

        # Files processed in sorted order: a_group.py, m_group.py, z_group.py
        assert [g.name for g in result] == ["a_group", "m_group", "z_group"]

    def test_no_featuregroup_file_alongside_valid_file(self, tmp_path: Path) -> None:
        """A file with only plain variables is skipped; the valid group is returned."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        write_definition(
            defs,
            "constants.py",
            "ANSWER = 42\nMESSAGE = 'hello'\nSOME_LIST = [1, 2, 3]\n",
        )
        write_definition(defs, "real.py", MINIMAL_GROUP.format(name="real"))

        result = _discover_definitions(defs)

        assert len(result) == 1
        assert result[0].name == "real"


class TestDiscoverDefinitionsErrors:
    """Error-path tests for _discover_definitions."""

    def test_empty_directory_raises_definition_error(self, tmp_path: Path) -> None:
        """An empty definitions directory raises DefinitionError."""
        defs = tmp_path / "definitions"
        defs.mkdir()

        with pytest.raises(DefinitionError, match=r"No feature group definitions found"):
            _discover_definitions(defs)

    def test_syntax_error_raises_definition_error_with_filepath(self, tmp_path: Path) -> None:
        """A file with a syntax error raises DefinitionError naming the file."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        write_definition(defs, "broken.py", "def this is not valid python !!!")

        with pytest.raises(DefinitionError, match=r"broken\.py.*SyntaxError"):
            _discover_definitions(defs)

    def test_import_error_raises_definition_error_with_filepath(self, tmp_path: Path) -> None:
        """A file with a missing import raises DefinitionError naming the file."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        write_definition(defs, "bad_import.py", "import nonexistent_package_xyz_123")

        with pytest.raises(DefinitionError, match=r"bad_import\.py.*ModuleNotFoundError"):
            _discover_definitions(defs)

    def test_only_non_py_files_raises_definition_error(self, tmp_path: Path) -> None:
        """A directory with only non-.py files raises DefinitionError."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        (defs / "notes.txt").write_text("not python")
        (defs / "data.csv").write_text("a,b\n1,2")

        with pytest.raises(DefinitionError, match=r"No feature group definitions found"):
            _discover_definitions(defs)

    def test_only_init_py_raises_definition_error(self, tmp_path: Path) -> None:
        """A directory with only __init__.py raises DefinitionError."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        write_definition(defs, "__init__.py", MINIMAL_GROUP.format(name="hidden"))

        with pytest.raises(DefinitionError, match=r"No feature group definitions found"):
            _discover_definitions(defs)

    def test_multiple_import_errors_collected(self, tmp_path: Path) -> None:
        """All import errors are reported together, not just the first."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        write_definition(defs, "bad_one.py", "def !!!")
        write_definition(defs, "bad_two.py", "import nonexistent_xyz_abc")

        with pytest.raises(DefinitionError) as exc_info:
            _discover_definitions(defs)

        message = str(exc_info.value)
        assert "bad_one.py" in message
        assert "bad_two.py" in message

    def test_nonexistent_directory_raises_definition_error(self, tmp_path: Path) -> None:
        """A path that does not exist raises DefinitionError instead of FileNotFoundError."""
        missing = tmp_path / "does_not_exist"

        with pytest.raises(DefinitionError, match=r"does_not_exist"):
            _discover_definitions(missing)

    def test_runtime_error_in_definition_file(self, tmp_path: Path) -> None:
        """A file that raises at module-level produces DefinitionError with the filename."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        write_definition(defs, "boom.py", "x = 1 / 0\n")

        with pytest.raises(DefinitionError, match=r"boom\.py.*ZeroDivisionError"):
            _discover_definitions(defs)

    def test_valid_file_alongside_broken_file_raises_definition_error(self, tmp_path: Path) -> None:
        """A broken file causes the whole operation to fail even when other files are valid."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        write_definition(defs, "good.py", MINIMAL_GROUP.format(name="good"))
        write_definition(defs, "broken.py", "def this is not valid python !!!")

        with pytest.raises(DefinitionError) as exc_info:
            _discover_definitions(defs)

        message = str(exc_info.value)
        assert "broken.py" in message
        assert "good" not in message


class TestDiscoverDefinitionsReferenceUseCase:
    """Verify discovery works with the reference use case definitions."""

    def test_reference_use_case_definitions_discovered(self, tmp_path: Path) -> None:
        """Both reference use case feature groups are discovered from definition files."""
        defs = tmp_path / "definitions"
        defs.mkdir()

        listing_content = dedent("""\
            from kitefs import (
                EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
                FeatureType, JoinKey, Metadata, StorageTarget, ValidationMode,
            )

            listing_features = FeatureGroup(
                name="listing_features",
                storage_target=StorageTarget.OFFLINE,
                entity_key=EntityKey(
                    name="listing_id",
                    dtype=FeatureType.INTEGER,
                    description="Unique identifier for each listing",
                ),
                event_timestamp=EventTimestamp(
                    name="event_timestamp",
                    dtype=FeatureType.DATETIME,
                    description="When the listing was sold",
                ),
                features=[
                    Feature(name="net_area", dtype=FeatureType.INTEGER,
                            description="Usable area in sqm",
                            expect=Expect().not_null().gt(0)),
                    Feature(name="number_of_rooms", dtype=FeatureType.INTEGER,
                            description="Number of rooms",
                            expect=Expect().not_null().gt(0)),
                    Feature(name="build_year", dtype=FeatureType.INTEGER,
                            description="Year the building was constructed",
                            expect=Expect().not_null().gte(1900).lte(2030)),
                    Feature(name="sold_price", dtype=FeatureType.FLOAT,
                            description="Sold price in TL (training label)",
                            expect=Expect().not_null().gt(0)),
                    Feature(name="town_id", dtype=FeatureType.INTEGER,
                            description="Join key to town_market_features"),
                ],
                join_keys=[
                    JoinKey(field_name="town_id",
                            referenced_group="town_market_features"),
                ],
                ingestion_validation=ValidationMode.ERROR,
                offline_retrieval_validation=ValidationMode.NONE,
                metadata=Metadata(
                    description="Historical sold listing attributes and prices",
                    owner="data-science-team",
                    tags={"domain": "real-estate", "cadence": "monthly"},
                ),
            )
        """)

        town_content = dedent("""\
            from kitefs import (
                EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
                FeatureType, Metadata, StorageTarget, ValidationMode,
            )

            town_market_features = FeatureGroup(
                name="town_market_features",
                storage_target=StorageTarget.OFFLINE_AND_ONLINE,
                entity_key=EntityKey(
                    name="town_id",
                    dtype=FeatureType.INTEGER,
                    description="Unique town identifier",
                ),
                event_timestamp=EventTimestamp(
                    name="event_timestamp",
                    dtype=FeatureType.DATETIME,
                    description="When this value became available",
                ),
                features=[
                    Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT,
                            description="Average sold price per sqm in this town last month",
                            expect=Expect().not_null().gt(0)),
                ],
                ingestion_validation=ValidationMode.ERROR,
                offline_retrieval_validation=ValidationMode.NONE,
                metadata=Metadata(
                    description="Monthly town-level market aggregate",
                    owner="data-science-team",
                    tags={"domain": "real-estate", "cadence": "monthly"},
                ),
            )
        """)

        write_definition(defs, "listing_features.py", listing_content)
        write_definition(defs, "town_market_features.py", town_content)

        result = _discover_definitions(defs)

        assert len(result) == 2
        names = {g.name for g in result}
        assert names == {"listing_features", "town_market_features"}
