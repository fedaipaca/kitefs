"""Tests for the KiteFS definition module (src/kitefs/definitions.py)."""

import dataclasses
from typing import Any

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
# Importability
# ---------------------------------------------------------------------------


class TestImportability:
    """All public definition symbols are importable from the top-level kitefs package."""

    def test_all_symbols_importable(self) -> None:
        symbols = [
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
        ]
        for sym in symbols:
            assert sym is not None, f"{sym} was not importable"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestFeatureType:
    """FeatureType enum has all four required values."""

    def test_string(self) -> None:
        assert FeatureType.STRING.value == "STRING"

    def test_integer(self) -> None:
        assert FeatureType.INTEGER.value == "INTEGER"

    def test_float(self) -> None:
        assert FeatureType.FLOAT.value == "FLOAT"

    def test_datetime(self) -> None:
        assert FeatureType.DATETIME.value == "DATETIME"

    def test_exactly_four_members(self) -> None:
        assert len(FeatureType) == 4


class TestStorageTarget:
    """StorageTarget enum has both required values."""

    def test_offline(self) -> None:
        assert StorageTarget.OFFLINE.value == "OFFLINE"

    def test_offline_and_online(self) -> None:
        assert StorageTarget.OFFLINE_AND_ONLINE.value == "OFFLINE_AND_ONLINE"

    def test_exactly_two_members(self) -> None:
        assert len(StorageTarget) == 2


class TestValidationMode:
    """ValidationMode enum has all three required values."""

    def test_error(self) -> None:
        assert ValidationMode.ERROR.value == "ERROR"

    def test_filter(self) -> None:
        assert ValidationMode.FILTER.value == "FILTER"

    def test_none(self) -> None:
        assert ValidationMode.NONE.value == "NONE"

    def test_exactly_three_members(self) -> None:
        assert len(ValidationMode) == 3


# ---------------------------------------------------------------------------
# Expect fluent builder
# ---------------------------------------------------------------------------


class TestExpect:
    """Expect fluent builder produces correct constraints and is immutable."""

    def test_empty_expect(self) -> None:
        e = Expect()
        assert dataclasses.asdict(e)["_constraints"] == ()

    def test_not_null(self) -> None:
        e = Expect().not_null()
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "not_null"},)

    def test_gt(self) -> None:
        e = Expect().gt(0)
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "gt", "value": 0},)

    def test_gte(self) -> None:
        e = Expect().gte(1900)
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "gte", "value": 1900},)

    def test_lt(self) -> None:
        e = Expect().lt(100)
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "lt", "value": 100},)

    def test_lte(self) -> None:
        e = Expect().lte(2030)
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "lte", "value": 2030},)

    def test_one_of(self) -> None:
        e = Expect().one_of(["a", "b", "c"])
        # values is stored as a tuple (defensive copy — see Expect.one_of implementation)
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "one_of", "values": ("a", "b", "c")},)

    def test_chaining_returns_new_instance(self) -> None:
        e1 = Expect()
        e2 = e1.not_null()
        e3 = e2.gt(0)
        assert e1 is not e2
        assert e2 is not e3
        assert dataclasses.asdict(e1)["_constraints"] == ()
        assert len(dataclasses.asdict(e2)["_constraints"]) == 1
        assert len(dataclasses.asdict(e3)["_constraints"]) == 2

    def test_chaining_not_null_gt(self) -> None:
        e = Expect().not_null().gt(0)
        assert dataclasses.asdict(e)["_constraints"] == (
            {"type": "not_null"},
            {"type": "gt", "value": 0},
        )

    def test_chaining_gte_lte(self) -> None:
        e = Expect().gte(1900).lte(2030)
        assert dataclasses.asdict(e)["_constraints"] == (
            {"type": "gte", "value": 1900},
            {"type": "lte", "value": 2030},
        )

    def test_frozen(self) -> None:
        e = Expect().not_null()
        with pytest.raises(dataclasses.FrozenInstanceError):
            e._constraints = ()  # type: ignore[misc]

    def test_asdict_serializable(self) -> None:
        e = Expect().not_null().gt(5)
        d = dataclasses.asdict(e)
        assert d == {"_constraints": ({"type": "not_null"}, {"type": "gt", "value": 5})}

    def test_one_of_defensive_copy(self) -> None:
        original = ["apartment", "house"]
        e = Expect().one_of(original)
        original.append("land")  # mutate the original list after construction
        constraint = dataclasses.asdict(e)["_constraints"][0]
        assert "land" not in constraint["values"], "Mutating original list must not affect stored constraint"

    def test_one_of_stores_tuple_not_list(self) -> None:
        e = Expect().one_of(["a", "b"])
        constraint = dataclasses.asdict(e)["_constraints"][0]
        assert isinstance(constraint["values"], tuple)

    def test_one_of_empty_list(self) -> None:
        e = Expect().one_of([])
        constraint = dataclasses.asdict(e)["_constraints"][0]
        assert constraint["values"] == ()


