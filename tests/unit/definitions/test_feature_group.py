import pytest

from kitefs import (
    DefinitionError,
    EntityKey,
    EventTimestamp,
    Feature,
    FeatureGroup,
    FeatureType,
    JoinKey,
    StorageTarget,
    ValidationMode,
)
from tests.fixtures.definitions import build_listing_features, build_town_market_features


def _minimal_group(
    name: str = "valid_group",
    features: list[Feature] | None = None,
    join_keys: list[JoinKey] | None = None,
) -> FeatureGroup:
    """Builds the smallest valid FeatureGroup for tests that don't care about content."""
    return FeatureGroup(
        name=name,
        storage_target=StorageTarget.OFFLINE,
        entity_key=EntityKey(name="entity_id", dtype=FeatureType.INTEGER),
        event_timestamp=EventTimestamp(name="event_ts"),
        features=features if features is not None else [Feature(name="value", dtype=FeatureType.FLOAT)],
        join_keys=join_keys,
    )


class TestFeatureGroupName:
    """FeatureGroup validates its name against the CON-009 identifier regex."""

    @pytest.mark.parametrize(
        "bad_name",
        [
            pytest.param("123-invalid", id="starts_with_digit_and_dash"),
            pytest.param("foo-bar", id="contains_dash"),
            pytest.param("with space", id="contains_space"),
            pytest.param("", id="empty_string"),
        ],
    )
    def test_rejects_invalid_name(self, bad_name: str) -> None:
        """FeatureGroup raises DefinitionError for names that are not valid identifiers."""
        with pytest.raises(DefinitionError) as exc_info:
            _minimal_group(name=bad_name)
        msg = str(exc_info.value)
        assert bad_name in msg
        assert "identifier" in msg

    @pytest.mark.parametrize(
        "good_name",
        [
            pytest.param("listing_features", id="snake_case"),
            pytest.param("_internal", id="underscore_prefix"),
            pytest.param("Group1", id="camel_with_digit"),
        ],
    )
    def test_accepts_valid_name(self, good_name: str) -> None:
        """FeatureGroup accepts valid identifier names."""
        group = _minimal_group(name=good_name)
        assert group.name == good_name


class TestFeatureGroupFeatures:
    """FeatureGroup requires at least one feature."""

    def test_rejects_empty_features(self) -> None:
        """FeatureGroup raises DefinitionError when features list is empty."""
        with pytest.raises(DefinitionError):
            _minimal_group(features=[])


class TestFeatureGroupJoinKeys:
    """FeatureGroup allows None, empty, or single join_keys only."""

    def test_accepts_none_join_keys(self) -> None:
        """join_keys=None is valid."""
        group = _minimal_group(join_keys=None)
        assert group.join_keys == []

    def test_accepts_empty_join_keys(self) -> None:
        """join_keys=[] is valid."""
        group = _minimal_group(join_keys=[])
        assert group.join_keys == []

    def test_accepts_single_join_key(self) -> None:
        """A single join key is valid."""
        group = _minimal_group(join_keys=[JoinKey(name="ref_id", dtype=FeatureType.INTEGER, referenced_group="other")])
        assert len(group.join_keys) == 1

    def test_rejects_two_join_keys(self) -> None:
        """FeatureGroup raises DefinitionError when join_keys has more than one entry."""
        with pytest.raises(DefinitionError):
            _minimal_group(
                join_keys=[
                    JoinKey(name="ref_a", dtype=FeatureType.INTEGER, referenced_group="group_a"),
                    JoinKey(name="ref_b", dtype=FeatureType.INTEGER, referenced_group="group_b"),
                ]
            )


class TestFeatureGroupFieldUniqueness:
    """FeatureGroup enforces unique field names across all slots."""

    def test_rejects_duplicate_entity_key_and_feature_name(self) -> None:
        """DefinitionError when entity_key and a feature share the same name."""
        with pytest.raises(DefinitionError) as exc_info:
            FeatureGroup(
                name="listing_features",
                storage_target=StorageTarget.OFFLINE,
                entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
                event_timestamp=EventTimestamp(name="sold_at"),
                features=[Feature(name="listing_id", dtype=FeatureType.FLOAT)],
            )
        msg = str(exc_info.value)
        assert "listing_id" in msg
        assert "duplicate" in msg

    def test_rejects_duplicate_event_timestamp_and_feature_name(self) -> None:
        """DefinitionError when event_timestamp and a feature share the same name."""
        with pytest.raises(DefinitionError):
            FeatureGroup(
                name="group",
                storage_target=StorageTarget.OFFLINE,
                entity_key=EntityKey(name="entity_id", dtype=FeatureType.INTEGER),
                event_timestamp=EventTimestamp(name="ts"),
                features=[Feature(name="ts", dtype=FeatureType.FLOAT)],
            )

    def test_rejects_duplicate_feature_names(self) -> None:
        """DefinitionError when two features share the same name."""
        with pytest.raises(DefinitionError):
            FeatureGroup(
                name="group",
                storage_target=StorageTarget.OFFLINE,
                entity_key=EntityKey(name="entity_id", dtype=FeatureType.INTEGER),
                event_timestamp=EventTimestamp(name="ts"),
                features=[
                    Feature(name="price", dtype=FeatureType.FLOAT),
                    Feature(name="price", dtype=FeatureType.INTEGER),
                ],
            )


class TestFeatureGroupReferenceUseCase:
    """FeatureGroup constructs the reference use-case groups successfully."""

    def test_listing_features(self) -> None:
        """listing_features from the reference use case constructs without error."""
        group = build_listing_features()
        assert group.name == "listing_features"

    def test_town_market_features(self) -> None:
        """town_market_features from the reference use case constructs without error."""
        group = build_town_market_features()
        assert group.name == "town_market_features"

    def test_listing_features_validation_modes(self) -> None:
        """listing_features carries the expected validation modes."""
        group = build_listing_features()
        assert group.ingestion_validation == ValidationMode.ERROR
        assert group.offline_retrieval_validation == ValidationMode.NONE

    def test_listing_features_metadata(self) -> None:
        """listing_features carries the expected metadata."""
        group = build_listing_features()
        assert group.metadata is not None
        assert group.metadata.owner == "data-science-team"
