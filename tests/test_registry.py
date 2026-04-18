"""Tests for the KiteFS registry module (src/kitefs/registry.py)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent
from typing import cast
from unittest.mock import MagicMock

import pytest

from kitefs.config import Config
from kitefs.definitions import (
    EntityKey,
    EventTimestamp,
    Expect,
    Feature,
    FeatureGroup,
    FeatureType,
    JoinKey,
    Metadata,
    StorageTarget,
    ValidationMode,
)
from kitefs.exceptions import DefinitionError, FeatureGroupNotFoundError, ProviderError, RegistryError
from kitefs.providers.local import LocalProvider
from kitefs.registry import RegistryManager, _discover_definitions, _validate_definitions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_GROUP = dedent("""\
    from kitefs import (
        EntityKey, EventTimestamp, Feature, FeatureGroup,
        FeatureType, StorageTarget,
    )

    group = FeatureGroup(
        name="{name}",
        storage_target=StorageTarget.OFFLINE,
        entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
        event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
        features=[Feature(name="value", dtype=FeatureType.FLOAT)],
    )
""")


def _write_definition(directory: Path, filename: str, content: str) -> Path:
    """Write a Python definition file into *directory* and return the path."""
    path = directory / filename
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


class TestDiscoverDefinitionsSuccess:
    """Happy-path tests for _discover_definitions."""

    def test_discover_single_group(self, tmp_path: Path) -> None:
        defs = tmp_path / "definitions"
        defs.mkdir()
        _write_definition(defs, "my_group.py", _MINIMAL_GROUP.format(name="my_group"))

        result = _discover_definitions(defs)

        assert len(result) == 1
        assert result[0].name == "my_group"

    def test_discover_multiple_groups_across_files(self, tmp_path: Path) -> None:
        defs = tmp_path / "definitions"
        defs.mkdir()
        _write_definition(defs, "alpha.py", _MINIMAL_GROUP.format(name="alpha"))
        _write_definition(defs, "beta.py", _MINIMAL_GROUP.format(name="beta"))

        result = _discover_definitions(defs)

        assert len(result) == 2
        names = {g.name for g in result}
        assert names == {"alpha", "beta"}

    def test_discover_multiple_groups_in_single_file(self, tmp_path: Path) -> None:
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
        _write_definition(defs, "two_groups.py", content)

        result = _discover_definitions(defs)

        assert len(result) == 2
        names = {g.name for g in result}
        assert names == {"first", "second"}

    def test_init_py_skipped(self, tmp_path: Path) -> None:
        defs = tmp_path / "definitions"
        defs.mkdir()
        # __init__.py with a FeatureGroup that should be ignored
        _write_definition(defs, "__init__.py", _MINIMAL_GROUP.format(name="should_skip"))
        _write_definition(defs, "real.py", _MINIMAL_GROUP.format(name="real"))

        result = _discover_definitions(defs)

        assert len(result) == 1
        assert result[0].name == "real"

    def test_non_featuregroup_attributes_ignored(self, tmp_path: Path) -> None:
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
        _write_definition(defs, "mixed.py", content)

        result = _discover_definitions(defs)

        assert len(result) == 1
        assert result[0].name == "the_group"

    def test_non_py_files_ignored(self, tmp_path: Path) -> None:
        defs = tmp_path / "definitions"
        defs.mkdir()
        (defs / "notes.txt").write_text("some notes")
        (defs / "config.yaml").write_text("key: value")
        (defs / "README.md").write_text("# Readme")
        _write_definition(defs, "valid.py", _MINIMAL_GROUP.format(name="valid"))

        result = _discover_definitions(defs)

        assert len(result) == 1
        assert result[0].name == "valid"

    def test_discovery_order_deterministic(self, tmp_path: Path) -> None:
        """Groups are discovered in sorted filename order."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        # Write in reverse alphabetical order
        _write_definition(defs, "z_group.py", _MINIMAL_GROUP.format(name="z_group"))
        _write_definition(defs, "a_group.py", _MINIMAL_GROUP.format(name="a_group"))
        _write_definition(defs, "m_group.py", _MINIMAL_GROUP.format(name="m_group"))

        result = _discover_definitions(defs)

        # Files processed in sorted order: a_group.py, m_group.py, z_group.py
        assert [g.name for g in result] == ["a_group", "m_group", "z_group"]

    def test_no_featuregroup_file_alongside_valid_file(self, tmp_path: Path) -> None:
        """A file with only plain variables is skipped; the valid group is returned."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        _write_definition(
            defs,
            "constants.py",
            "ANSWER = 42\nMESSAGE = 'hello'\nSOME_LIST = [1, 2, 3]\n",
        )
        _write_definition(defs, "real.py", _MINIMAL_GROUP.format(name="real"))

        result = _discover_definitions(defs)

        assert len(result) == 1
        assert result[0].name == "real"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestDiscoverDefinitionsErrors:
    """Error-path tests for _discover_definitions."""

    def test_empty_directory_raises_definition_error(self, tmp_path: Path) -> None:
        defs = tmp_path / "definitions"
        defs.mkdir()

        with pytest.raises(DefinitionError, match=r"No feature group definitions found"):
            _discover_definitions(defs)

    def test_syntax_error_raises_definition_error_with_filepath(self, tmp_path: Path) -> None:
        defs = tmp_path / "definitions"
        defs.mkdir()
        _write_definition(defs, "broken.py", "def this is not valid python !!!")

        with pytest.raises(DefinitionError, match=r"broken\.py.*SyntaxError"):
            _discover_definitions(defs)

    def test_import_error_raises_definition_error_with_filepath(self, tmp_path: Path) -> None:
        defs = tmp_path / "definitions"
        defs.mkdir()
        _write_definition(defs, "bad_import.py", "import nonexistent_package_xyz_123")

        with pytest.raises(DefinitionError, match=r"bad_import\.py.*ModuleNotFoundError"):
            _discover_definitions(defs)

    def test_only_non_py_files_raises_definition_error(self, tmp_path: Path) -> None:
        defs = tmp_path / "definitions"
        defs.mkdir()
        (defs / "notes.txt").write_text("not python")
        (defs / "data.csv").write_text("a,b\n1,2")

        with pytest.raises(DefinitionError, match=r"No feature group definitions found"):
            _discover_definitions(defs)

    def test_only_init_py_raises_definition_error(self, tmp_path: Path) -> None:
        defs = tmp_path / "definitions"
        defs.mkdir()
        _write_definition(defs, "__init__.py", _MINIMAL_GROUP.format(name="hidden"))

        with pytest.raises(DefinitionError, match=r"No feature group definitions found"):
            _discover_definitions(defs)

    def test_multiple_import_errors_collected(self, tmp_path: Path) -> None:
        """All import errors are reported together, not just the first."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        _write_definition(defs, "bad_one.py", "def !!!")
        _write_definition(defs, "bad_two.py", "import nonexistent_xyz_abc")

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
        _write_definition(defs, "boom.py", "x = 1 / 0\n")

        with pytest.raises(DefinitionError, match=r"boom\.py.*ZeroDivisionError"):
            _discover_definitions(defs)

    def test_valid_file_alongside_broken_file_raises_definition_error(self, tmp_path: Path) -> None:
        """A broken file causes the whole operation to fail even when other files are valid."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        _write_definition(defs, "good.py", _MINIMAL_GROUP.format(name="good"))
        _write_definition(defs, "broken.py", "def this is not valid python !!!")

        with pytest.raises(DefinitionError) as exc_info:
            _discover_definitions(defs)

        message = str(exc_info.value)
        assert "broken.py" in message
        assert "good" not in message


# ---------------------------------------------------------------------------
# Reference use case
# ---------------------------------------------------------------------------


class TestDiscoverDefinitionsReferenceUseCase:
    """Verify discovery works with the reference use case definitions."""

    def test_reference_use_case_definitions_discovered(self, tmp_path: Path) -> None:
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

        _write_definition(defs, "listing_features.py", listing_content)
        _write_definition(defs, "town_market_features.py", town_content)

        result = _discover_definitions(defs)

        assert len(result) == 2
        names = {g.name for g in result}
        assert names == {"listing_features", "town_market_features"}


# ===========================================================================
# _validate_definitions tests
# ===========================================================================

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_group(
    name: str = "test_group",
    *,
    entity_key: EntityKey | None = None,
    event_timestamp: EventTimestamp | None = None,
    features: list[Feature] | None = None,
    join_keys: list[JoinKey] | None = None,
    storage_target: StorageTarget = StorageTarget.OFFLINE,
) -> FeatureGroup:
    """Build a minimal valid FeatureGroup, overriding individual fields as needed."""
    return FeatureGroup(
        name=name,
        storage_target=storage_target,
        entity_key=entity_key or EntityKey(name="id", dtype=FeatureType.INTEGER),
        event_timestamp=event_timestamp or EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
        features=features or [Feature(name="value", dtype=FeatureType.FLOAT)],
        join_keys=join_keys or [],
    )


# ---------------------------------------------------------------------------
# Individual group validation
# ---------------------------------------------------------------------------


class TestValidateDefinitionsIndividual:
    """Per-group structural validation rules."""

    def test_valid_single_group_returns_empty(self) -> None:
        errors = _validate_definitions([_make_group()])
        assert errors == []

    def test_empty_group_list_returns_empty(self) -> None:
        errors = _validate_definitions([])
        assert errors == []

    def test_event_timestamp_non_datetime_dtype_error(self) -> None:
        group = _make_group(
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.STRING),
        )

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "EventTimestamp" in errors[0]
        assert "DATETIME" in errors[0]
        assert "STRING" in errors[0]
        assert "test_group" in errors[0]

    def test_feature_invalid_dtype_error(self) -> None:
        """A feature with a non-FeatureType dtype is caught."""
        feature = Feature(name="bad_feat", dtype=FeatureType.INTEGER)
        # Inject an invalid dtype bypassing frozen protection.
        object.__setattr__(feature, "dtype", "NOT_A_TYPE")

        group = _make_group(features=[feature])

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "bad_feat" in errors[0]
        assert "invalid dtype" in errors[0]

    def test_duplicate_field_names_entity_key_and_feature(self) -> None:
        group = _make_group(
            entity_key=EntityKey(name="shared", dtype=FeatureType.INTEGER),
            features=[Feature(name="shared", dtype=FeatureType.FLOAT)],
        )

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "Duplicate field name 'shared'" in errors[0]

    def test_duplicate_field_names_event_timestamp_and_feature(self) -> None:
        group = _make_group(
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
            features=[Feature(name="ts", dtype=FeatureType.FLOAT)],
        )

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "Duplicate field name 'ts'" in errors[0]

    def test_duplicate_field_names_entity_key_and_event_timestamp(self) -> None:
        group = _make_group(
            entity_key=EntityKey(name="same", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="same", dtype=FeatureType.DATETIME),
        )

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "Duplicate field name 'same'" in errors[0]

    def test_multiple_individual_errors_in_one_group(self) -> None:
        """A group with both a bad timestamp dtype and duplicate names produces multiple errors."""
        group = _make_group(
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="id", dtype=FeatureType.STRING),
        )

        errors = _validate_definitions([group])

        assert len(errors) == 2
        assert any("EventTimestamp" in e for e in errors)
        assert any("Duplicate field name" in e for e in errors)

    def test_duplicate_feature_names_within_features(self) -> None:
        """Two features sharing the same name produce a duplicate field error."""
        group = _make_group(
            features=[
                Feature(name="dup_feat", dtype=FeatureType.FLOAT),
                Feature(name="dup_feat", dtype=FeatureType.INTEGER),
            ],
        )

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "Duplicate field name 'dup_feat'" in errors[0]


# ---------------------------------------------------------------------------
# Cross-group validation
# ---------------------------------------------------------------------------


class TestValidateDefinitionsCrossGroup:
    """Cross-group validation rules (duplicates and join keys)."""

    def test_duplicate_group_names_error(self) -> None:
        g1 = _make_group(name="dup")
        g2 = _make_group(name="dup")

        errors = _validate_definitions([g1, g2])

        assert any("Duplicate feature group name 'dup'" in e for e in errors)
        assert any("2 times" in e for e in errors)

    def test_join_key_references_nonexistent_group_error(self) -> None:
        group = _make_group(
            features=[Feature(name="fk", dtype=FeatureType.INTEGER)],
            join_keys=[JoinKey(field_name="fk", referenced_group="ghost")],
        )

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "non-existent group 'ghost'" in errors[0]

    def test_join_key_field_name_mismatch_error(self) -> None:
        """Join key field_name differs from referenced group's entity key name."""
        referenced = _make_group(
            name="ref_group",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        base = _make_group(
            name="base_group",
            features=[Feature(name="location_id", dtype=FeatureType.INTEGER)],
            join_keys=[JoinKey(field_name="location_id", referenced_group="ref_group")],
        )

        errors = _validate_definitions([base, referenced])

        assert len(errors) == 1
        assert "must match entity key name 'town_id'" in errors[0]
        assert "Rename the field to 'town_id'" in errors[0]

    def test_join_key_type_mismatch_error(self) -> None:
        """Join key field dtype differs from referenced entity key dtype."""
        referenced = _make_group(
            name="ref_group",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        base = _make_group(
            name="base_group",
            features=[Feature(name="town_id", dtype=FeatureType.STRING)],
            join_keys=[JoinKey(field_name="town_id", referenced_group="ref_group")],
        )

        errors = _validate_definitions([base, referenced])

        assert len(errors) == 1
        assert "STRING" in errors[0]
        assert "INTEGER" in errors[0]
        assert "base_group" in errors[0]
        assert "ref_group" in errors[0]

    def test_join_key_type_match_via_entity_key(self) -> None:
        """Type check finds the field on entity_key when names match."""
        referenced = _make_group(
            name="ref_group",
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
        )
        base = _make_group(
            name="base_group",
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            join_keys=[JoinKey(field_name="id", referenced_group="ref_group")],
        )

        errors = _validate_definitions([base, referenced])

        assert errors == []

    def test_join_key_valid_relationship_no_errors(self) -> None:
        """A correctly declared join key produces no errors."""
        town = _make_group(
            name="towns",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        listings = _make_group(
            name="listings",
            features=[Feature(name="town_id", dtype=FeatureType.INTEGER)],
            join_keys=[JoinKey(field_name="town_id", referenced_group="towns")],
        )

        errors = _validate_definitions([listings, town])

        assert errors == []

    def test_join_key_field_not_in_base_group_error(self) -> None:
        """Join key field doesn't exist in the base group despite name matching referenced entity key."""
        town = _make_group(
            name="town_market_features",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        listing = _make_group(
            name="listing_features",
            entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
            features=[
                Feature(name="net_area", dtype=FeatureType.FLOAT),
                Feature(name="sold_price", dtype=FeatureType.FLOAT),
            ],
            join_keys=[JoinKey(field_name="town_id", referenced_group="town_market_features")],
        )

        errors = _validate_definitions([listing, town])

        assert len(errors) == 1
        assert "does not exist as an entity_key or feature" in errors[0]
        assert "listing_features" in errors[0]
        assert "town_id" in errors[0]

    def test_multiple_join_keys_one_valid_one_invalid(self) -> None:
        """Only the invalid join key produces an error; the valid one passes."""
        region = _make_group(
            name="regions",
            entity_key=EntityKey(name="region_id", dtype=FeatureType.INTEGER),
        )
        town = _make_group(
            name="towns",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        listing = _make_group(
            name="listings",
            features=[
                Feature(name="town_id", dtype=FeatureType.INTEGER),
            ],
            join_keys=[
                JoinKey(field_name="town_id", referenced_group="towns"),
                JoinKey(field_name="region_id", referenced_group="regions"),
            ],
        )

        errors = _validate_definitions([listing, town, region])

        assert len(errors) == 1
        assert "region_id" in errors[0]
        assert "does not exist" in errors[0]

    def test_self_referencing_join_key(self) -> None:
        """A group referencing itself via its own entity key passes validation."""
        group = _make_group(
            name="categories",
            entity_key=EntityKey(name="category_id", dtype=FeatureType.INTEGER),
            join_keys=[JoinKey(field_name="category_id", referenced_group="categories")],
        )

        errors = _validate_definitions([group])

        assert errors == []

    def test_join_key_field_name_and_type_both_wrong(self) -> None:
        """Both name mismatch and type mismatch errors are collected for the same join key."""
        referenced = _make_group(
            name="ref_group",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        base = _make_group(
            name="base_group",
            features=[Feature(name="location_id", dtype=FeatureType.STRING)],
            join_keys=[JoinKey(field_name="location_id", referenced_group="ref_group")],
        )

        errors = _validate_definitions([base, referenced])

        assert len(errors) == 2
        assert any("must match entity key name 'town_id'" in e for e in errors)
        assert any("STRING" in e and "INTEGER" in e for e in errors)

    def test_three_duplicate_group_names(self) -> None:
        """Three groups with the same name report the correct count."""
        g1 = _make_group(name="dup")
        g2 = _make_group(name="dup")
        g3 = _make_group(name="dup")

        errors = _validate_definitions([g1, g2, g3])

        assert any("3 times" in e for e in errors)


# ---------------------------------------------------------------------------
# Collected errors
# ---------------------------------------------------------------------------


class TestValidateDefinitionsCollectedErrors:
    """Multiple errors from multiple groups are collected in one call."""

    def test_multiple_errors_from_multiple_groups(self) -> None:
        """Each group has a different error — all are returned together."""
        g1 = _make_group(
            name="bad_ts",
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.INTEGER),
        )
        g2 = _make_group(
            name="dup_fields",
            entity_key=EntityKey(name="x", dtype=FeatureType.INTEGER),
            features=[Feature(name="x", dtype=FeatureType.FLOAT)],
        )

        errors = _validate_definitions([g1, g2])

        assert len(errors) == 2
        assert any("bad_ts" in e for e in errors)
        assert any("dup_fields" in e for e in errors)

    def test_individual_and_cross_group_errors_collected(self) -> None:
        """Both per-group and cross-group errors appear in the result."""
        g1 = _make_group(
            name="same",
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.STRING),
        )
        g2 = _make_group(name="same")

        errors = _validate_definitions([g1, g2])

        has_ts_error = any("EventTimestamp" in e for e in errors)
        has_dup_error = any("Duplicate feature group name" in e for e in errors)
        assert has_ts_error
        assert has_dup_error
        assert len(errors) >= 2


# ---------------------------------------------------------------------------
# Reference use case
# ---------------------------------------------------------------------------


class TestValidateDefinitionsReferenceUseCase:
    """Reference use case definitions pass validation."""

    def test_reference_use_case_passes_validation(self) -> None:
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
                Feature(
                    name="net_area",
                    dtype=FeatureType.INTEGER,
                    description="Usable area in sqm",
                    expect=Expect().not_null().gt(0),
                ),
                Feature(
                    name="number_of_rooms",
                    dtype=FeatureType.INTEGER,
                    description="Number of rooms",
                    expect=Expect().not_null().gt(0),
                ),
                Feature(
                    name="build_year",
                    dtype=FeatureType.INTEGER,
                    description="Year the building was constructed",
                    expect=Expect().not_null().gte(1900).lte(2030),
                ),
                Feature(
                    name="sold_price",
                    dtype=FeatureType.FLOAT,
                    description="Sold price in TL (training label)",
                    expect=Expect().not_null().gt(0),
                ),
                Feature(name="town_id", dtype=FeatureType.INTEGER, description="Join key to town_market_features"),
            ],
            join_keys=[
                JoinKey(field_name="town_id", referenced_group="town_market_features"),
            ],
            ingestion_validation=ValidationMode.ERROR,
            offline_retrieval_validation=ValidationMode.NONE,
            metadata=Metadata(
                description="Historical sold listing attributes and prices",
                owner="data-science-team",
                tags={"domain": "real-estate", "cadence": "monthly"},
            ),
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
                Feature(
                    name="avg_price_per_sqm",
                    dtype=FeatureType.FLOAT,
                    description="Average sold price per sqm in this town last month",
                    expect=Expect().not_null().gt(0),
                ),
            ],
            ingestion_validation=ValidationMode.ERROR,
            offline_retrieval_validation=ValidationMode.NONE,
            metadata=Metadata(
                description="Monthly town-level market aggregate",
                owner="data-science-team",
                tags={"domain": "real-estate", "cadence": "monthly"},
            ),
        )

        errors = _validate_definitions([listing_features, town_market_features])

        assert errors == []


# ===========================================================================
# RegistryManager tests
# ===========================================================================

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path) -> Config:
    """Create a Config pointing at tmp_path with a local provider."""
    storage_root = tmp_path / "feature_store"
    storage_root.mkdir(parents=True, exist_ok=True)
    return Config(
        provider="local",
        project_root=tmp_path,
        storage_root=storage_root,
        definitions_path=storage_root / "definitions",
        aws=None,
    )


