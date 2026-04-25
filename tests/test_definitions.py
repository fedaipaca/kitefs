"""Tests for the KiteFS definition module (src/kitefs/definitions.py)."""

import dataclasses

import pytest
from helpers import make_feature_group

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
        """All public definition symbols are importable."""
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
        """STRING member has value 'STRING'."""
        assert FeatureType.STRING.value == "STRING"

    def test_integer(self) -> None:
        """INTEGER member has value 'INTEGER'."""
        assert FeatureType.INTEGER.value == "INTEGER"

    def test_float(self) -> None:
        """FLOAT member has value 'FLOAT'."""
        assert FeatureType.FLOAT.value == "FLOAT"

    def test_datetime(self) -> None:
        """DATETIME member has value 'DATETIME'."""
        assert FeatureType.DATETIME.value == "DATETIME"

    def test_exactly_four_members(self) -> None:
        """FeatureType has exactly four members."""
        assert len(FeatureType) == 4


class TestStorageTarget:
    """StorageTarget enum has both required values."""

    def test_offline(self) -> None:
        """OFFLINE member has value 'OFFLINE'."""
        assert StorageTarget.OFFLINE.value == "OFFLINE"

    def test_offline_and_online(self) -> None:
        """OFFLINE_AND_ONLINE member has value 'OFFLINE_AND_ONLINE'."""
        assert StorageTarget.OFFLINE_AND_ONLINE.value == "OFFLINE_AND_ONLINE"

    def test_exactly_two_members(self) -> None:
        """StorageTarget has exactly two members."""
        assert len(StorageTarget) == 2


class TestValidationMode:
    """ValidationMode enum has all three required values."""

    def test_error(self) -> None:
        """ERROR member has value 'ERROR'."""
        assert ValidationMode.ERROR.value == "ERROR"

    def test_filter(self) -> None:
        """FILTER member has value 'FILTER'."""
        assert ValidationMode.FILTER.value == "FILTER"

    def test_none(self) -> None:
        """NONE member has value 'NONE'."""
        assert ValidationMode.NONE.value == "NONE"

    def test_exactly_three_members(self) -> None:
        """ValidationMode has exactly three members."""
        assert len(ValidationMode) == 3


# ---------------------------------------------------------------------------
# Expect fluent builder
# ---------------------------------------------------------------------------


class TestExpect:
    """Expect fluent builder produces correct constraints and is immutable."""

    def test_empty_expect(self) -> None:
        """An Expect with no constraints has an empty tuple."""
        e = Expect()
        assert dataclasses.asdict(e)["_constraints"] == ()

    def test_not_null(self) -> None:
        """not_null() adds a not_null constraint."""
        e = Expect().not_null()
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "not_null"},)

    def test_gt(self) -> None:
        """gt() adds a gt constraint with the given value."""
        e = Expect().gt(0)
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "gt", "value": 0},)

    def test_gte(self) -> None:
        """gte() adds a gte constraint with the given value."""
        e = Expect().gte(1900)
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "gte", "value": 1900},)

    def test_lt(self) -> None:
        """lt() adds a lt constraint with the given value."""
        e = Expect().lt(100)
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "lt", "value": 100},)

    def test_lte(self) -> None:
        """lte() adds a lte constraint with the given value."""
        e = Expect().lte(2030)
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "lte", "value": 2030},)

    def test_one_of(self) -> None:
        """one_of() adds a one_of constraint with values as a tuple."""
        e = Expect().one_of(["a", "b", "c"])
        # values is stored as a tuple (defensive copy — see Expect.one_of implementation)
        assert dataclasses.asdict(e)["_constraints"] == ({"type": "one_of", "values": ("a", "b", "c")},)

    def test_chaining_returns_new_instance(self) -> None:
        """Each chained call returns a new Expect instance, not a mutation."""
        e1 = Expect()
        e2 = e1.not_null()
        e3 = e2.gt(0)
        assert e1 is not e2
        assert e2 is not e3
        assert dataclasses.asdict(e1)["_constraints"] == ()
        assert len(dataclasses.asdict(e2)["_constraints"]) == 1
        assert len(dataclasses.asdict(e3)["_constraints"]) == 2

    def test_chaining_not_null_gt(self) -> None:
        """Chaining not_null().gt() produces both constraints in order."""
        e = Expect().not_null().gt(0)
        assert dataclasses.asdict(e)["_constraints"] == (
            {"type": "not_null"},
            {"type": "gt", "value": 0},
        )

    def test_chaining_gte_lte(self) -> None:
        """Chaining gte().lte() produces both constraints in order."""
        e = Expect().gte(1900).lte(2030)
        assert dataclasses.asdict(e)["_constraints"] == (
            {"type": "gte", "value": 1900},
            {"type": "lte", "value": 2030},
        )

    def test_frozen(self) -> None:
        """Expect is frozen and cannot be mutated."""
        e = Expect().not_null()
        with pytest.raises(dataclasses.FrozenInstanceError):
            e._constraints = ()  # type: ignore[misc]

    def test_asdict_serializable(self) -> None:
        """Expect serializes to a dict via dataclasses.asdict."""
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
        """one_of stores values as a tuple, not a list."""
        e = Expect().one_of(["a", "b"])
        constraint = dataclasses.asdict(e)["_constraints"][0]
        assert isinstance(constraint["values"], tuple)

    def test_one_of_empty_list(self) -> None:
        """one_of with an empty list stores an empty tuple."""
        e = Expect().one_of([])
        constraint = dataclasses.asdict(e)["_constraints"][0]
        assert constraint["values"] == ()


