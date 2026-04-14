---
description: "Use when writing or modifying tests. Covers pytest conventions, fixture patterns, and test data sources for KiteFS."
applyTo: "tests/**/*.py"
---
# Testing Conventions

## Structure

- Tests live in `tests/`, mirroring `src/kitefs/` module structure
- One test file per source module (e.g., `test_definitions.py` for `definitions.py`)
- Use descriptive test names: `test_<function>_<scenario>_<expected>`

## Filesystem Isolation

- Always use `tmp_path` fixture for any test that reads/writes files
- Never write to the real project directory or hardcoded paths
- Create `kitefs.yaml` and `definitions/` inside `tmp_path` when testing SDK or registry flows

## Coverage

- Test both **success paths** and **error paths** for every public function
- For error paths: test invalid inputs, missing files, constraint violations, and edge cases
- Validate that the correct exception type is raised with an actionable message

## Test Data

- Reference use case data from `docs/docs-00-01-reference-use-case.md` for integration-style tests
- Use the real estate listing platform entities (`listing_features`, `town_market_features`) as realistic test fixtures
- For unit tests, prefer minimal inline data over shared fixtures

## Validation Testing

- Test all three `ValidationMode` behaviors: `ERROR` (reject), `FILTER` (pass valid), `NONE` (skip)
- Test Phase 1 schema validation separately from Phase 2 data validation
- Verify that Phase 2 never runs if Phase 1 fails

## Running Tests

- `just test` or `uv run pytest` — run all tests
- `just check` — lint + tests; run before considering work complete
- `uv run pytest tests/test_specific.py -k "test_name"` — run a single test