def _setup_manager(tmp_path: Path, seed_registry: bool = True) -> RegistryManager:
    """Create a RegistryManager backed by a LocalProvider in tmp_path.

    Optionally seeds an empty registry.json (mirrors what kitefs init does).
    """
    config = _make_config(tmp_path)
    config.definitions_path.mkdir(parents=True, exist_ok=True)

    if seed_registry:
        registry_path = config.storage_root / "registry.json"
        registry_path.write_text('{"version": "1.0", "feature_groups": {}}', encoding="utf-8")

    provider = LocalProvider(config)
    return RegistryManager(provider, config.definitions_path)


_MINIMAL_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup,
    FeatureType, StorageTarget,
)

{varname} = FeatureGroup(
    name="{name}",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[Feature(name="value", dtype=FeatureType.FLOAT)],
)
"""

_LISTING_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
    FeatureType, JoinKey, Metadata, StorageTarget, ValidationMode,
)

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER,
                         description="Unique identifier for each listing"),
    event_timestamp=EventTimestamp(name="event_timestamp", dtype=FeatureType.DATETIME,
                                   description="When the listing was sold"),
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
    join_keys=[JoinKey(field_name="town_id", referenced_group="town_market_features")],
    ingestion_validation=ValidationMode.ERROR,
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(
        description="Historical sold listing attributes and prices",
        owner="data-science-team",
        tags={"domain": "real-estate", "cadence": "monthly"},
    ),
)
"""

