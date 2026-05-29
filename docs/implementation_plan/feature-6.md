# Feature 6: Validation engine

## Goal

Provide a single, stateless way to check that a DataFrame matches a registered feature group's schema and expectations so ingestion and retrieval can enforce data quality consistently at the configured gates.

## Description

A storage-agnostic engine that takes a registered group description, a DataFrame, and an operation mode (`ERROR`, `FILTER`, `NONE`) and either raises, filters, or passes through rows. Structural checks (entity key, event timestamp, join key, structural dtype compatibility, and UTC validation for structural datetime values) always run. Feature-level dtype checks, UTC validation for DATETIME feature values, and feature-level expectations run per the operation's mode.

## Scope

- IN: Validation Engine stateless validation: structural null/dtype/UTC checks, feature dtype checks, expectation operators (`not_null`, `gt`, `gte`, `lt`, `lte`, `is_in`), per-mode behavior, `ValidationReport`, `ValidationFailure`.
- NOT IN: Storage I/O, online retrieval validation, materialization validation, deciding when to call the engine (callers do that).

## Expected output

Callers can validate a Pandas DataFrame against any registered group and either get back a filtered DataFrame plus report (in `FILTER`), the original DataFrame (in `NONE`), or a `ValidationError` (in `ERROR` or any structural failure). The engine never reads or writes storage.

## Implements

Internal validation engine, `ValidationReport`, `ValidationFailure`, `ValidationError`, `IngestionShapeError` — as declared in `contracts.py`.

## Dependencies

Feature 4.

## Behavior

1. Accept a registered group description, a Pandas DataFrame, the operation mode, and operation context (for error messages).
2. Shape check: every declared structural column (entity key, event timestamp, join key when declared) and every declared feature column must be present in the DataFrame; otherwise raise `IngestionShapeError`. Extra columns are ignored here and handled by the caller.
3. Always run structural checks regardless of mode:
   - Entity key, event timestamp, and join key values cannot be null.
   - Structural value dtypes must be compatible with the declared `FeatureType`.
   - Datetime values are either naive (treated as UTC) or UTC-aware; non-UTC tz-aware values are rejected.
4. Any structural failure raises `ValidationError` immediately, including in `FILTER` and `NONE`.
5. In `NONE` mode, skip all feature-level checks and return the DataFrame unchanged with `validation_report = None`.
6. In `ERROR` and `FILTER` modes, check feature dtype compatibility and evaluate every declared expectation (`not_null`, `gt`, `gte`, `lt`, `lte`, `is_in`) against the feature columns.
7. Build a `ValidationFailure` per failing row × failing check with field, constraint, actual value, entity key value, and row index.
8. In `ERROR` mode, raise `ValidationError` carrying a `ValidationReport` if any feature check failed.
9. In `FILTER` mode, drop the failing rows, return the passing subset DataFrame, and produce a `ValidationReport` with `pass_count`, `fail_count`, and `failures`.

## Error Handling

| Error                 | When                                                      | Behavior                                                                 |
| --------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------ |
| `IngestionShapeError` | A required structural or feature column is missing        | Raise; no rows are processed                                             |
| `ValidationError`     | Any structural failure (null, dtype, non-UTC) in any mode | Raise with `ValidationReport`                                            |
| `ValidationError`     | Any feature failure in `ERROR` mode                       | Raise with `ValidationReport`                                            |
| Per-row failure       | Feature failure in `FILTER` mode                          | Drop the row; record in `ValidationReport`                               |
| No failures           | All rows pass                                             | Return DataFrame plus pass-only `ValidationReport` (or `None` in `NONE`) |

## Example

Input: a DataFrame for `town_market_features` with one row `town_id=3, avg_price_per_sqm=-10.0, event_timestamp=2024-02-01T00:00:00Z`. Group's `ingestion_validation` is `ERROR` and the feature declares `Expect().not_null().gt(0)`.
Output: `ValidationError` carrying a `ValidationReport` with one `ValidationFailure(field="avg_price_per_sqm", constraint="gt(0)", actual=-10.0, entity_key_value=3, row_index=0)`.

Input: the same DataFrame with mode `FILTER` plus a second valid row for `town_id=1`.
Output: a one-row DataFrame containing only `town_id=1`, and a `ValidationReport(pass_count=1, fail_count=1, failures=[...])`.

## BDD Scenarios

```gherkin
Scenario: Valid rows pass in ERROR mode
  Given "town_market_features" expects "avg_price_per_sqm" to be not_null and gt 0
  And a DataFrame contains town_id 1, avg_price_per_sqm 24500.0, and event_timestamp 2024-02-01T00:00:00Z
  When the DataFrame is validated in ERROR mode
  Then no exception is raised
  And the validation report has pass_count 1
  And the validation report has fail_count 0

Scenario: Feature expectation failure raises in ERROR mode
  Given "town_market_features" expects "avg_price_per_sqm" to be gt 0
  And a DataFrame contains town_id 3, avg_price_per_sqm -10.0, and event_timestamp 2024-02-01T00:00:00Z
  When the DataFrame is validated in ERROR mode
  Then ValidationError is raised
  And the error report contains one failure for field "avg_price_per_sqm"

Scenario: Feature expectation failure filters rows in FILTER mode
  Given "town_market_features" expects "avg_price_per_sqm" to be gt 0
  And a DataFrame contains town_id 1 with avg_price_per_sqm 24500.0
  And the DataFrame contains town_id 3 with avg_price_per_sqm -10.0
  When the DataFrame is validated in FILTER mode
  Then the returned DataFrame contains only town_id 1
  And the validation report has pass_count 1
  And the validation report has fail_count 1

Scenario: Null entity key is rejected in every mode
  Given "town_market_features" has entity key "town_id"
  And a DataFrame contains a null town_id and event_timestamp 2024-02-01T00:00:00Z
  When the DataFrame is validated in NONE mode
  Then ValidationError is raised
  And the error report contains a failure for field "town_id"
```
