"""Tests for registry definition validation."""

from helpers import make_feature_group

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
from kitefs.registry import _validate_definitions


class TestValidateDefinitionsIndividual:
    """Per-group structural validation rules."""

    def test_valid_single_group_returns_empty(self) -> None:
        """A valid group produces no validation errors."""
        errors = _validate_definitions([make_feature_group()])
        assert errors == []

    def test_empty_group_list_returns_empty(self) -> None:
        """An empty definitions list produces no errors."""
        errors = _validate_definitions([])
        assert errors == []

    def test_event_timestamp_non_datetime_dtype_error(self) -> None:
        """EventTimestamp with non-DATETIME dtype produces an error."""
        group = make_feature_group(
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

        group = make_feature_group(features=[feature])

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "bad_feat" in errors[0]
        assert "invalid dtype" in errors[0]

    def test_duplicate_field_names_entity_key_and_feature(self) -> None:
        """Entity key sharing a name with a feature produces a duplicate error."""
        group = make_feature_group(
            entity_key=EntityKey(name="shared", dtype=FeatureType.INTEGER),
            features=[Feature(name="shared", dtype=FeatureType.FLOAT)],
        )

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "Duplicate field name 'shared'" in errors[0]

    def test_duplicate_field_names_event_timestamp_and_feature(self) -> None:
        """Event timestamp sharing a name with a feature produces a duplicate error."""
        group = make_feature_group(
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
            features=[Feature(name="ts", dtype=FeatureType.FLOAT)],
        )

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "Duplicate field name 'ts'" in errors[0]

    def test_duplicate_field_names_entity_key_and_event_timestamp(self) -> None:
        """Entity key and event timestamp sharing a name produces a duplicate error."""
        group = make_feature_group(
            entity_key=EntityKey(name="same", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="same", dtype=FeatureType.DATETIME),
        )

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "Duplicate field name 'same'" in errors[0]

    def test_multiple_individual_errors_in_one_group(self) -> None:
        """A group with both a bad timestamp dtype and duplicate names produces multiple errors."""
        group = make_feature_group(
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="id", dtype=FeatureType.STRING),
        )

        errors = _validate_definitions([group])

        assert len(errors) == 2
        assert any("EventTimestamp" in e for e in errors)
        assert any("Duplicate field name" in e for e in errors)

    def test_duplicate_feature_names_within_features(self) -> None:
        """Two features sharing the same name produce a duplicate field error."""
        group = make_feature_group(
            features=[
                Feature(name="dup_feat", dtype=FeatureType.FLOAT),
                Feature(name="dup_feat", dtype=FeatureType.INTEGER),
            ],
        )

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "Duplicate field name 'dup_feat'" in errors[0]


class TestValidateDefinitionsCrossGroup:
    """Cross-group validation rules (duplicates and join keys)."""

    def test_duplicate_group_names_error(self) -> None:
        """Two groups with the same name produce a duplicate name error."""
        g1 = make_feature_group(name="dup")
        g2 = make_feature_group(name="dup")

        errors = _validate_definitions([g1, g2])

        assert any("Duplicate feature group name 'dup'" in e for e in errors)
        assert any("2 times" in e for e in errors)

    def test_join_key_references_nonexistent_group_error(self) -> None:
        """A join key referencing a non-existent group produces an error."""
        group = make_feature_group(
            features=[Feature(name="fk", dtype=FeatureType.INTEGER)],
            join_keys=[JoinKey(field_name="fk", referenced_group="ghost")],
        )

        errors = _validate_definitions([group])

        assert len(errors) == 1
        assert "non-existent group 'ghost'" in errors[0]

    def test_join_key_field_name_mismatch_error(self) -> None:
        """Join key field_name differs from referenced group's entity key name."""
        referenced = make_feature_group(
            name="ref_group",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        base = make_feature_group(
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
        referenced = make_feature_group(
            name="ref_group",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        base = make_feature_group(
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
        """Type check passes when the join key field matches via entity_key."""
        referenced = make_feature_group(
            name="ref_group",
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
        )
        base = make_feature_group(
            name="base_group",
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            join_keys=[JoinKey(field_name="id", referenced_group="ref_group")],
        )

        errors = _validate_definitions([base, referenced])

        assert errors == []

    def test_join_key_valid_relationship_no_errors(self) -> None:
        """A correctly declared join key produces no errors."""
        town = make_feature_group(
            name="towns",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        listings = make_feature_group(
            name="listings",
            features=[Feature(name="town_id", dtype=FeatureType.INTEGER)],
            join_keys=[JoinKey(field_name="town_id", referenced_group="towns")],
        )

        errors = _validate_definitions([listings, town])

        assert errors == []

    def test_join_key_field_not_in_base_group_error(self) -> None:
        """Join key field doesn't exist in the base group despite name matching referenced entity key."""
        town = make_feature_group(
            name="town_market_features",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        listing = make_feature_group(
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
        region = make_feature_group(
            name="regions",
            entity_key=EntityKey(name="region_id", dtype=FeatureType.INTEGER),
        )
        town = make_feature_group(
            name="towns",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        listing = make_feature_group(
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
        group = make_feature_group(
            name="categories",
            entity_key=EntityKey(name="category_id", dtype=FeatureType.INTEGER),
            join_keys=[JoinKey(field_name="category_id", referenced_group="categories")],
        )

        errors = _validate_definitions([group])

        assert errors == []

    def test_join_key_field_name_and_type_both_wrong(self) -> None:
        """Both name mismatch and type mismatch errors are collected for the same join key."""
        referenced = make_feature_group(
            name="ref_group",
            entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
        )
        base = make_feature_group(
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
        g1 = make_feature_group(name="dup")
        g2 = make_feature_group(name="dup")
        g3 = make_feature_group(name="dup")

        errors = _validate_definitions([g1, g2, g3])

        assert any("3 times" in e for e in errors)


class TestValidateDefinitionsCollectedErrors:
    """Multiple errors from multiple groups are collected in one call."""

    def test_multiple_errors_from_multiple_groups(self) -> None:
        """Each group has a different error — all are returned together."""
        g1 = make_feature_group(
            name="bad_ts",
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.INTEGER),
        )
        g2 = make_feature_group(
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
        g1 = make_feature_group(
            name="same",
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.STRING),
        )
        g2 = make_feature_group(name="same")

        errors = _validate_definitions([g1, g2])

        has_ts_error = any("EventTimestamp" in e for e in errors)
        has_dup_error = any("Duplicate feature group name" in e for e in errors)
        assert has_ts_error
        assert has_dup_error
        assert len(errors) >= 2


class TestValidateDefinitionsReferenceUseCase:
    """Reference use case definitions pass validation."""

    def test_reference_use_case_passes_validation(self) -> None:
        """Both reference use case definitions pass cross-group validation."""
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
