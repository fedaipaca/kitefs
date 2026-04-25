"""Tests for reference use case definitions — listing_features and town_market_features."""

import dataclasses

import pytest

from kitefs import (
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

# ---------------------------------------------------------------------------
# Reference use case: listing_features
# ---------------------------------------------------------------------------


class TestReferenceUseCaseListingFeatures:
    """listing_features from the reference use case is instantiable."""

    @pytest.fixture()
    def listing_features(self) -> FeatureGroup:
        """Build the listing_features definition from the reference use case."""
        return FeatureGroup(
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
                Feature(
                    name="town_id",
                    dtype=FeatureType.INTEGER,
                    description="Join key to town_market_features",
                ),
            ],
            join_keys=[
                JoinKey(
                    field_name="town_id",
                    referenced_group="town_market_features",
                ),
            ],
            ingestion_validation=ValidationMode.ERROR,
            offline_retrieval_validation=ValidationMode.NONE,
            metadata=Metadata(
                description="Historical sold listing attributes and prices",
                owner="data-science-team",
                tags={"domain": "real-estate", "cadence": "monthly"},
            ),
        )

    def test_name(self, listing_features: FeatureGroup) -> None:
        """listing_features has the correct name."""
        assert listing_features.name == "listing_features"

    def test_storage_target(self, listing_features: FeatureGroup) -> None:
        """listing_features uses OFFLINE storage."""
        assert listing_features.storage_target == StorageTarget.OFFLINE

    def test_entity_key(self, listing_features: FeatureGroup) -> None:
        """listing_features has listing_id as entity key."""
        assert listing_features.entity_key.name == "listing_id"
        assert listing_features.entity_key.dtype == FeatureType.INTEGER

    def test_event_timestamp(self, listing_features: FeatureGroup) -> None:
        """listing_features has event_timestamp as the time field."""
        assert listing_features.event_timestamp.name == "event_timestamp"
        assert listing_features.event_timestamp.dtype == FeatureType.DATETIME

    def test_features_sorted(self, listing_features: FeatureGroup) -> None:
        """Features are sorted alphabetically by name."""
        names = [f.name for f in listing_features.features]
        assert names == sorted(names)

    def test_feature_count(self, listing_features: FeatureGroup) -> None:
        """listing_features has 5 features."""
        assert len(listing_features.features) == 5

    def test_join_keys(self, listing_features: FeatureGroup) -> None:
        """listing_features joins to town_market_features via town_id."""
        assert len(listing_features.join_keys) == 1
        assert listing_features.join_keys[0].field_name == "town_id"
        assert listing_features.join_keys[0].referenced_group == "town_market_features"

    def test_metadata(self, listing_features: FeatureGroup) -> None:
        """listing_features has data-science-team as owner."""
        assert listing_features.metadata.owner == "data-science-team"
        assert listing_features.metadata.tags == {"domain": "real-estate", "cadence": "monthly"}

    def test_build_year_expectations(self, listing_features: FeatureGroup) -> None:
        """build_year feature has not_null, gte(1900), and lte(2030) constraints."""
        build_year = next(f for f in listing_features.features if f.name == "build_year")
        assert build_year.expect is not None
        constraints = dataclasses.asdict(build_year.expect)["_constraints"]
        assert len(constraints) == 3
        types = [c["type"] for c in constraints]
        assert types == ["not_null", "gte", "lte"]


# ---------------------------------------------------------------------------
# Reference use case: town_market_features
# ---------------------------------------------------------------------------


class TestReferenceUseCaseTownMarketFeatures:
    """town_market_features from the reference use case is instantiable."""

    @pytest.fixture()
    def town_market_features(self) -> FeatureGroup:
        """Build the town_market_features definition from the reference use case."""
        return FeatureGroup(
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

    def test_name(self, town_market_features: FeatureGroup) -> None:
        """town_market_features has the correct name."""
        assert town_market_features.name == "town_market_features"

    def test_storage_target(self, town_market_features: FeatureGroup) -> None:
        """town_market_features uses OFFLINE_AND_ONLINE storage."""
        assert town_market_features.storage_target == StorageTarget.OFFLINE_AND_ONLINE

    def test_entity_key(self, town_market_features: FeatureGroup) -> None:
        """town_market_features has town_id as entity key."""
        assert town_market_features.entity_key.name == "town_id"
        assert town_market_features.entity_key.dtype == FeatureType.INTEGER

    def test_no_join_keys(self, town_market_features: FeatureGroup) -> None:
        """town_market_features has no join keys."""
        assert town_market_features.join_keys == ()

    def test_single_feature(self, town_market_features: FeatureGroup) -> None:
        """town_market_features has one feature: avg_price_per_sqm."""
        assert len(town_market_features.features) == 1
        assert town_market_features.features[0].name == "avg_price_per_sqm"

    def test_feature_expectation(self, town_market_features: FeatureGroup) -> None:
        """avg_price_per_sqm has not_null and gt(0) constraints."""
        feat = town_market_features.features[0]
        assert feat.expect is not None
        assert dataclasses.asdict(feat.expect)["_constraints"] == (
            {"type": "not_null"},
            {"type": "gt", "value": 0},
        )