# ---------------------------------------------------------------------------
# EntityKey
# ---------------------------------------------------------------------------


class TestEntityKey:
    """EntityKey frozen dataclass."""

    def test_creation(self) -> None:
        ek = EntityKey(name="listing_id", dtype=FeatureType.INTEGER)
        assert ek.name == "listing_id"
        assert ek.dtype == FeatureType.INTEGER
        assert ek.description is None

    def test_with_description(self) -> None:
        ek = EntityKey(name="id", dtype=FeatureType.STRING, description="Primary key")
        assert ek.description == "Primary key"

    def test_frozen(self) -> None:
        ek = EntityKey(name="id", dtype=FeatureType.INTEGER)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ek.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EventTimestamp
# ---------------------------------------------------------------------------


class TestEventTimestamp:
    """EventTimestamp frozen dataclass."""

    def test_creation(self) -> None:
        et = EventTimestamp(name="event_timestamp", dtype=FeatureType.DATETIME)
        assert et.name == "event_timestamp"
        assert et.dtype == FeatureType.DATETIME
        assert et.description is None

    def test_with_description(self) -> None:
        et = EventTimestamp(name="ts", dtype=FeatureType.DATETIME, description="When sold")
        assert et.description == "When sold"

    def test_frozen(self) -> None:
        et = EventTimestamp(name="ts", dtype=FeatureType.DATETIME)
        with pytest.raises(dataclasses.FrozenInstanceError):
            et.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Feature
# ---------------------------------------------------------------------------


class TestFeature:
    """Feature frozen dataclass."""

    def test_creation_minimal(self) -> None:
        f = Feature(name="price", dtype=FeatureType.FLOAT)
        assert f.name == "price"
        assert f.dtype == FeatureType.FLOAT
        assert f.description is None
        assert f.expect is None

    def test_with_expect(self) -> None:
        f = Feature(name="price", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0))
        assert f.expect is not None
        assert len(dataclasses.asdict(f.expect)["_constraints"]) == 2

    def test_frozen(self) -> None:
        f = Feature(name="price", dtype=FeatureType.FLOAT)
        with pytest.raises(dataclasses.FrozenInstanceError):
            f.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# JoinKey
# ---------------------------------------------------------------------------


class TestJoinKey:
    """JoinKey frozen dataclass."""

    def test_creation(self) -> None:
        jk = JoinKey(field_name="town_id", referenced_group="town_market_features")
        assert jk.field_name == "town_id"
        assert jk.referenced_group == "town_market_features"

    def test_frozen(self) -> None:
        jk = JoinKey(field_name="town_id", referenced_group="town_market_features")
        with pytest.raises(dataclasses.FrozenInstanceError):
            jk.field_name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    """Metadata frozen dataclass with all-optional fields."""

    def test_defaults(self) -> None:
        m = Metadata()
        assert m.description is None
        assert m.owner is None
        assert m.tags is None

    def test_with_all_fields(self) -> None:
        m = Metadata(
            description="Test group",
            owner="team-a",
            tags={"domain": "real-estate"},
        )
        assert m.description == "Test group"
        assert m.owner == "team-a"
        assert m.tags == {"domain": "real-estate"}

    def test_frozen(self) -> None:
        m = Metadata()
        with pytest.raises(dataclasses.FrozenInstanceError):
            m.description = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FeatureGroup
