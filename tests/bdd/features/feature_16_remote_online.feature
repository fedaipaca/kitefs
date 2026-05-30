Feature: Feature 16 — Remote materialization and online store retrieval (DynamoDB)

  Scenario: Remote materialize makes latest town market rows available online
    Given runtime.target resolves to "remote"
    And remote offline data exists for "town_market_features" with 72 rows for 12 months and 6 towns
    And the remote online store table prefix is "kitefs_"
    When the user calls store.materialize("town_market_features")
    Then no exception is raised
    And result.succeeded contains "town_market_features"
    And a later online lookup for each town returns that town's latest market row

  Scenario: Remote online retrieval returns a hit
    Given runtime.target resolves to "remote"
    And the remote online store has town_id 5, avg_price_per_sqm 15200.0, event_timestamp 2025-07-01T00:00:00.000000Z
    When the user gets online features from "town_market_features" with select ["avg_price_per_sqm"] where town_id is 5
    Then no exception is raised
    And the result contains town_id 5
    And the result contains avg_price_per_sqm 15200.0
    And the result contains event_timestamp 2025-07-01T00:00:00Z

  Scenario: Remote online miss returns an empty dict
    Given runtime.target resolves to "remote"
    And the remote online store has no item for town_id 999
    When the user gets online features from "town_market_features" selecting ["avg_price_per_sqm"] where town_id is 999
    Then no exception is raised
    And the result is {}

  Scenario: Remote online retrieval from a never-materialized group returns an empty dict
    Given runtime.target resolves to "remote"
    And "town_market_features" has never been materialized to the remote online store
    When the user gets online features from "town_market_features" with select ["avg_price_per_sqm"] where town_id is 1
    Then no exception is raised
    And the result is {}

  Scenario: Existing remote online table with wrong key schema fails materialization for the group
    Given runtime.target resolves to "remote"
    And remote offline data exists for "town_market_features"
    And the remote online table for "town_market_features" has partition key "city_id"
    When the user calls store.materialize("town_market_features")
    Then no exception is raised
    And result.failed contains a group named "town_market_features"
    And the failure message contains "partition key"
    And the failure message contains "town_id"

  Scenario: Missing remote online configuration fails clearly
    Given runtime.target resolves to "remote"
    And remote.online_store is absent
    When the user calls store.materialize("town_market_features")
    Then ConfigurationError is raised
    And the error message contains "remote online"

  Scenario: Remote online read failures are surfaced
    Given runtime.target resolves to "remote"
    And "town_market_features" is registered as online-capable
    And the remote online read fails with "AccessDenied"
    When the user gets online features from "town_market_features" with select ["avg_price_per_sqm"] where town_id is 1
    Then OnlineStoreReadError is raised
    And the error message contains "AccessDenied"
