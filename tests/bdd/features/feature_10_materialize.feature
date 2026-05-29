Feature: Local SQLite online store materialization

  Scenario: Materialize the latest market row per town
    Given "town_market_features" has 72 offline rows for 12 months and 6 towns
    When the user calls store.materialize("town_market_features")
    Then no exception is raised
    And result.succeeded contains "town_market_features"
    And result.skipped is empty
    And result.failed is empty
    And SQLite table town_market_features has exactly 6 rows
    And the registry entry for "town_market_features" has last_materialized_at set

  Scenario: Named materialization rejects an unknown group
    Given the registry contains only "town_market_features"
    When the user calls store.materialize("neighborhood_features")
    Then FeatureGroupNotFoundError is raised
    And the error message contains "neighborhood_features"

  Scenario: Named materialization rejects an offline-only group
    Given "listing_features" is registered with storage_target OFFLINE
    When the user calls store.materialize("listing_features")
    Then FeatureGroupNotMaterializableError is raised
    And the error message contains "listing_features"
    And the error message contains "OFFLINE"

  Scenario: Materialization skips a group with no offline data
    Given "town_market_features" is registered with storage_target OFFLINE_AND_ONLINE
    And "town_market_features" has no offline rows
    When the user calls store.materialize("town_market_features")
    Then no exception is raised
    And result.skipped contains a group named "town_market_features" with reason "no offline data"
    And result.succeeded is empty
    And result.failed is empty