# ---------------------------------------------------------------------------


def _make_feature_group(**overrides: Any) -> FeatureGroup:
    """Helper to build a minimal FeatureGroup with sensible defaults."""
    defaults = {
        "name": "test_group",
        "storage_target": StorageTarget.OFFLINE,
        "entity_key": EntityKey(name="id", dtype=FeatureType.INTEGER),
        "event_timestamp": EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
        "features": [Feature(name="value", dtype=FeatureType.FLOAT)],
    }
    defaults.update(overrides)
    return FeatureGroup(**defaults)


class TestFeatureGroup:
    """FeatureGroup frozen dataclass with __post_init__ normalisation."""

    def test_creation_minimal(self) -> None:
        fg = _make_feature_group()
        assert fg.name == "test_group"
        assert fg.storage_target == StorageTarget.OFFLINE

    def test_defaults(self) -> None:
        fg = _make_feature_group()
        assert fg.join_keys == ()
        assert fg.ingestion_validation == ValidationMode.ERROR
        assert fg.offline_retrieval_validation == ValidationMode.NONE
        assert fg.metadata == Metadata()

    def test_features_normalised_to_sorted_tuple(self) -> None:
        features = [
            Feature(name="z_col", dtype=FeatureType.STRING),
            Feature(name="a_col", dtype=FeatureType.INTEGER),
            Feature(name="m_col", dtype=FeatureType.FLOAT),
        ]
        fg = _make_feature_group(features=features)
        assert isinstance(fg.features, tuple)
        assert [f.name for f in fg.features] == ["a_col", "m_col", "z_col"]

    def test_join_keys_normalised_to_tuple(self) -> None:
        jk = [JoinKey(field_name="town_id", referenced_group="towns")]
        fg = _make_feature_group(join_keys=jk)
        assert isinstance(fg.join_keys, tuple)
        assert len(fg.join_keys) == 1

    def test_frozen(self) -> None:
        fg = _make_feature_group()
        with pytest.raises(dataclasses.FrozenInstanceError):
            fg.name = "other"  # type: ignore[misc]

    def test_required_fields_enforced_by_type_system(self) -> None:
        with pytest.raises(TypeError):
            FeatureGroup(name="test")  # type: ignore[call-arg]

    def test_asdict_roundtrip(self) -> None:
        fg = _make_feature_group(
            metadata=Metadata(description="Test", owner="me", tags={"k": "v"}),
            features=[
                Feature(name="price", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0)),
            ],
        )
        d = dataclasses.asdict(fg)
        assert d["name"] == "test_group"
        assert d["storage_target"] == StorageTarget.OFFLINE
        assert d["entity_key"]["name"] == "id"
        assert d["event_timestamp"]["name"] == "ts"
        assert len(d["features"]) == 1
        assert d["features"][0]["expect"]["_constraints"] == (
            {"type": "not_null"},
            {"type": "gt", "value": 0},
        )
        assert d["metadata"]["owner"] == "me"
        assert d["metadata"]["tags"] == {"k": "v"}

    def test_equality_independent_of_feature_order(self) -> None:
        features_a = [
            Feature(name="b", dtype=FeatureType.STRING),
            Feature(name="a", dtype=FeatureType.INTEGER),
        ]
        features_b = [
            Feature(name="a", dtype=FeatureType.INTEGER),
            Feature(name="b", dtype=FeatureType.STRING),
        ]
        fg_a = _make_feature_group(features=features_a)
        fg_b = _make_feature_group(features=features_b)
        assert fg_a == fg_b

    def test_empty_features_list(self) -> None:
        # BB-03 does not enforce a minimum feature count — that is BB-04's job at apply().
        # Verify construction succeeds and results in an empty tuple.
        fg = _make_feature_group(features=[])
        assert fg.features == ()

    def test_single_feature(self) -> None:
        fg = _make_feature_group(features=[Feature(name="price", dtype=FeatureType.FLOAT)])
        assert len(fg.features) == 1
        assert fg.features[0].name == "price"

    def test_duplicate_feature_names(self) -> None:
        # BB-03 does not reject duplicates — BB-04 catches them at apply().
        # Sorted tuple will contain both; this documents that behaviour.
        features = [
            Feature(name="price", dtype=FeatureType.FLOAT),
            Feature(name="price", dtype=FeatureType.INTEGER),
        ]
        fg = _make_feature_group(features=features)
        assert len(fg.features) == 2
        assert all(f.name == "price" for f in fg.features)


