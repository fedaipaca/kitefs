"""Unit tests for cross-definition validation."""

from __future__ import annotations

import pytest

from kitefs.definitions import (
    EntityKey,
    EventTimestamp,
    Feature,
    FeatureGroup,
    FeatureType,
    JoinKey,
    StorageTarget,
)
from kitefs.errors import DefinitionValidationError
from kitefs.registry.validation import validate_cross_definition
from tests.fixtures.definitions import build_listing_features, build_town_market_features


def _simple_group(
    name: str,
    *,
    entity_key_name: str = "id",
    entity_key_dtype: FeatureType = FeatureType.INTEGER,
    join_keys: list[JoinKey] | None = None,
) -> FeatureGroup:
    return FeatureGroup(
        name=name,
        storage_target=StorageTarget.OFFLINE,
        entity_key=EntityKey(name=entity_key_name, dtype=entity_key_dtype),
        event_timestamp=EventTimestamp(name="ts"),
        features=[Feature(name="value", dtype=FeatureType.FLOAT)],
        join_keys=join_keys,
    )


class TestValidCrossDefinition:
    """validate_cross_definition accepts a valid set of groups without raising."""

    def test_reference_use_case_passes(self) -> None:
        """The two reference feature groups form a valid set."""
        validate_cross_definition([build_listing_features(), build_town_market_features()])

    def test_single_group_no_join_key_passes(self) -> None:
        """A single group with no join keys is always valid at cross-definition level."""
        validate_cross_definition([_simple_group("standalone")])


class TestDuplicateGroupNames:
    """validate_cross_definition rejects duplicate group names."""

    def test_duplicate_name_raises_validation_error(self) -> None:
        """Two groups with the same name raise DefinitionValidationError."""
        groups = [_simple_group("same_name"), _simple_group("same_name")]

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition(groups)

        msg = str(exc_info.value)
        assert "same_name" in msg
        assert "duplicate" in msg

    def test_duplicate_message_includes_both_occurrences(self) -> None:
        """Error message identifies the duplicated group name."""
        groups = [_simple_group("dupe"), _simple_group("dupe"), _simple_group("unique")]

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition(groups)

        assert "dupe" in str(exc_info.value)


class TestReservedFieldNames:
    """validate_cross_definition rejects reserved Hive partition column names."""

    @pytest.mark.parametrize(
        "field_name",
        [
            pytest.param("year", id="reserved_year"),
            pytest.param("month", id="reserved_month"),
        ],
    )
    def test_reserved_feature_name_raises(self, field_name: str) -> None:
        """A feature named 'year' or 'month' violates the reserved-column rule."""
        group = FeatureGroup(
            name="my_group",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts"),
            features=[Feature(name=field_name, dtype=FeatureType.FLOAT)],
        )

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([group])

        assert field_name in str(exc_info.value)

    def test_reserved_entity_key_name_raises(self) -> None:
        """An entity key named 'year' violates the reserved-column rule."""
        group = FeatureGroup(
            name="my_group",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="year", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts"),
            features=[Feature(name="value", dtype=FeatureType.FLOAT)],
        )

        with pytest.raises(DefinitionValidationError):
            validate_cross_definition([group])


class TestJoinKeyValidation:
    """validate_cross_definition checks JoinKey.referenced_group and dtype."""

    def test_missing_referenced_group_raises(self) -> None:
        """A JoinKey pointing to a non-existent group raises DefinitionValidationError."""
        group = _simple_group(
            "listing",
            join_keys=[JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="missing_group")],
        )

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([group])

        msg = str(exc_info.value)
        assert "missing_group" in msg
        assert "referenced" in msg

    def test_dtype_mismatch_raises(self) -> None:
        """JoinKey dtype not matching the referenced group's EntityKey dtype raises."""
        target = _simple_group("target", entity_key_dtype=FeatureType.STRING)
        source = _simple_group(
            "source",
            join_keys=[JoinKey(name="ref_id", dtype=FeatureType.INTEGER, referenced_group="target")],
        )

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([source, target])

        msg = str(exc_info.value)
        assert "INTEGER" in msg
        assert "STRING" in msg

    def test_correct_join_key_passes(self) -> None:
        """A JoinKey with matching dtype and existing referenced group is valid."""
        target = _simple_group("target", entity_key_dtype=FeatureType.INTEGER)
        source = _simple_group(
            "source",
            join_keys=[JoinKey(name="ref_id", dtype=FeatureType.INTEGER, referenced_group="target")],
        )
        validate_cross_definition([source, target])


