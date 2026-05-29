# Feature 3: Configuration runtime and local provider boundary

## Goal

Let users construct a working `FeatureStore` instance in an initialized local project, with a clean separation between core logic and the local storage backend so later operations can read configuration and storage through one consistent abstraction.

## Description

The configuration manager loads and validates `./kitefs.yaml`, applies environment variable interpolation, honours the `KITEFS_RUNTIME_TARGET` override, and exposes the resolved runtime target. The provider boundary (`Provider`, `RegistryStore`, `OfflineStore`, `OnlineStore` ABCs) is defined, and the local provider plus a local `RegistryStore` are wired through `FeatureStore.__init__`.

## Scope

- IN: Configuration Manager YAML loader, env interpolation `${VAR:-default}`, fixed-type validation, runtime target override. Provider Layer ABCs. `LocalProvider` factory and the local `RegistryStore` (atomic JSON read/write). `TimestampFilter` value object. `FeatureStore.__init__` wiring config → provider.
- NOT IN: Local `OfflineStore` and `OnlineStore` implementations, AWS provider, registry apply logic, validation engine, CLI SDK-backed commands.

## Expected output

In a directory created by `kitefs init`, `FeatureStore()` constructs successfully and is wired to a local provider whose `RegistryStore` reads and writes `./feature_store/registry.json`. Missing or invalid configuration raises `ConfigurationError` with an actionable message.

## Implements

`FeatureStore.__init__`, `Provider`, `RegistryStore`, `OfflineStore`, `OnlineStore` ABCs (signatures only for offline/online), local `RegistryStore` implementation, `TimestampFilter`, `ConfigurationError`, `ProviderError`, `RegistryReadError`, `RegistryWriteError` — all as declared in `contracts.py`.

## Dependencies

Feature 1, Feature 2.

## Behavior

1. Treat the current working directory as the project root; do not search parents.
2. Require `./kitefs.yaml`; if missing, raise `ConfigurationError` suggesting `kitefs init`.
3. Parse YAML; on parse error raise `ConfigurationError` with file context.
4. Validate fixed literal fields before interpolation: `remote.registry.type` and `remote.online_store.type` (and `remote.offline_store.type` when present) must be exact literals from the supported set; reject `${...}` expressions in these fields.
5. Apply `${VAR}` and `${VAR:-default}` interpolation to configurable fields.
6. Apply `KITEFS_RUNTIME_TARGET` env override to `runtime.target` after interpolation.
7. Validate required top-level fields: `version`, `project.name`, `runtime.target`.
8. Reject runtime target values other than `local` or `remote`.
9. When `runtime.target` is `local`, build a `LocalProvider`.
10. The local `RegistryStore.read()` reads and parses `./feature_store/registry.json`; on missing file raise `RegistryReadError`.
11. The local `RegistryStore.write()` serializes JSON with `sort_keys=True`, two-space indent, `ensure_ascii=False`, plus trailing newline, writes to a temp file in the same directory, and uses `os.replace()` to atomically install it.
12. Local paths are fixed; they are never read from `kitefs.yaml`.

## Error Handling

| Error                | When                                               | Behavior                                              |
| -------------------- | -------------------------------------------------- | ----------------------------------------------------- |
| `ConfigurationError` | `./kitefs.yaml` missing                            | Message suggests running `kitefs init`                |
| `ConfigurationError` | YAML parse error                                   | Message names the file and the parse problem          |
| `ConfigurationError` | Required field missing                             | Message names the missing key                         |
| `ConfigurationError` | Unsupported `runtime.target`                       | Message names the value and the allowed set           |
| `ConfigurationError` | Fixed remote `type` has interpolation or bad value | Message identifies the setting and expected literal   |
| `RegistryReadError`  | Local registry file missing or corrupt             | Raised by `LocalRegistryStore.read`                   |
| `RegistryWriteError` | Local registry write I/O failure                   | Raised by `LocalRegistryStore.write`; prior file kept |

## Example

Input: `FeatureStore()` invoked in a directory just created by `kitefs init`.
Output: SDK object is ready; its provider is the local provider, whose `RegistryStore` reads `./feature_store/registry.json` and currently returns `{"feature_groups": {}}`.

Input: same call in a directory with no `kitefs.yaml`.
Output: `ConfigurationError("kitefs.yaml not found in current directory. Run 'kitefs init' first.")`.

## BDD Scenarios

```gherkin
Scenario: Construct FeatureStore in an initialized local project
  Given an initialized local project for the reference use case
  When the user creates FeatureStore()
  Then no exception is raised
  And the active runtime target is "local"

Scenario: Missing kitefs.yaml fails clearly
  Given no "kitefs.yaml" exists in the current directory
  When the user creates FeatureStore()
  Then ConfigurationError is raised
  And the error message contains "kitefs.yaml"
  And the error message contains "kitefs init"

Scenario: Unsupported runtime target fails clearly
  Given "kitefs.yaml" has runtime.target "staging"
  When the user creates FeatureStore()
  Then ConfigurationError is raised
  And the error message contains "staging"
  And the error message contains "local"
  And the error message contains "remote"

Scenario: KITEFS_RUNTIME_TARGET overrides the resolved file value
  Given "kitefs.yaml" has runtime.target "local"
  And the environment variable KITEFS_RUNTIME_TARGET is "remote"
  And a valid remote section is configured
  When the user creates FeatureStore()
  Then no exception is raised
  And the active runtime target is "remote"
```
