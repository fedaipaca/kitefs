Feature: Local registry apply

  Scenario: Apply the reference feature definitions
    Given "listing_features.py" and "town_market_features.py" exist in "feature_store/definitions/"
    When the user calls FeatureStore().apply()
    Then no exception is raised
    And result.registered_groups equals ["listing_features", "town_market_features"]
    And result.published is False
    And "feature_store/registry.json" contains "listing_features"
    And "feature_store/registry.json" contains "town_market_features"

  Scenario: Apply fails when no feature groups are discovered
    Given "feature_store/definitions/" contains no FeatureGroup definitions
    And the registry already contains "town_market_features"
    When the user calls FeatureStore().apply()
    Then DefinitionDiscoveryError is raised
    And the error message contains "FeatureGroup"
    And the error message contains "declare"
    And the registry still contains "town_market_features"

  Scenario: Apply reports duplicate group names
    Given two definition files both declare a FeatureGroup named "town_market_features"
    And the registry already contains an empty registry
    When the user calls FeatureStore().apply()
    Then DefinitionValidationError is raised
    And the error message contains "town_market_features"
    And the error message contains "duplicate"
    And the registry remains an empty registry

  Scenario: Apply rejects a missing join target
    Given "listing_features.py" references "town_market_features"
    And "town_market_features.py" is missing
    When the user calls FeatureStore().apply()
    Then DefinitionValidationError is raised
    And the error message contains "town_market_features"
    And the error message contains "referenced"
