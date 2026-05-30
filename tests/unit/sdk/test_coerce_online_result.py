"""Unit tests for _coerce_online_result — dtype-aware SDK result coercion."""

from __future__ import annotations

import datetime
from datetime import UTC
from typing import Any

from kitefs.constants import DATETIME_FMT
from kitefs.sdk.feature_store import _coerce_online_result


def _description() -> Any:
    """Return a FeatureGroupDescription for town_market_features (INTEGER entity key, FLOAT feature)."""
    from datetime import datetime

    from kitefs.registry.parser import describe_feature_group
    from kitefs.registry.serializer import build_registry_document
    from tests.fixtures.definitions import build_town_market_features

    groups = [build_town_market_features()]
    doc = build_registry_document(groups, prior_document={"feature_groups": {}}, now=datetime.now(UTC))
    return describe_feature_group(doc, "town_market_features")


class TestCoerceOnlineResultFloat:
    """FLOAT features are coerced to float regardless of the wire value type."""

    def test_integral_int_value_coerced_to_float(self) -> None:
        """A whole-valued FLOAT feature arriving as int (DynamoDB N round-trip) becomes float."""
        desc = _description()

        result = _coerce_online_result(
            {
                "town_id": 5,
                "event_timestamp": datetime.datetime(2025, 7, 1, tzinfo=UTC).strftime(DATETIME_FMT),
                "avg_price_per_sqm": 15200,  # int, as _deserialize_attr returns for integral N
            },
            desc,
        )

        price = result["avg_price_per_sqm"]
        assert isinstance(price, float), f"expected float, got {type(price).__name__}: {price!r}"
        assert price == 15200.0

    def test_fractional_float_value_stays_float(self) -> None:
        """A fractional FLOAT feature stays float."""
        desc = _description()

        result = _coerce_online_result(
            {
                "town_id": 5,
                "event_timestamp": datetime.datetime(2025, 7, 1, tzinfo=UTC).strftime(DATETIME_FMT),
                "avg_price_per_sqm": 152.75,
            },
            desc,
        )

        assert isinstance(result["avg_price_per_sqm"], float)
        assert result["avg_price_per_sqm"] == 152.75


class TestCoerceOnlineResultInteger:
    """INTEGER entity keys are coerced to int."""

    def test_entity_key_coerced_to_int(self) -> None:
        """An INTEGER entity key is returned as int."""
        desc = _description()

        result = _coerce_online_result(
            {
                "town_id": 5,
                "event_timestamp": datetime.datetime(2025, 7, 1, tzinfo=UTC).strftime(DATETIME_FMT),
                "avg_price_per_sqm": 10000.0,
            },
            desc,
        )

        assert isinstance(result["town_id"], int)
        assert result["town_id"] == 5


class TestCoerceOnlineResultNullPassthrough:
    """None values pass through unchanged for any dtype."""

    def test_null_float_feature_stays_none(self) -> None:
        """A null FLOAT feature value is not coerced — it stays None."""
        desc = _description()

        result = _coerce_online_result(
            {
                "town_id": 1,
                "event_timestamp": datetime.datetime(2025, 7, 1, tzinfo=UTC).strftime(DATETIME_FMT),
                "avg_price_per_sqm": None,
            },
            desc,
        )

        assert result["avg_price_per_sqm"] is None
