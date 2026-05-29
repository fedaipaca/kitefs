# Feature 14: Remote registry publish, list, and describe (S3)

## Goal

Let producers publish the generated registry to S3 and let consumers list and describe feature groups from that S3 registry, so registry information can flow across environments without sharing local files.

## Description

`apply(publish=True)` writes the local working registry first, then writes the same deterministic JSON to S3. CLI `apply --publish` prompts for confirmation unless `--no-confirm`. With `runtime.target: remote`, `list_feature_groups` and `describe_feature_group` read directly from the S3 registry.

## Scope

- IN: `FeatureStore.apply(publish=True)`, AWS `RegistryStore.read`/`write` (S3 PutObject/GetObject on `s3://{bucket}/{s3_prefix}/registry.json`), CLI publish confirmation, remote `list`/`describe`.
- NOT IN: Remote offline data (Feature 15), DynamoDB (Feature 16), post-MVP `pull`.

## Expected output

A producer can run `kitefs apply --publish --no-confirm` after defining the Turkish real estate groups locally; the S3 object `s3://{bucket}/{s3_prefix}/registry.json` is overwritten with the same JSON written locally. A consumer with `runtime.target: remote` can then run `kitefs list` and `kitefs describe town_market_features` against the S3 registry.

## Implements

`FeatureStore.apply` (publish path), `FeatureStore.list_feature_groups` (remote path), `FeatureStore.describe_feature_group` (remote path), AWS `RegistryStore.read`, AWS `RegistryStore.write` — as declared in `specs/interfaces.py`.

## Dependencies

Feature 4, Feature 5, Feature 12, Feature 13.

## Behavior

1. SDK `apply(publish=True)` does not prompt; CLI confirmation is the only prompting layer.
2. Validate the remote registry configuration (`remote.registry.type == "aws_s3"`, `bucket`, `s3_prefix`) before any work.
3. Run the same local-apply path (Feature 4) end-to-end: discover, validate, write the local working registry.
4. After the local write succeeds, serialize the same JSON document and write it to `s3://{bucket}/{s3_prefix}/registry.json` via a single `PutObject` call (S3 `PutObject` is atomic per object).
5. On full success, return `ApplyResult(registered_groups=<sorted>, published=True)`.
6. If the remote write fails after the local write succeeded, raise `RegistryWriteError`. The local working registry may already contain the new content (this is acceptable per FR-REG-003).
7. CLI `apply --publish` prompts on stderr for exact `yes` before any configuration loading; `--no-confirm` skips the prompt.
8. For `runtime.target: remote`, `list_feature_groups` and `describe_feature_group` call AWS `RegistryStore.read()` which `GetObject`s `s3://{bucket}/{s3_prefix}/registry.json` and parses the JSON.
9. Remote `list_feature_groups` returns an empty list when the S3 object exists but has no `feature_groups`.
10. Remote `describe_feature_group` raises `FeatureGroupNotFoundError` for an unknown name, listing the available names when known.
11. A missing S3 registry object surfaces as `RegistryReadError` whose message suggests `apply --publish`.

## Error Handling

| Error                       | When                                          | Behavior                                          |
| --------------------------- | --------------------------------------------- | ------------------------------------------------- |
| Publish declined            | CLI confirmation input is not exact `yes`     | Abort before configuration loading; exit non-zero |
| `ConfigurationError`        | Remote registry configuration missing/invalid | Raise before discovery                            |
| `DefinitionDiscoveryError`  | No definitions discovered                     | Raise; nothing is written locally or remotely     |
| `DefinitionValidationError` | Cross-definition validation fails             | Raise; nothing is written locally or remotely     |
| `RegistryWriteError`        | Local write fails before remote write         | Raise; remote unchanged                           |
| `RegistryWriteError`        | Remote `PutObject` fails after local write    | Raise; local registry may already be updated      |
| `RegistryReadError`         | S3 registry object missing or unreadable      | Raise with actionable message (suggest publish)   |
| `FeatureGroupNotFoundError` | Remote describe target absent                 | Raise                                             |

## Example

Input (producer): after defining `listing_features.py` and `town_market_features.py` locally and configuring `KITEFS_REMOTE_REGISTRY_S3_BUCKET=company-ml`, run `kitefs apply --publish --no-confirm`.
Output: local `./feature_store/registry.json` is regenerated; `s3://company-ml/kitefs/registry.json` is overwritten with the same JSON; CLI prints `Registered 2 group(s) and published to s3://company-ml/kitefs/registry.json`.

Input (consumer): in a project initialized by `kitefs init-config` with `runtime.target=remote` pointing at the same bucket, run `kitefs list`.
Output: lists `listing_features` and `town_market_features` from the S3 registry.

## BDD Scenarios

```gherkin
Scenario: Publish the registry to S3
  Given valid local definitions for "listing_features" and "town_market_features"
  And the remote registry is configured at "s3://company-ml/kitefs/registry.json"
  When the user calls FeatureStore().apply(publish=True)
  Then no exception is raised
  And result.registered_groups equals ["listing_features", "town_market_features"]
  And result.published is True
  And the S3 registry object contains "listing_features"
  And the S3 registry object contains "town_market_features"

Scenario: Consumer lists the remote registry
  Given runtime.target resolves to "remote"
  And the S3 registry contains "listing_features" and "town_market_features"
  When the user runs "kitefs list"
  Then the command exits 0
  And stdout contains "listing_features"
  And stdout contains "town_market_features"

Scenario: Consumer describes a remote feature group
  Given runtime.target resolves to "remote"
  And the S3 registry contains "town_market_features"
  When the user runs "kitefs describe town_market_features --format json"
  Then the command exits 0
  And stdout is a JSON object
  And the JSON output has entity_key.name "town_id"
  And the JSON output has storage_target "OFFLINE_AND_ONLINE"

Scenario: Missing remote registry surfaces a clear error
  Given runtime.target resolves to "remote"
  And the S3 registry object does not exist
  When the user runs "kitefs list"
  Then the command exits non-zero
  And stderr contains "RegistryReadError"
  And stderr contains "apply --publish"

Scenario: Remote describe unknown group lists known names
  Given runtime.target resolves to "remote"
  And the S3 registry contains only "listing_features" and "town_market_features"
  When the user runs "kitefs describe neighborhood_features"
  Then the command exits non-zero
  And stderr contains "FeatureGroupNotFoundError"
  And stderr contains "neighborhood_features"
  And stderr contains "listing_features"
```
