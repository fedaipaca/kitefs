import datetime

import pytest

from kitefs import DefinitionError, Expect


class TestExpectFluent:
    """Fluent chain returns self and accumulates constraints."""

    def test_not_null_returns_self(self) -> None:
        """not_null() returns the same Expect instance."""
        e = Expect()
        assert e.not_null() is e

    def test_gt_returns_self(self) -> None:
        """gt() returns the same Expect instance."""
        e = Expect()
        assert e.gt(0) is e

    def test_chained_chain_returns_self(self) -> None:
        """A fluent chain through multiple operators returns the original instance."""
        e = Expect()
        result = e.not_null().gt(0).gte(1).lt(100).lte(99)
        assert result is e

    def test_not_null_appends_constraint(self) -> None:
        """not_null() appends one constraint."""
        e = Expect()
        e.not_null()
        assert len(e._constraints) == 1
        assert e._constraints[0][0] == "not_null"

    def test_is_in_appends_constraint(self) -> None:
        """is_in() appends one constraint with the values list."""
        e = Expect()
        e.is_in([1, 2, 3])
        assert len(e._constraints) == 1
        assert e._constraints[0] == ("is_in", [1, 2, 3])

    def test_chained_appends_multiple_constraints(self) -> None:
        """Each chained operator adds an entry to _constraints."""
        e = Expect().not_null().gt(0).lte(100)
        assert len(e._constraints) == 3


class TestExpectNumericOperators:
    """Numeric operators accept int/float/datetime and reject everything else."""

    @pytest.mark.parametrize(
        "bad_value",
        [
            pytest.param("zero", id="string"),
            pytest.param(None, id="none"),
            pytest.param([1, 2], id="list"),
            pytest.param({"a": 1}, id="dict"),
        ],
    )
    @pytest.mark.parametrize("op", ["gt", "gte", "lt", "lte"])
    def test_rejects_non_numeric(self, op: str, bad_value: object) -> None:
        """Numeric operators raise DefinitionError for non-numeric values."""
        e = Expect()
        with pytest.raises(DefinitionError) as exc_info:
            getattr(e, op)(bad_value)
        msg = str(exc_info.value)
        assert op in msg
        assert "int, float, or datetime" in msg

    @pytest.mark.parametrize(
        "good_value",
        [
            pytest.param(0, id="int_zero"),
            pytest.param(-5, id="negative_int"),
            pytest.param(3.14, id="float"),
            pytest.param(datetime.datetime(2024, 1, 1), id="datetime"),
        ],
    )
    @pytest.mark.parametrize("op", ["gt", "gte", "lt", "lte"])
    def test_accepts_numeric(self, op: str, good_value: object) -> None:
        """Numeric operators accept int, float, and datetime without raising."""
        e = Expect()
        getattr(e, op)(good_value)  # must not raise


class TestExpectIsIn:
    """is_in validates the values list."""

    def test_rejects_empty_list(self) -> None:
        """is_in([]) raises DefinitionError."""
        with pytest.raises(DefinitionError):
            Expect().is_in([])

    def test_accepts_nonempty_list(self) -> None:
        """is_in with at least one element does not raise."""
        Expect().is_in(["a", "b"])  # must not raise

    def test_accepts_mixed_types(self) -> None:
        """is_in accepts a list with mixed allowed types."""
        Expect().is_in([1, "two", 3.0])  # must not raise
