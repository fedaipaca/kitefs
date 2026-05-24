from kitefs.errors import KiteFSError, ValidationError


def test_report_round_trip() -> None:
    sentinel = object()
    err = ValidationError("something failed", report=sentinel)
    assert err.report is sentinel


def test_message() -> None:
    err = ValidationError("something failed", report=object())
    assert str(err) == "something failed"


def test_is_kitefsError() -> None:
    err = ValidationError("x")
    assert isinstance(err, KiteFSError)


def test_report_defaults_to_none() -> None:
    err = ValidationError("x")
    assert err.report is None
