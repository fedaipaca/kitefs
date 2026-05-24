from kitefs.errors import format_actionable


def test_full_kwargs_contains_all_values() -> None:
    msg = format_actionable(
        setting="store.backend",
        group="user_features",
        field="age",
        problem="value out of range",
        next_step="check ingestion config",
    )
    assert "store.backend" in msg
    assert "user_features" in msg
    assert "age" in msg
    assert "value out of range" in msg
    assert "check ingestion config" in msg
    assert "\n" not in msg
    assert msg != ""


def test_minimal_kwargs_no_none_literal() -> None:
    msg = format_actionable(problem="missing column", next_step="add column to source")
    assert "None" not in msg
    assert "missing column" in msg
    assert "add column to source" in msg
    assert "\n" not in msg


def test_returns_str() -> None:
    result = format_actionable(problem="p", next_step="n")
    assert isinstance(result, str)
