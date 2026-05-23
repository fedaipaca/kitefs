---
name: "Test Guidelines"
description: "Style rules for unit and integration tests under tests/"
applyTo: "tests/**"
---

**Important!**: Does not apply this instructions to `tests/bdd/`.

## Structure

- Use idiomatic `pytest`.
- Group related tests for one subject in `class Test<Subject>` with a one-line class docstring.
- Use concise `test_<behavior>` function names with a one-line docstring describing expected behavior.
- Prefer docstrings over comments for intent.
- Keep unit tests focused on one behavior; keep integration tests focused on one user flow or cross-module collaboration.
- Use Arrange / Act / Assert spacing.

## Naming

Good:

- `test_rejects_missing_entity_key`
- `test_accepts_utc_datetime`
- `test_returns_latest_value`
- `test_writes_partitioned_parquet`

Avoid vague names (`test_validation`, `test_error`, `test_success`, `test_case_1`) and full-sentence names (`test_it_should_reject_a_record_when_the_...`).

## Assertions and Fixtures

- Prefer direct assertions. Introduce a helper only when a domain-specific assertion repeats and clarifies intent.
- Use fixtures for reusable setup; keep them simple and local unless shared widely.
- Reuse `tests/fixtures/` and `helpers/` before adding new utilities.

## Parametrization

- Use `pytest.mark.parametrize` for related cases.
- Always provide readable `ids` or `pytest.param(..., id="...")` values.

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
