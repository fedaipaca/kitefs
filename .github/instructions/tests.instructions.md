---
name: "Test Guidelines"
description: "Instructions for unit and integration tests under the tests directory"
applyTo: "tests/**"
---

### Unit and Integration Test Style Guidelines

- Use idiomatic pytest for unit and integration tests.
- Use `class Test<Subject>` to group related tests when a file has multiple behaviors for the same subject.
- Add a short one-line class docstring that explains the group being tested.
- Use concise `test_<behavior>` function names. Keep names readable, but avoid full-sentence test names.
- Add a one-line test function docstring that explains the expected behavior in plain language.
- Prefer docstrings over comments for class and test intent.
- Do not apply this style guide to BDD tests which are in `tests/bdd` directory.

Example:

```python
class TestFeatureValueValidation:
    """Tests validation rules for feature values."""

    def test_rejects_missing_entity_key(self) -> None:
        """Rejects records that do not include the required entity key."""
        ...

    def test_accepts_valid_feature_value(self) -> None:
        """Accepts records with the required entity key, timestamp, and value."""
        ...
```

Good test names:

- `test_rejects_missing_entity_key`
- `test_accepts_utc_datetime`
- `test_returns_latest_value`
- `test_writes_partitioned_parquet`

Avoid vague names:

- `test_validation`
- `test_error`
- `test_success`
- `test_case_1`

Avoid overly long sentence-style names:

- `test_it_should_reject_a_record_when_the_entity_key_is_missing_from_the_input_dataframe`

For parametrized tests, keep the function name concise and use readable case IDs:

```python
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("house_id", True, id="valid_string_key"),
        pytest.param("", False, id="empty_key"),
    ],
)
def test_validates_entity_key_name(value: str, expected: bool) -> None:
    """Validates accepted and rejected entity key names."""
    ...
```

Use Arrange / Act / Assert spacing:

```python
def test_returns_latest_value(self) -> None:
    """Returns the latest feature value at or before the event timestamp."""
    feature_values = make_feature_values()
    event_timestamp = datetime(2026, 1, 15, tzinfo=UTC)

    result = lookup_latest_value(feature_values, event_timestamp)

    assert result.value == 42
```

- Prefer direct assertions unless a repeated domain-specific assertion helper makes the test clearer.
- Keep unit tests focused on one behavior.
- Keep integration tests focused on one user flow or cross-module collaboration.
- Use `pytest.mark.parametrize` for related cases, and always provide readable `ids` or `pytest.param(..., id="...")` values.
- Use fixtures for reusable setup, but keep fixtures simple and local unless they are shared across many tests.
