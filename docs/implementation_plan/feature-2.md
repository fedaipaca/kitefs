# Feature 2: Project scaffold and local configuration

## Goal

Give users a one-command path from an empty directory to a usable KiteFS project so they can start defining features locally without any infrastructure setup.

## Description

The CLI commands `kitefs init` (producer) and `kitefs init-config` (consumer) scaffold the local project files needed before any SDK operation can run. They create `kitefs.yaml`, the fixed local directories where needed, an empty registry, an example feature definition, and the `.gitignore` entries that keep the registry out of version control.

## Scope

- IN: `kitefs init`, `kitefs init-config`, generated `kitefs.yaml` content, fixed local paths from `specs/06-api-and-cli-contracts.md`, `.gitignore` entries, the example feature definition file, the root Click group and CLI error boundary.
- NOT IN: SDK runtime loading, registry generation, any storage reads/writes beyond scaffold files.

## Expected output

A user can run `kitefs init` in an empty directory and get a usable KiteFS project scaffold. Running `kitefs init-config` instead creates the consumer-only configuration file. Both commands abort cleanly when `./kitefs.yaml` already exists.

## Implements

Nothing from `contracts.py` directly. Provides CLI entry point plus the scaffold files that every later feature depends on.

## Dependencies

Feature 1 (uses `KiteFSError` for the CLI error boundary).

## Behavior

1. Register the `kitefs` console command via Click; running it with no subcommand prints help and exits non-zero.
2. Every subcommand supports `--help` and rejects invalid input before any work.
3. The global error boundary catches `KiteFSError`, prints the message to stderr without traceback, and exits `1`; unexpected errors exit `2`.
4. `kitefs init`: abort if `./kitefs.yaml` exists.
5. `kitefs init`: write `./kitefs.yaml` using the producer template from `specs/06-api-and-cli-contracts.md`, with `runtime.target` interpolating `${KITEFS_RUNTIME_TARGET:-local}`.
6. `kitefs init`: create `./feature_store/definitions/` and write one example feature group definition file inside it.
7. `kitefs init`: create `./feature_store/data/offline_store/` and `./feature_store/data/online_store/`.
8. `kitefs init`: write `./feature_store/registry.json` with `{"feature_groups": {}}` plus trailing newline.
9. `kitefs init`: append `.gitignore` entries for `feature_store/data/` and `feature_store/registry.json`.
10. `kitefs init-config`: abort if `./kitefs.yaml` exists; write only `./kitefs.yaml` using the consumer template (no directories, no example).
11. Print a success summary listing the created files on success.

## Error Handling

| Error                   | When                                      | Behavior                                                 |
| ----------------------- | ----------------------------------------- | -------------------------------------------------------- |
| Already initialized     | `./kitefs.yaml` exists                    | Print message to stderr, exit non-zero, no files changed |
| I/O failure on scaffold | Cannot create a directory or write a file | Exit non-zero; do not expose a partial scaffold          |
| Invalid CLI input       | Unsupported flags or arguments            | Click rejects before any work                            |

## Example

Input: `kitefs init` in an empty directory for the Turkish real estate demo.
Output: `./kitefs.yaml`, `./feature_store/definitions/<example>.py`, `./feature_store/data/offline_store/`, `./feature_store/data/online_store/`, `./feature_store/registry.json` (containing `{"feature_groups": {}}`), and `.gitignore` entries for `feature_store/data/` and `feature_store/registry.json`. The user can next drop in `listing_features.py` and `town_market_features.py` from the reference use case.

## BDD Scenarios

```gherkin
Scenario: kitefs init creates a usable producer project scaffold
  Given an empty working directory
  When the user runs "kitefs init"
  Then the command exits 0
  And "kitefs.yaml" exists
  And "feature_store/definitions/" exists
  And "feature_store/data/offline_store/" exists
  And "feature_store/data/online_store/" exists
  And "feature_store/registry.json" contains an empty registry
  And ".gitignore" contains entries for KiteFS data and registry files

Scenario: kitefs init creates an example feature definition
  Given an empty working directory
  When the user runs "kitefs init"
  Then "feature_store/definitions/" contains a Python feature definition file
  And the example definition file contains "FeatureGroup"

Scenario: kitefs init refuses to overwrite an existing project
  Given "kitefs.yaml" already exists with content "project: existing"
  When the user runs "kitefs init"
  Then the command exits non-zero
  And stderr contains "kitefs.yaml"
  And stderr contains "already"
  And "kitefs.yaml" still contains "project: existing"

Scenario: kitefs init-config creates consumer configuration only
  Given an empty working directory
  When the user runs "kitefs init-config"
  Then the command exits 0
  And "kitefs.yaml" exists
  And "feature_store/" does not exist

Scenario: kitefs init-config refuses to overwrite an existing project
  Given "kitefs.yaml" already exists with content "project: existing"
  When the user runs "kitefs init-config"
  Then the command exits non-zero
  And stderr contains "kitefs.yaml"
  And stderr contains "already"
  And "kitefs.yaml" still contains "project: existing"
```
