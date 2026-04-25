"""Tests for KiteFS definition enums and importability."""

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
