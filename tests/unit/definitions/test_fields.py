import pytest

from kitefs import DefinitionError, EntityKey, EventTimestamp, Feature, FeatureType, JoinKey, StorageTarget


class TestEntityKey:
    """EntityKey construction-time dtype and identifier validation."""

    @pytest.mark.parametrize(
        "dtype",
        [
            pytest.param(FeatureType.STRING, id="string"),
            pytest.param(FeatureType.INTEGER, id="integer"),
        ],
    )
    def test_accepts_valid_dtypes(self, dtype: FeatureType) -> None:
        """EntityKey accepts STRING and INTEGER dtypes."""
        key = EntityKey(name="listing_id", dtype=dtype)
        assert key.dtype == dtype

    @pytest.mark.parametrize(
        "dtype",
        [
            pytest.param(FeatureType.FLOAT, id="float"),
            pytest.param(FeatureType.DATETIME, id="datetime"),
        ],
    )
    def test_rejects_invalid_dtypes(self, dtype: FeatureType) -> None:
        """EntityKey raises DefinitionError for FLOAT and DATETIME dtypes."""
        with pytest.raises(DefinitionError) as exc_info:
            EntityKey(name="listing_id", dtype=dtype)
        msg = str(exc_info.value)
        assert "listing_id" in msg
        assert "STRING or INTEGER" in msg

    @pytest.mark.parametrize(
        "dtype",
        [
            pytest.param("INTEGER", id="string_value"),
            pytest.param(None, id="none"),
            pytest.param(StorageTarget.OFFLINE, id="wrong_enum"),
        ],
    )
    def test_rejects_non_featuretype_dtype(self, dtype: object) -> None:
        """EntityKey raises DefinitionError when dtype is not a FeatureType member."""
        with pytest.raises(DefinitionError) as exc_info:
            EntityKey(name="listing_id", dtype=dtype)  # type: ignore[arg-type]
        msg = str(exc_info.value)
        assert "listing_id" in msg
        assert "STRING or INTEGER" in msg

    def test_stores_attributes(self) -> None:
        """EntityKey stores name, dtype, and description."""
        key = EntityKey(name="listing_id", dtype=FeatureType.INTEGER, description="The ID")
        assert key.name == "listing_id"
        assert key.dtype == FeatureType.INTEGER
        assert key.description == "The ID"

    def test_description_defaults_to_none(self) -> None:
        """EntityKey description defaults to None."""
        key = EntityKey(name="listing_id", dtype=FeatureType.INTEGER)
        assert key.description is None


class TestEventTimestamp:
    """EventTimestamp construction-time dtype and identifier validation."""

    def test_defaults_to_datetime(self) -> None:
        """EventTimestamp dtype defaults to DATETIME when omitted."""
        ts = EventTimestamp(name="sold_at")
        assert ts.dtype == FeatureType.DATETIME

    def test_accepts_datetime_explicitly(self) -> None:
        """EventTimestamp accepts explicit DATETIME dtype."""
        ts = EventTimestamp(name="sold_at", dtype=FeatureType.DATETIME)
        assert ts.dtype == FeatureType.DATETIME

    @pytest.mark.parametrize(
        "dtype",
        [
            pytest.param(FeatureType.STRING, id="string"),
            pytest.param(FeatureType.INTEGER, id="integer"),
            pytest.param(FeatureType.FLOAT, id="float"),
        ],
    )
    def test_rejects_non_datetime(self, dtype: FeatureType) -> None:
        """EventTimestamp raises DefinitionError for non-DATETIME dtypes."""
        with pytest.raises(DefinitionError):
            EventTimestamp(name="sold_at", dtype=dtype)

    @pytest.mark.parametrize(
        "dtype",
        [
            pytest.param("DATETIME", id="string_value"),
            pytest.param(None, id="none"),
            pytest.param(StorageTarget.OFFLINE, id="wrong_enum"),
        ],
    )
    def test_rejects_non_featuretype_dtype(self, dtype: object) -> None:
        """EventTimestamp raises DefinitionError when dtype is not a FeatureType member."""
        with pytest.raises(DefinitionError):
            EventTimestamp(name="sold_at", dtype=dtype)  # type: ignore[arg-type]


