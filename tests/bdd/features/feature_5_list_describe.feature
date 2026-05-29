Feature: Local registry list and describe

  Scenario: List registered reference feature groups
    Given "listing_features" and "town_market_features" have been applied
    When the user runs "kitefs list"
    Then the command exits 0
    And stdout contains "listing_features"
    And stdout contains "town_market_features"

  Scenario: List returns an empty result for an empty registry
    Given the registry contains no feature groups
    When the user calls FeatureStore().list_feature_groups()
    Then the result is an empty list

  Scenario: Describe a registered feature group as JSON
    Given "town_market_features" has been applied
    When the user runs "kitefs describe town_market_features --format json"
    Then the command exits 0
    And stdout is a JSON object
    And the JSON output has entity_key.name "town_id"
    And the JSON output has storage_target "OFFLINE_AND_ONLINE"
    And the JSON output contains feature "avg_price_per_sqm"

  Scenario: Describe an unknown feature group
    Given the registry contains only "listing_features" and "town_market_features"
    When the user runs "kitefs describe neighborhood_features"
    Then the command exits non-zero
    And stderr contains "FeatureGroupNotFoundError"
    And stderr contains "neighborhood_features"
    And stderr contains "listing_features"
    And stderr contains "town_market_features"