# ---------------------------------------------------------------------------
# EntityKey
# ---------------------------------------------------------------------------


class TestEntityKey:
    """EntityKey frozen dataclass."""

    def test_creation(self) -> None:
        """EntityKey stores name and dtype with description defaulting to None."""
        ek = EntityKey(name="listing_id", dtype=FeatureType.INTEGER)
        assert ek.name == "listing_id"
        assert ek.dtype == FeatureType.INTEGER
        assert ek.description is None

    def test_with_description(self) -> None:
        """EntityKey accepts an optional description."""
        ek = EntityKey(name="id", dtype=FeatureType.STRING, description="Primary key")
        assert ek.description == "Primary key"

    def test_frozen(self) -> None:
        """EntityKey is frozen and cannot be mutated."""
        ek = EntityKey(name="id", dtype=FeatureType.INTEGER)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ek.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EventTimestamp
# ---------------------------------------------------------------------------


class TestEventTimestamp:
    """EventTimestamp frozen dataclass."""

    def test_creation(self) -> None:
        """EventTimestamp stores name and dtype with description defaulting to None."""
        et = EventTimestamp(name="event_timestamp", dtype=FeatureType.DATETIME)
        assert et.name == "event_timestamp"
        assert et.dtype == FeatureType.DATETIME
        assert et.description is None

    def test_with_description(self) -> None:
        """EventTimestamp accepts an optional description."""
        et = EventTimestamp(name="ts", dtype=FeatureType.DATETIME, description="When sold")
        assert et.description == "When sold"

    def test_frozen(self) -> None:
        """EventTimestamp is frozen and cannot be mutated."""
        et = EventTimestamp(name="ts", dtype=FeatureType.DATETIME)
        with pytest.raises(dataclasses.FrozenInstanceError):
            et.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Feature
# ---------------------------------------------------------------------------


class TestFeature:
    """Feature frozen dataclass."""

    def test_creation_minimal(self) -> None:
        """Feature stores name, dtype, with description and expect defaulting to None."""
        f = Feature(name="price", dtype=FeatureType.FLOAT)
        assert f.name == "price"
        assert f.dtype == FeatureType.FLOAT
        assert f.description is None
        assert f.expect is None

    def test_with_expect(self) -> None:
        """Feature accepts an optional Expect constraint."""
        f = Feature(name="price", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0))
        assert f.expect is not None
        assert len(dataclasses.asdict(f.expect)["_constraints"]) == 2

    def test_frozen(self) -> None:
        """Feature is frozen and cannot be mutated."""
        f = Feature(name="price", dtype=FeatureType.FLOAT)
        with pytest.raises(dataclasses.FrozenInstanceError):
            f.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# JoinKey
# ---------------------------------------------------------------------------


