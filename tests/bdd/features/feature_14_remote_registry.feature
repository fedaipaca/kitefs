Feature: Remote registry publish, list, and describe (S3)

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
    And stderr contains "apply --publish"

  Scenario: Remote describe unknown group lists known names
    Given runtime.target resolves to "remote"
    And the S3 registry contains only "listing_features" and "town_market_features"
    When the user runs "kitefs describe neighborhood_features"
    Then the command exits non-zero
    And stderr contains "neighborhood_features"
    And stderr contains "listing_features"
