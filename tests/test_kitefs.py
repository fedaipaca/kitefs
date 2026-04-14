"""Smoke test for the kitefs package."""

from kitefs import FeatureGroup, FeatureType


class TestPackage:
    def test_core_types_importable(self) -> None:
        assert FeatureGroup is not None
        assert FeatureType is not None