# ---------------------------------------------------------------------------
# Reference use case: listing_features
# ---------------------------------------------------------------------------


class TestReferenceUseCaseListingFeatures:
    """listing_features from docs-00-01-reference-use-case.md is instantiable."""

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
        assert listing_features.name == "listing_features"

    def test_storage_target(self, listing_features: FeatureGroup) -> None:
        assert listing_features.storage_target == StorageTarget.OFFLINE

    def test_entity_key(self, listing_features: FeatureGroup) -> None:
        assert listing_features.entity_key.name == "listing_id"
        assert listing_features.entity_key.dtype == FeatureType.INTEGER

    def test_event_timestamp(self, listing_features: FeatureGroup) -> None:
        assert listing_features.event_timestamp.name == "event_timestamp"
        assert listing_features.event_timestamp.dtype == FeatureType.DATETIME

    def test_features_sorted(self, listing_features: FeatureGroup) -> None:
        names = [f.name for f in listing_features.features]
        assert names == sorted(names)

    def test_feature_count(self, listing_features: FeatureGroup) -> None:
        assert len(listing_features.features) == 5

    def test_join_keys(self, listing_features: FeatureGroup) -> None:
        assert len(listing_features.join_keys) == 1
        assert listing_features.join_keys[0].field_name == "town_id"
        assert listing_features.join_keys[0].referenced_group == "town_market_features"

    def test_metadata(self, listing_features: FeatureGroup) -> None:
        assert listing_features.metadata.owner == "data-science-team"
        assert listing_features.metadata.tags == {"domain": "real-estate", "cadence": "monthly"}

    def test_build_year_expectations(self, listing_features: FeatureGroup) -> None:
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
    """town_market_features from docs-00-01-reference-use-case.md is instantiable."""

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
        assert town_market_features.name == "town_market_features"

    def test_storage_target(self, town_market_features: FeatureGroup) -> None:
        assert town_market_features.storage_target == StorageTarget.OFFLINE_AND_ONLINE

    def test_entity_key(self, town_market_features: FeatureGroup) -> None:
        assert town_market_features.entity_key.name == "town_id"
        assert town_market_features.entity_key.dtype == FeatureType.INTEGER

    def test_no_join_keys(self, town_market_features: FeatureGroup) -> None:
        assert town_market_features.join_keys == ()

    def test_single_feature(self, town_market_features: FeatureGroup) -> None:
        assert len(town_market_features.features) == 1
        assert town_market_features.features[0].name == "avg_price_per_sqm"

    def test_feature_expectation(self, town_market_features: FeatureGroup) -> None:
        feat = town_market_features.features[0]
        assert feat.expect is not None
        assert dataclasses.asdict(feat.expect)["_constraints"] == (
            {"type": "not_null"},
            {"type": "gt", "value": 0},
        )
