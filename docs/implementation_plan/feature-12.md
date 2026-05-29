# Feature 12: CLI wrappers for SDK operations

## Goal

Expose the MVP SDK operations through Click commands so users can drive KiteFS from a terminal or CI/CD without writing Python, with consistent output and no Python tracebacks for expected errors.

## Description

Wires `kitefs apply`, `kitefs ingest`, and `kitefs materialize` to the SDK `FeatureStore`, applies the global CLI error boundary, and renders the SDK return types as plain-text or JSON output. `apply --publish` prompts for an exact `yes` unless `--no-confirm` is passed; this feature only wires the confirmation flow against the local apply path (publish itself is implemented in Feature 14).

## Scope

- IN: CLI `apply` (calls SDK `apply(publish=...)`), CLI `ingest <name> <path>`, CLI `materialize [name]`, publish confirmation prompt, exit-code rules, plain-text and JSON rendering for the relevant result types.
- NOT IN: SDK business logic, SDK-only commands (`get_historical_features`, `get_online_features`), `kitefs init` / `init-config` (Feature 2), remote registry publish behavior itself (Feature 14).

## Expected output

A user can run `kitefs apply`, `kitefs ingest <group> <file.csv|file.parquet>`, and `kitefs materialize [group]` end-to-end against a local project and get the same observable outcomes as the SDK calls, with non-zero exits on expected user errors and on materialization runs that contain failed groups.

## Implements

CLI subcommands wiring `FeatureStore.apply`, `FeatureStore.ingest`, and `FeatureStore.materialize` (BB-01). Rendering of `ApplyResult`, `IngestResult`, `MaterializeResult` to stdout. No new public interfaces.

## Dependencies

Feature 5 (CLI scaffolding and error boundary already in place via Features 2 and 5), Feature 7, Feature 10.

## Behavior

1. CLI subcommands all live under the existing `kitefs` Click group; each has `--help`.
2. CLI handlers do not contain domain logic; they construct `FeatureStore()` and call SDK methods.
3. `kitefs apply` calls `FeatureStore().apply(publish=False)` by default and prints `ApplyResult.registered_groups`.
4. `kitefs apply --publish` prompts on stderr for the exact word `yes` (case-sensitive) before any config loading; any other input aborts non-zero. `--no-confirm` skips the prompt.
5. On confirmed publish, the handler calls `FeatureStore().apply(publish=True)`.
6. `kitefs ingest <group_name> <path>` validates that `<path>` ends in `.csv` or `.parquet` before constructing the SDK; otherwise exits `1` with an actionable message.
7. `kitefs ingest` then calls `FeatureStore().ingest(group_name, path)` and prints `accepted_rows`, `rejected_rows`, and the count of written files.
8. `kitefs materialize [group_name]` calls `FeatureStore().materialize(group_name)` (or with no argument for all online-eligible groups).
9. The handler prints the per-group summary (`succeeded`, `skipped`, `failed`); if `MaterializeResult.failed` is non-empty, exits non-zero.
10. Expected `KiteFSError` exceptions render to stderr as plain text with operation context and exit `1`. Unexpected exceptions exit `2` and may show their traceback.

## Error Handling

| Error                         | When                                           | Behavior                                                 |
| ----------------------------- | ---------------------------------------------- | -------------------------------------------------------- |
| Any `KiteFSError`             | Raised by SDK during the command               | Print actionable message to stderr; exit `1`             |
| Unexpected exception          | Non-`KiteFSError` bubbles up                   | Exit `2` (traceback allowed)                             |
| Publish declined              | Confirmation input is not exact `yes`          | Abort before configuration loading; exit non-zero        |
| Unsupported ingest path       | `<path>` extension is not `.csv` or `.parquet` | Exit `1` before SDK construction with actionable message |
| Materialization with failures | `MaterializeResult.failed` is non-empty        | Print summary; exit non-zero                             |

## Example

Input: `kitefs ingest town_market_features ./data/town_market_2024.parquet` in a project where the group is registered and data is valid.
Output (stdout): `Ingested 72 row(s) into 'town_market_features'. Wrote 12 file(s).` Exit code `0`.

Input: `kitefs materialize` after the same ingestion.
Output: `Succeeded: town_market_features. Skipped: (none). Failed: (none).` Exit code `0`.

## BDD Scenarios

```gherkin
Scenario: Apply through CLI succeeds
  Given "listing_features.py" and "town_market_features.py" exist in "feature_store/definitions/"
  When the user runs "kitefs apply"
  Then the command exits 0
  And stdout contains "listing_features"
  And stdout contains "town_market_features"

Scenario: CLI apply expected errors are printed without traceback
  Given "feature_store/definitions/" contains no FeatureGroup definitions
  When the user runs "kitefs apply"
  Then the command exits 1
  And stderr contains "DefinitionDiscoveryError"
  And stderr contains "FeatureGroup"
  And stderr does not contain "Traceback"

Scenario: CLI ingest succeeds for a CSV file
  Given "town_market_features" is registered
  And "data/town_market_2024_02.csv" contains 6 valid town market rows
  When the user runs "kitefs ingest town_market_features data/town_market_2024_02.csv"
  Then the command exits 0
  And stdout contains "Ingested 6 row"
  And stdout contains "town_market_features"

Scenario: CLI ingest rejects unsupported file extension
  Given a valid local project
  When the user runs "kitefs ingest town_market_features data/town_market.xlsx"
  Then the command exits 1
  And stderr contains ".csv"
  And stderr contains ".parquet"

Scenario: CLI materialize named group succeeds
  Given "town_market_features" has offline rows
  When the user runs "kitefs materialize town_market_features"
  Then the command exits 0
  And stdout contains "Succeeded"
  And stdout contains "town_market_features"

Scenario: Publish aborts when confirmation is not yes
  Given a valid local project
  When the user runs "kitefs apply --publish" and types "no"
  Then the command exits non-zero
  And stderr contains "aborted"
```
