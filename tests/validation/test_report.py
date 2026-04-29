"""Tests for ValidationReport and FailureDetail types."""

import dataclasses

from kitefs.validation import FailureDetail, ValidationReport


class TestFailureDetail:
    """Tests for the FailureDetail frozen dataclass."""

    def test_frozen(self) -> None:
        """FailureDetail instances are immutable."""
        detail = FailureDetail(
            entity_key_value=1,
            field="net_area",
            expected="gt(0)",
            actual="-5",
        )
        try:
            detail.field = "other"  # type: ignore[misc]
            raised = False
        except dataclasses.FrozenInstanceError:
            raised = True
        assert raised

    def test_asdict_roundtrip(self) -> None:
        """FailureDetail can be serialized via dataclasses.asdict."""
        detail = FailureDetail(
            entity_key_value=42,
            field="sold_price",
            expected="not_null",
            actual="None",
        )
        d = dataclasses.asdict(detail)
        assert d == {
            "entity_key_value": 42,
            "field": "sold_price",
            "expected": "not_null",
            "actual": "None",
        }

    def test_none_entity_key(self) -> None:
        """FailureDetail accepts None as entity_key_value."""
        detail = FailureDetail(entity_key_value=None, field="x", expected="not_null", actual="NaN")
        assert detail.entity_key_value is None


class TestValidationReport:
    """Tests for the ValidationReport frozen dataclass."""

    def test_frozen(self) -> None:
        """ValidationReport instances are immutable."""
        report = ValidationReport(total_count=10, passed_count=8, failed_count=2, failures=())
        try:
            report.total_count = 99  # type: ignore[misc]
            raised = False
        except dataclasses.FrozenInstanceError:
            raised = True
        assert raised

    def test_asdict_roundtrip(self) -> None:
        """ValidationReport can be serialized via dataclasses.asdict."""
        detail = FailureDetail(entity_key_value=1, field="x", expected="gt(0)", actual="-1")
        report = ValidationReport(total_count=5, passed_count=4, failed_count=1, failures=(detail,))
        d = dataclasses.asdict(report)
        assert d["total_count"] == 5
        assert d["passed_count"] == 4
        assert d["failed_count"] == 1
        assert len(d["failures"]) == 1
        assert d["failures"][0]["field"] == "x"

    def test_empty_failures(self) -> None:
        """A clean report has empty failures tuple."""
        report = ValidationReport(total_count=3, passed_count=3, failed_count=0, failures=())
        assert report.failures == ()
        assert report.failed_count == 0


class TestFormatFailures:
    """Tests for the _format_failures internal helper."""

    def test_format_failures_truncation(self) -> None:
        """More than 20 failures are truncated with a summary."""
        from kitefs.validation import _format_failures

        failures = [FailureDetail(entity_key_value=i, field="x", expected="gt(0)", actual=str(-i)) for i in range(25)]
        output = _format_failures(failures)
        lines = output.strip().split("\n")
        # 20 detail lines + 1 truncation line
        assert len(lines) == 21
        assert "... and 5 more failure(s)" in lines[-1]

    def test_format_failures_no_truncation_at_boundary(self) -> None:
        """Exactly 20 failures are shown without truncation."""
        from kitefs.validation import _format_failures

        failures = [FailureDetail(entity_key_value=i, field="x", expected="gt(0)", actual=str(-i)) for i in range(20)]
        output = _format_failures(failures)
        lines = output.strip().split("\n")
        assert len(lines) == 20
        assert "more failure" not in output