_TOWN_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
    FeatureType, Metadata, StorageTarget, ValidationMode,
)

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER,
                         description="Unique town identifier"),
    event_timestamp=EventTimestamp(name="event_timestamp", dtype=FeatureType.DATETIME,
                                   description="When this value became available"),
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
"""


# ---------------------------------------------------------------------------
# Successful apply
# ---------------------------------------------------------------------------


class TestRegistryManagerApplySuccess:
    """Happy-path tests for RegistryManager.apply()."""

    def test_apply_single_group_returns_apply_result(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "group.py").write_text(_MINIMAL_DEF.format(varname="group", name="my_group"))

        result = manager.apply()

        assert result.group_count == 1
        assert result.registered_groups == ("my_group",)

    def test_apply_multiple_groups_returns_all(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "alpha.py").write_text(_MINIMAL_DEF.format(varname="alpha", name="alpha"))
        (manager._definitions_path / "beta.py").write_text(_MINIMAL_DEF.format(varname="beta", name="beta"))

        result = manager.apply()

        assert result.group_count == 2
        assert result.registered_groups == ("alpha", "beta")

    def test_apply_writes_registry_json(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        config.definitions_path.mkdir(parents=True, exist_ok=True)
        registry_path = config.storage_root / "registry.json"
        registry_path.write_text('{"version": "1.0", "feature_groups": {}}', encoding="utf-8")

        provider = LocalProvider(config)
        manager = RegistryManager(provider, config.definitions_path)
        (manager._definitions_path / "group.py").write_text(_MINIMAL_DEF.format(varname="group", name="my_group"))
        manager.apply()

        data = json.loads(registry_path.read_text(encoding="utf-8"))
        assert data["version"] == "1.0"
        assert "my_group" in data["feature_groups"]

    def test_apply_version_field_is_1_0(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        assert manager._registry["version"] == "1.0"

    def test_applied_at_is_valid_iso8601(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        applied_at = manager._registry["feature_groups"]["g"]["applied_at"]
        # Must not raise — valid ISO 8601
        parsed = datetime.fromisoformat(applied_at)
        assert parsed is not None

    def test_last_materialized_at_null_for_new_group(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        assert manager._registry["feature_groups"]["g"]["last_materialized_at"] is None

    def test_last_materialized_at_preserved_on_reapply(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        # Simulate a materialization by manually setting the value in the registry file.
        registry_path = cast(LocalProvider, manager._provider)._registry_path
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        data["feature_groups"]["g"]["last_materialized_at"] = "2025-06-01T12:00:00+00:00"
        registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Re-load and re-apply.
        config2 = _make_config(tmp_path)
        provider2 = LocalProvider(config2)
        manager2 = RegistryManager(provider2, manager._definitions_path)
        manager2.apply()

        assert manager2._registry["feature_groups"]["g"]["last_materialized_at"] == "2025-06-01T12:00:00+00:00"

    def test_deleted_definition_vanishes_on_reapply(self, tmp_path: Path) -> None:
        """Groups whose definition file is removed no longer appear after re-apply."""
        manager = _setup_manager(tmp_path)
        def_alpha = manager._definitions_path / "alpha.py"
        def_beta = manager._definitions_path / "beta.py"
        def_alpha.write_text(_MINIMAL_DEF.format(varname="alpha", name="alpha"))
        def_beta.write_text(_MINIMAL_DEF.format(varname="beta", name="beta"))
        manager.apply()

        assert manager.group_exists("alpha")
        assert manager.group_exists("beta")

        def_beta.unlink()
        manager.apply()

        assert manager.group_exists("alpha")
        assert not manager.group_exists("beta")

    def test_deterministic_json_output(self, tmp_path: Path) -> None:
        """Applying the same definitions twice produces identical JSON (exc. applied_at)."""
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()
        registry_path = cast(LocalProvider, manager._provider)._registry_path
        first = json.loads(registry_path.read_text(encoding="utf-8"))

        manager.apply()
        second = json.loads(registry_path.read_text(encoding="utf-8"))

        # Strip volatile field before comparing structure.
        for data in (first, second):
            for group in data["feature_groups"].values():
                group.pop("applied_at", None)
        assert first == second

    def test_json_uses_sort_keys_and_indent_2(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        raw = cast(LocalProvider, manager._provider)._registry_path.read_text(encoding="utf-8")
        # Indented with 2 spaces: top-level keys start with two spaces.
        assert '\n  "' in raw
        # sort_keys=True: "feature_groups" (f) appears before "version" (v) at top level.
        assert raw.index('"feature_groups"') < raw.index('"version"')


# ---------------------------------------------------------------------------
# All-or-nothing behavior
# ---------------------------------------------------------------------------


class TestRegistryManagerApplyAllOrNothing:
    """Invalid definitions must leave the existing registry unchanged."""

    def test_invalid_definitions_raise_definition_error(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "bad.py").write_text("def this is broken!!!")

        with pytest.raises(DefinitionError):
            manager.apply()

    def test_invalid_definitions_leave_registry_unchanged(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        # First apply: register a valid group.
        (manager._definitions_path / "good.py").write_text(_MINIMAL_DEF.format(varname="good", name="good_group"))
        manager.apply()

        registry_path = cast(LocalProvider, manager._provider)._registry_path
        original_content = registry_path.read_text(encoding="utf-8")

        # Add a broken definition file alongside the valid one.
        (manager._definitions_path / "bad.py").write_text("def !!!invalid")

        with pytest.raises(DefinitionError):
            manager.apply()

        # Registry file must be byte-for-byte unchanged.
        assert registry_path.read_text(encoding="utf-8") == original_content

    def test_validation_errors_collected_before_raising(self, tmp_path: Path) -> None:
        """All definition errors appear in the single DefinitionError message."""
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "bad.py").write_text("import nonexistent_package_xyz_abc_123")

        with pytest.raises(DefinitionError, match=r"bad\.py"):
            manager.apply()


# ---------------------------------------------------------------------------
# Lookup methods
# ---------------------------------------------------------------------------


class TestRegistryManagerLookup:
    """Tests for get_group(), list_groups(), and group_exists()."""

    def test_get_group_returns_correct_feature_group(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="my_group"))
        manager.apply()

        group = manager.get_group("my_group")

        assert group.name == "my_group"
        assert group.entity_key.name == "id"
        assert group.event_timestamp.name == "ts"
        assert len(group.features) == 1
        assert group.features[0].name == "value"

    def test_get_group_unknown_name_raises(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)

        with pytest.raises(FeatureGroupNotFoundError, match=r"ghost"):
            manager.get_group("ghost")

    def test_get_group_actionable_error_message(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)

        with pytest.raises(FeatureGroupNotFoundError, match=r"kitefs apply"):
            manager.get_group("missing")

    def test_list_groups_empty_registry(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)

        assert manager.list_groups() == []

    def test_list_groups_returns_summaries(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="my_group"))
        manager.apply()

        summaries = manager.list_groups()

        assert len(summaries) == 1
        s = summaries[0]
        assert s["name"] == "my_group"
        assert s["entity_key"] == "id"
        assert s["storage_target"] == "OFFLINE"
        assert s["feature_count"] == 1

    def test_list_groups_multiple(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "a.py").write_text(_MINIMAL_DEF.format(varname="a", name="alpha"))
        (manager._definitions_path / "b.py").write_text(_MINIMAL_DEF.format(varname="b", name="beta"))
        manager.apply()

        names = {s["name"] for s in manager.list_groups()}
        assert names == {"alpha", "beta"}

    def test_group_exists_true(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="my_group"))
        manager.apply()

        assert manager.group_exists("my_group") is True

    def test_group_exists_false(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)

        assert manager.group_exists("nonexistent") is False

    def test_get_group_round_trips_expect_constraints(self, tmp_path: Path) -> None:
        """Expect constraints survive serialize → persist → deserialize."""
        content = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
    FeatureType, StorageTarget,
)
g = FeatureGroup(
    name="constrained",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[
        Feature(name="score", dtype=FeatureType.FLOAT,
                expect=Expect().not_null().gte(0.0).lte(1.0)),
        Feature(name="category", dtype=FeatureType.STRING,
                expect=Expect().one_of(["a", "b", "c"])),
    ],
)
"""
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(content)
        manager.apply()

        group = manager.get_group("constrained")

        score = next(f for f in group.features if f.name == "score")
        category = next(f for f in group.features if f.name == "category")
        assert score.expect is not None
        assert score.expect._constraints == (
            {"type": "not_null"},
            {"type": "gte", "value": 0.0},
            {"type": "lte", "value": 1.0},
        )
        assert category.expect is not None
        assert category.expect._constraints == ({"type": "one_of", "values": ("a", "b", "c")},)

    def test_get_group_none_expect_round_trips(self, tmp_path: Path) -> None:
        """A feature with no expectations deserializes back to expect=None."""
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        group = manager.get_group("g")
        assert group.features[0].expect is None


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class TestRegistryManagerStubs:
    """Stub methods raise NotImplementedError with informative messages."""

    def test_update_materialized_at_not_implemented(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        with pytest.raises(NotImplementedError, match=r"Task 18"):
            manager.update_materialized_at("any_group", datetime.now(UTC))

    def test_validate_query_params_not_implemented(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        with pytest.raises(NotImplementedError, match=r"Task"):
            manager.validate_query_params("g", "*", None, None, "get_historical_features")


# ---------------------------------------------------------------------------
# _load_registry error handling
# ---------------------------------------------------------------------------


class TestRegistryManagerLoadRegistry:
    """Tests for RegistryManager._load_registry() error handling."""

    def test_absent_registry_returns_empty_registry(self, tmp_path: Path) -> None:
        """No registry.json on disk — manager starts with an empty registry dict."""
        manager = _setup_manager(tmp_path, seed_registry=False)

        assert manager._registry == {"version": "1.0", "feature_groups": {}}

    def test_absent_registry_apply_creates_file(self, tmp_path: Path) -> None:
        """apply() succeeds and creates registry.json when no file existed before."""
        manager = _setup_manager(tmp_path, seed_registry=False)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="g"))

        result = manager.apply()

        assert result.group_count == 1
        registry_path = cast(LocalProvider, manager._provider)._registry_path
        assert registry_path.exists()
        assert json.loads(registry_path.read_text(encoding="utf-8"))["version"] == "1.0"

    def test_malformed_registry_raises_registry_error(self, tmp_path: Path) -> None:
        """A corrupt registry.json raises RegistryError on construction."""
        config = _make_config(tmp_path)
        config.definitions_path.mkdir(parents=True, exist_ok=True)
        (config.storage_root / "registry.json").write_text("{invalid json!!!", encoding="utf-8")

        with pytest.raises(RegistryError, match=r"invalid JSON"):
            RegistryManager(LocalProvider(config), config.definitions_path)

    def test_io_error_during_load_raises_registry_error(self, tmp_path: Path) -> None:
        """A genuine I/O failure from the provider raises RegistryError, not silent fallback."""
        config = _make_config(tmp_path)
        config.definitions_path.mkdir(parents=True, exist_ok=True)

        provider = MagicMock()
        io_cause = OSError("Permission denied")
        provider.read_registry.side_effect = ProviderError("Failed to read registry: Permission denied.").__class__(
            "Failed to read registry: Permission denied."
        )
        # Attach the cause so _load_registry can distinguish it from "not found".
        provider.read_registry.side_effect = _make_provider_error_with_cause(
            "Failed to read registry: Permission denied.", io_cause
        )

        with pytest.raises(RegistryError, match=r"could not be read"):
            RegistryManager(provider, config.definitions_path)


