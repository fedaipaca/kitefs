# Feature 13: Remote configuration and aws provider

## Goal

Let users switch a project from local to remote storage by changing configuration only, so SDK calls remain unchanged when the runtime target is `remote`.

## Description

Validates the remote configuration block, constructs an `AWSProvider`, and exposes AWS implementations of `RegistryStore`, `OfflineStore`, and `OnlineStore` through the provider boundary. `boto3` imports are confined to `src/kitefs/providers/aws/`. Per-operation configuration validation checks only the remote stores actually needed by an operation.

## Scope

- IN: Remote-mode `kitefs.yaml` validation, fixed remote backend `type` literal checks, AWS provider factory, boto3 client construction confined to `providers/aws/`, credential-safe `ConfigurationError` and `ProviderError`, per-operation validation of needed remote sections.
- NOT IN: Actual S3 read/write logic (Feature 14, 15), DynamoDB read/write logic (Feature 16), post-MVP `pull`.

## Expected output

In a project whose configuration resolves `runtime.target` to `remote` and provides valid AWS settings, `FeatureStore()` constructs successfully and is wired to AWS provider interfaces. Operations that need an unconfigured remote store fail with `ConfigurationError` naming the missing capability before any AWS call is made.

## Implements

`AWSProvider`, AWS implementations of `RegistryStore`/`OfflineStore`/`OnlineStore` (constructors and ABC compliance only; methods filled in by Features 14–16), `FeatureStore.__init__` (remote path), additional `ConfigurationError` and `ProviderError` cases — as declared in `specs/interfaces.py`.

## Dependencies

Feature 3.

## Behavior

1. Detect remote target after env interpolation and `KITEFS_RUNTIME_TARGET` override.
2. Require a `remote` section when the runtime target is `remote`; raise `ConfigurationError` otherwise.
3. Validate `remote.registry.type == "aws_s3"` whenever a registry capability is needed.
4. Validate `remote.offline_store.type == "aws_s3"` whenever an offline capability is needed.
5. Validate `remote.online_store.type == "aws_dynamodb"` whenever an online capability is needed.
6. Reject `${...}` interpolation expressions on any fixed `type` field; these must be exact literals.
7. Per-operation validation: only the remote stores an operation actually needs are validated; an unused store may be absent without failing the operation.
8. Validate required values (`remote.region`, registry/offline `bucket`, registry/offline `s3_prefix`, online `dynamodb_table_prefix`) only when needed.
9. Build the `AWSProvider` with boto3 clients for S3 and DynamoDB based on the resolved region.
10. Confine every `boto3`/`botocore` import to `src/kitefs/providers/aws/`. Importing the base `kitefs` package on a machine without the `aws` extra must not fail.
11. Use the standard boto3 credential chain (env vars, AWS config files, instance roles, etc.). KiteFS never reads, stores, or prompts for credentials.
12. Map boto3 client errors into actionable `ProviderError`/`ConfigurationError` messages without echoing secret values (no access keys, tokens, or session tokens in error text).

## Error Handling

| Error                | When                                                | Behavior                                                      |
| -------------------- | --------------------------------------------------- | ------------------------------------------------------------- |
| `ConfigurationError` | `runtime.target` is `remote` but `remote` is absent | Raise; message names the missing section                      |
| `ConfigurationError` | Needed remote sub-section is missing                | Raise; message names the capability (registry/offline/online) |
| `ConfigurationError` | Fixed `type` literal is wrong or interpolated       | Raise; message names the setting and expected literal         |
| `ProviderError`      | AWS extra (`boto3`) not installed                   | Raise; message suggests `pip install kitefs[aws]`             |
| `ProviderError`      | boto3 fails to authenticate or initialize           | Raise without leaking secrets                                 |

## Example

Input: a `kitefs.yaml` matching the producer template; environment has `KITEFS_RUNTIME_TARGET=remote`, `KITEFS_REMOTE_REGISTRY_S3_BUCKET=company-ml`, `KITEFS_REMOTE_OFFLINE_S3_BUCKET=company-ml`, valid AWS credentials available to the default boto3 chain.
Output: `FeatureStore()` constructs; the provider is an `AWSProvider`. A subsequent `list_feature_groups()` call (Feature 14) would read from `s3://company-ml/kitefs/registry.json`.

Input: same project but `runtime.target` is `remote` and `remote.registry.bucket` is empty when a list call is made.
Output: `ConfigurationError("remote registry bucket is not configured; set remote.registry.bucket or KITEFS_REMOTE_REGISTRY_S3_BUCKET")` before any S3 call.

## BDD Scenarios

```gherkin
Scenario: Remote runtime constructs with valid registry configuration
  Given runtime.target resolves to "remote"
  And remote.region is "eu-central-1"
  And remote.registry.type is "aws_s3"
  And remote.registry.bucket is "company-ml"
  And remote.registry.s3_prefix is "kitefs"
  When the user creates FeatureStore()
  Then no exception is raised
  And the active runtime target is "remote"
  And the active provider is the AWS provider

Scenario: Remote target without a remote section fails clearly
  Given runtime.target is "remote"
  And "kitefs.yaml" has no remote section
  When the user creates FeatureStore()
  Then ConfigurationError is raised
  And the error message contains "remote"

Scenario: Missing remote offline configuration does not block online retrieval
  Given runtime.target is "remote"
  And the remote registry contains "town_market_features"
  And remote.online_store.type is "aws_dynamodb"
  And remote.online_store.dynamodb_table_prefix is "kitefs_"
  And remote.offline_store is absent
  When the user calls get_online_features for "town_market_features" where town_id equals 1
  Then no ConfigurationError about offline storage is raised

Scenario: Missing needed remote offline configuration fails before ingestion
  Given runtime.target is "remote"
  And remote.offline_store is absent
  When the user calls store.ingest("town_market_features", df)
  Then ConfigurationError is raised
  And the error message contains "remote offline"

Scenario: Interpolated remote type field is rejected
  Given runtime.target is "remote"
  And remote.registry.type is "${KITEFS_REMOTE_REGISTRY_TYPE:-aws_s3}"
  When the user creates FeatureStore()
  Then ConfigurationError is raised
  And the error message contains "remote.registry.type"
  And the error message contains "literal"

Scenario: Missing boto3 extra fails with installation guidance
  Given runtime.target is "remote"
  And the AWS extra is not installed
  When the user creates FeatureStore()
  Then ProviderError is raised
  And the error message contains "boto3"
  And the error message contains "kitefs[aws]"
```
