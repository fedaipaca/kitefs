"""Tests for the KiteFS registry module (src/kitefs/registry.py)."""

from pathlib import Path
from textwrap import dedent

import pytest

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
from kitefs.exceptions import DefinitionError
from kitefs.registry import _discover_definitions, _validate_definitions

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