def _make_provider_error_with_cause(message: str, cause: Exception) -> ProviderError:
    """Create a ProviderError with an explicit __cause__ for testing."""
    exc = ProviderError(message)
    exc.__cause__ = cause
    return exc


# ---------------------------------------------------------------------------
# applied_at timezone and new-group null materialized_at
# ---------------------------------------------------------------------------


class TestRegistryManagerApplyTimestamps:
    """Tests for applied_at timezone correctness and last_materialized_at edge cases."""

    def test_applied_at_is_utc_timezone_aware(self, tmp_path: Path) -> None:
        """applied_at must be a timezone-aware ISO 8601 string (UTC)."""
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(_MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        applied_at = manager._registry["feature_groups"]["g"]["applied_at"]
        parsed = datetime.fromisoformat(applied_at)
        assert parsed.tzinfo is not None

    def test_new_group_gets_null_materialized_at_alongside_existing(self, tmp_path: Path) -> None:
        """When a new group is added via re-apply, it gets null last_materialized_at
        while the existing group's last_materialized_at is preserved."""
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "existing.py").write_text(_MINIMAL_DEF.format(varname="existing", name="existing"))
        manager.apply()

        # Simulate materialization of the existing group.
        registry_path = cast(LocalProvider, manager._provider)._registry_path
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        data["feature_groups"]["existing"]["last_materialized_at"] = "2025-06-01T12:00:00+00:00"
        registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Create a fresh manager (to pick up the file change) and add a second group.
        config2 = _make_config(tmp_path)
        provider2 = LocalProvider(config2)
        manager2 = RegistryManager(provider2, manager._definitions_path)
        (manager2._definitions_path / "newgroup.py").write_text(
            _MINIMAL_DEF.format(varname="newgroup", name="newgroup")
        )
        manager2.apply()

        fg = manager2._registry["feature_groups"]
        assert fg["existing"]["last_materialized_at"] == "2025-06-01T12:00:00+00:00"
        assert fg["newgroup"]["last_materialized_at"] is None