class TestAggregatedErrors:
    """validate_cross_definition collects all errors before raising."""

    def test_multiple_violations_all_reported(self) -> None:
        """Two distinct violations both appear in one DefinitionValidationError."""
        group_a = _simple_group("dupe")
        group_b = _simple_group("dupe")
        group_c = _simple_group(
            "with_bad_join",
            join_keys=[JoinKey(name="bad", dtype=FeatureType.INTEGER, referenced_group="nonexistent")],
        )

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([group_a, group_b, group_c])

        msg = str(exc_info.value)
        assert "dupe" in msg
        assert "nonexistent" in msg


class TestDefensiveStructuralChecks:
    """validate_cross_definition rejects per-group invariants bypassed after construction."""

    def test_invalid_event_timestamp_dtype_raises(self) -> None:
        """A group whose EventTimestamp.dtype was mutated to a non-DATETIME value is rejected."""
        group = _simple_group("my_group")
        group.event_timestamp.dtype = FeatureType.FLOAT  # mutate past constructor

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([group])

        msg = str(exc_info.value)
        assert "EventTimestamp" in msg or "DATETIME" in msg

    def test_invalid_entity_key_dtype_raises(self) -> None:
        """A group whose EntityKey.dtype was mutated to FLOAT is rejected."""
        group = _simple_group("my_group")
        group.entity_key.dtype = FeatureType.FLOAT  # mutate past constructor

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([group])

        msg = str(exc_info.value)
        assert "EntityKey" in msg or "INTEGER" in msg or "STRING" in msg

    def test_invalid_feature_dtype_raises(self) -> None:
        """A feature whose dtype was mutated to a non-FeatureType value is rejected."""
        group = _simple_group("my_group")
        group.features[0].dtype = "not_a_type"  # type: ignore[assignment]

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([group])

        assert "Feature" in str(exc_info.value) or "FeatureType" in str(exc_info.value)

    def test_empty_features_list_raises(self) -> None:
        """A group whose features list was cleared after construction is rejected."""
        group = _simple_group("my_group")
        group.features = []  # mutate past constructor

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([group])

        msg = str(exc_info.value)
        assert "at least one feature" in msg

    def test_too_many_join_keys_raises(self) -> None:
        """A group with more than one join key is rejected."""
        group = _simple_group("source")
        target = _simple_group("target")
        jk1 = JoinKey(name="ref1", dtype=FeatureType.INTEGER, referenced_group="target")
        jk2 = JoinKey(name="ref2", dtype=FeatureType.INTEGER, referenced_group="target")
        group.join_keys = [jk1, jk2]  # mutate past constructor

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([group, target])

        msg = str(exc_info.value)
        assert "join_key" in msg or "join key" in msg

    def test_duplicate_field_names_raises(self) -> None:
        """A group with a feature sharing the entity key's name is rejected."""
        group = _simple_group("my_group")
        group.features.append(Feature(name="id", dtype=FeatureType.FLOAT))  # "id" = entity_key.name

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([group])

        msg = str(exc_info.value)
        assert "duplicate" in msg and "id" in msg

    def test_invalid_group_name_identifier_raises(self) -> None:
        """A group whose name was mutated to a non-identifier string is rejected."""
        group = _simple_group("my_group")
        group.name = "123-invalid"  # mutate past constructor

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([group])

        assert "identifier" in str(exc_info.value)

    def test_multiple_structural_violations_all_reported(self) -> None:
        """Multiple per-group structural violations appear in one DefinitionValidationError."""
        group = _simple_group("my_group")
        group.event_timestamp.dtype = FeatureType.FLOAT  # bad dtype
        group.features = []  # no features

        with pytest.raises(DefinitionValidationError) as exc_info:
            validate_cross_definition([group])

        msg = str(exc_info.value)
        assert "EventTimestamp" in msg or "DATETIME" in msg
        assert "at least one feature" in msg
