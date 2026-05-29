"""Builders for the reference feature groups from specs/01-reference-use-case.md."""

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


def build_listing_features() -> FeatureGroup:
    return FeatureGroup(
        name="listing_features",
        storage_target=StorageTarget.OFFLINE,
        entity_key=EntityKey(
            name="listing_id",
            dtype=FeatureType.INTEGER,
            description="Unique identifier for each listing",
        ),
        event_timestamp=EventTimestamp(
            name="sold_at",
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
        ],
        join_keys=[
            JoinKey(
                name="town_id",
                dtype=FeatureType.INTEGER,
                referenced_group="town_market_features",
                description="Join key to town_market_features",
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


def build_town_market_features() -> FeatureGroup:
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
            description="When this value became available",
        ),
        features=[
            Feature(
                name="avg_price_per_sqm",
                dtype=FeatureType.FLOAT,
                description=(
                    "Average sold price per sqm from sold listings in this town during the previous calendar month"
                ),
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