# ---------------------------------------------------------------------------
# get_group enum deserialization
# ---------------------------------------------------------------------------


class TestRegistryManagerGetGroupDeserialization:
    """Tests that get_group() returns correctly typed enum values, not raw strings."""

    def test_get_group_deserializes_storage_target_and_validation_modes(self, tmp_path: Path) -> None:
        """storage_target, ingestion_validation, and offline_retrieval_validation
        are deserialized back to enum members, not left as strings.
        """
        content = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup,
    FeatureType, StorageTarget, ValidationMode,
)
g = FeatureGroup(
    name="typed_group",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[Feature(name="v", dtype=FeatureType.FLOAT)],
    ingestion_validation=ValidationMode.FILTER,
    offline_retrieval_validation=ValidationMode.ERROR,
)
"""
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(content)
        manager.apply()

        group = manager.get_group("typed_group")

        assert group.storage_target is StorageTarget.OFFLINE_AND_ONLINE
        assert group.ingestion_validation is ValidationMode.FILTER
        assert group.offline_retrieval_validation is ValidationMode.ERROR


# ---------------------------------------------------------------------------
# Reference use case
# ---------------------------------------------------------------------------


class TestRegistryManagerReferenceUseCase:
    """Full reference use case produces a correct registry."""

    def test_reference_use_case_apply_succeeds(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "listing_features.py").write_text(_LISTING_DEF)
        (manager._definitions_path / "town_market_features.py").write_text(_TOWN_DEF)

        result = manager.apply()

        assert result.group_count == 2
        assert set(result.registered_groups) == {"listing_features", "town_market_features"}

    def test_reference_use_case_registry_structure(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "listing_features.py").write_text(_LISTING_DEF)
        (manager._definitions_path / "town_market_features.py").write_text(_TOWN_DEF)
        manager.apply()

        registry = manager._registry
        assert registry["version"] == "1.0"

        listing = registry["feature_groups"]["listing_features"]
        assert listing["storage_target"] == "OFFLINE"
        assert listing["entity_key"]["name"] == "listing_id"
        assert listing["entity_key"]["dtype"] == "INTEGER"
        assert listing["event_timestamp"]["dtype"] == "DATETIME"
        assert listing["ingestion_validation"] == "ERROR"
        assert listing["last_materialized_at"] is None
        assert len(listing["features"]) == 5
        assert listing["join_keys"] == [{"field_name": "town_id", "referenced_group": "town_market_features"}]

        town = registry["feature_groups"]["town_market_features"]
        assert town["storage_target"] == "OFFLINE_AND_ONLINE"
        assert town["entity_key"]["name"] == "town_id"

    def test_reference_use_case_get_group_round_trip(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "listing_features.py").write_text(_LISTING_DEF)
        (manager._definitions_path / "town_market_features.py").write_text(_TOWN_DEF)
        manager.apply()

        listing = manager.get_group("listing_features")
        town = manager.get_group("town_market_features")

        assert listing.name == "listing_features"
        assert listing.entity_key.name == "listing_id"
        assert len(listing.features) == 5
        assert len(listing.join_keys) == 1
        assert listing.join_keys[0].referenced_group == "town_market_features"
        assert listing.metadata.owner == "data-science-team"

        assert town.name == "town_market_features"
        assert town.storage_target.value == "OFFLINE_AND_ONLINE"
        assert town.features[0].expect is not None

    def test_reference_use_case_list_groups(self, tmp_path: Path) -> None:
        manager = _setup_manager(tmp_path)
        (manager._definitions_path / "listing_features.py").write_text(_LISTING_DEF)
        (manager._definitions_path / "town_market_features.py").write_text(_TOWN_DEF)
        manager.apply()

        summaries = manager.list_groups()
        by_name = {s["name"]: s for s in summaries}

        assert by_name["listing_features"]["feature_count"] == 5
        assert by_name["listing_features"]["owner"] == "data-science-team"
        assert by_name["town_market_features"]["storage_target"] == "OFFLINE_AND_ONLINE"
        assert by_name["town_market_features"]["entity_key"] == "town_id"
