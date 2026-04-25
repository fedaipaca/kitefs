"""Smoke test for the kitefs package."""

from kitefs import ApplyResult, FeatureGroup, FeatureStore, FeatureType


class TestPackage:
    """Core types are importable from the top-level package."""

    def test_core_types_importable(self) -> None:
        """FeatureGroup and FeatureType are importable from kitefs."""
        assert FeatureGroup is not None
        assert FeatureType is not None

    def test_feature_store_importable(self) -> None:
        """FeatureStore is importable from kitefs."""
        assert FeatureStore is not None

    def test_apply_result_importable(self) -> None:
        """ApplyResult is importable from kitefs."""
        assert ApplyResult is not None