class TestJoinKey:
    """JoinKey frozen dataclass."""

    def test_creation(self) -> None:
        """JoinKey stores field_name and referenced_group."""
        jk = JoinKey(field_name="town_id", referenced_group="town_market_features")
        assert jk.field_name == "town_id"
        assert jk.referenced_group == "town_market_features"

    def test_frozen(self) -> None:
        """JoinKey is frozen and cannot be mutated."""
        jk = JoinKey(field_name="town_id", referenced_group="town_market_features")
        with pytest.raises(dataclasses.FrozenInstanceError):
            jk.field_name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    """Metadata frozen dataclass with all-optional fields."""

    def test_defaults(self) -> None:
        """Metadata defaults all fields to None."""
        m = Metadata()
        assert m.description is None
        assert m.owner is None
        assert m.tags is None

    def test_with_all_fields(self) -> None:
        """Metadata accepts description, owner, and tags."""
        m = Metadata(
            description="Test group",
            owner="team-a",
            tags={"domain": "real-estate"},
        )
        assert m.description == "Test group"
        assert m.owner == "team-a"
        assert m.tags == {"domain": "real-estate"}

    def test_frozen(self) -> None:
        """Metadata is frozen and cannot be mutated."""
        m = Metadata()
        with pytest.raises(dataclasses.FrozenInstanceError):
            m.description = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FeatureGroup
# ---------------------------------------------------------------------------


class TestFeatureGroup:
    """FeatureGroup frozen dataclass with __post_init__ normalisation."""

    def test_creation_minimal(self) -> None:
        """FeatureGroup stores name and storage_target."""
        fg = make_feature_group()
        assert fg.name == "test_group"
        assert fg.storage_target == StorageTarget.OFFLINE

    def test_defaults(self) -> None:
        """FeatureGroup defaults join_keys, validation modes, and metadata."""
        fg = make_feature_group()
        assert fg.join_keys == ()
        assert fg.ingestion_validation == ValidationMode.ERROR
        assert fg.offline_retrieval_validation == ValidationMode.NONE
        assert fg.metadata == Metadata()

    def test_features_normalised_to_sorted_tuple(self) -> None:
        """Features are sorted by name and stored as a tuple."""
        features = [
            Feature(name="z_col", dtype=FeatureType.STRING),
            Feature(name="a_col", dtype=FeatureType.INTEGER),
            Feature(name="m_col", dtype=FeatureType.FLOAT),
        ]
        fg = make_feature_group(features=features)
        assert isinstance(fg.features, tuple)
        assert [f.name for f in fg.features] == ["a_col", "m_col", "z_col"]

    def test_join_keys_normalised_to_tuple(self) -> None:
        """Join keys are stored as a tuple."""
        jk = [JoinKey(field_name="town_id", referenced_group="towns")]
        fg = make_feature_group(join_keys=jk)
        assert isinstance(fg.join_keys, tuple)
        assert len(fg.join_keys) == 1

    def test_frozen(self) -> None:
        """FeatureGroup is frozen and cannot be mutated."""
        fg = make_feature_group()
        with pytest.raises(dataclasses.FrozenInstanceError):
            fg.name = "other"  # type: ignore[misc]

    def test_required_fields_enforced_by_type_system(self) -> None:
        """Missing required fields raise TypeError."""
        with pytest.raises(TypeError):
            FeatureGroup(name="test")  # type: ignore[call-arg]

    def test_asdict_roundtrip(self) -> None:
        """dataclasses.asdict produces a correct nested dict."""
        fg = make_feature_group(
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
        """Two FeatureGroups with features in different order are equal."""
        features_a = [
            Feature(name="b", dtype=FeatureType.STRING),
            Feature(name="a", dtype=FeatureType.INTEGER),
        ]
        features_b = [
            Feature(name="a", dtype=FeatureType.INTEGER),
            Feature(name="b", dtype=FeatureType.STRING),
        ]
        fg_a = make_feature_group(features=features_a)
        fg_b = make_feature_group(features=features_b)
        assert fg_a == fg_b

    def test_empty_features_list(self) -> None:
        """Empty features list results in an empty tuple."""
        # The definitions module does not enforce a minimum feature count —
        # that is the registry manager's job at apply() time.
        # Verify construction succeeds and results in an empty tuple.
        fg = make_feature_group(features=[])
        assert fg.features == ()

    def test_single_feature(self) -> None:
        """A single feature is stored correctly."""
        fg = make_feature_group(features=[Feature(name="price", dtype=FeatureType.FLOAT)])
        assert len(fg.features) == 1
        assert fg.features[0].name == "price"

    def test_duplicate_feature_names(self) -> None:
        """Duplicate feature names are accepted at the dataclass level."""
        # The definitions module does not reject duplicates — the registry
        # manager catches them at apply() time.
        # Sorted tuple will contain both; this documents that behaviour.
        features = [
            Feature(name="price", dtype=FeatureType.FLOAT),
            Feature(name="price", dtype=FeatureType.INTEGER),
        ]
        fg = make_feature_group(features=features)
        assert len(fg.features) == 2
        assert all(f.name == "price" for f in fg.features)


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