class TestFeature:
    """Feature construction-time identifier validation."""

    @pytest.mark.parametrize(
        "dtype",
        [
            pytest.param(FeatureType.STRING, id="string"),
            pytest.param(FeatureType.INTEGER, id="integer"),
            pytest.param(FeatureType.FLOAT, id="float"),
            pytest.param(FeatureType.DATETIME, id="datetime"),
        ],
    )
    def test_accepts_all_dtypes(self, dtype: FeatureType) -> None:
        """Feature accepts all four FeatureType values."""
        f = Feature(name="price", dtype=dtype)
        assert f.dtype == dtype

    def test_expect_defaults_to_none(self) -> None:
        """Feature expect attribute defaults to None."""
        f = Feature(name="price", dtype=FeatureType.FLOAT)
        assert f.expect is None

    @pytest.mark.parametrize(
        "dtype",
        [
            pytest.param("FLOAT", id="string_value"),
            pytest.param(None, id="none"),
            pytest.param(StorageTarget.OFFLINE, id="wrong_enum"),
        ],
    )
    def test_rejects_non_featuretype_dtype(self, dtype: object) -> None:
        """Feature raises DefinitionError when dtype is not a FeatureType member."""
        with pytest.raises(DefinitionError):
            Feature(name="price", dtype=dtype)  # type: ignore[arg-type]


class TestJoinKey:
    """JoinKey construction-time dtype and referenced_group validation."""

    @pytest.mark.parametrize(
        "dtype",
        [
            pytest.param(FeatureType.STRING, id="string"),
            pytest.param(FeatureType.INTEGER, id="integer"),
        ],
    )
    def test_accepts_valid_dtypes(self, dtype: FeatureType) -> None:
        """JoinKey accepts STRING and INTEGER dtypes."""
        jk = JoinKey(name="town_id", dtype=dtype, referenced_group="town_market_features")
        assert jk.dtype == dtype

    @pytest.mark.parametrize(
        "dtype",
        [
            pytest.param(FeatureType.FLOAT, id="float"),
            pytest.param(FeatureType.DATETIME, id="datetime"),
        ],
    )
    def test_rejects_invalid_dtypes(self, dtype: FeatureType) -> None:
        """JoinKey raises DefinitionError for FLOAT and DATETIME dtypes."""
        with pytest.raises(DefinitionError):
            JoinKey(name="town_id", dtype=dtype, referenced_group="town_market_features")

    @pytest.mark.parametrize(
        "dtype",
        [
            pytest.param("INTEGER", id="string_value"),
            pytest.param(None, id="none"),
            pytest.param(StorageTarget.OFFLINE, id="wrong_enum"),
        ],
    )
    def test_rejects_non_featuretype_dtype(self, dtype: object) -> None:
        """JoinKey raises DefinitionError when dtype is not a FeatureType member."""
        with pytest.raises(DefinitionError):
            JoinKey(name="town_id", dtype=dtype, referenced_group="town_market_features")  # type: ignore[arg-type]

    def test_rejects_empty_referenced_group(self) -> None:
        """JoinKey raises DefinitionError when referenced_group is empty."""
        with pytest.raises(DefinitionError):
            JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="")

    def test_rejects_whitespace_referenced_group(self) -> None:
        """JoinKey raises DefinitionError when referenced_group is whitespace."""
        with pytest.raises(DefinitionError):
            JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="   ")


class TestIdentifierValidation:
    """All field classes enforce the CON-009 identifier regex on their name."""

    @pytest.mark.parametrize(
        "bad_name",
        [
            pytest.param("123-invalid", id="starts_with_digit_and_dash"),
            pytest.param("foo-bar", id="contains_dash"),
            pytest.param("with space", id="contains_space"),
            pytest.param("", id="empty_string"),
            pytest.param("1abc", id="starts_with_digit"),
        ],
    )
    def test_entity_key_rejects_invalid_names(self, bad_name: str) -> None:
        """EntityKey raises DefinitionError for names that are not valid identifiers."""
        with pytest.raises(DefinitionError):
            EntityKey(name=bad_name, dtype=FeatureType.INTEGER)

    @pytest.mark.parametrize(
        "good_name",
        [
            pytest.param("_x", id="underscore_prefix"),
            pytest.param("x1", id="letter_then_digit"),
            pytest.param("a_b_c", id="underscores"),
            pytest.param("CamelCase", id="camel"),
        ],
    )
    def test_entity_key_accepts_valid_names(self, good_name: str) -> None:
        """EntityKey accepts valid Python identifier names."""
        key = EntityKey(name=good_name, dtype=FeatureType.INTEGER)
        assert key.name == good_name
