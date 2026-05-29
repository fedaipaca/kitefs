Feature: Local online store retrieval

  Scenario: Retrieve market feature for prediction
    Given "town_market_features" has been materialized with a row for town_id 1
    When the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 1
    Then no exception is raised
    And the result contains town_id 1
    And the result contains "event_timestamp"
    And the result contains "avg_price_per_sqm"

  Scenario: Online miss returns an empty dict
    Given "town_market_features" has been materialized without a row for town_id 999
    When the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 999
    Then no exception is raised
    And the result is {}

  Scenario: Never-materialized table returns an empty dict
    Given "town_market_features" is registered with storage_target OFFLINE_AND_ONLINE
    And "town_market_features" has not been materialized
    When the user calls get_online_features from "town_market_features" with select ["avg_price_per_sqm"] where town_id equals 1
    Then no exception is raised
    And the result is {}

  Scenario: Offline-only group is rejected for online retrieval
    Given "listing_features" is registered with storage_target OFFLINE
    When the user calls get_online_features from "listing_features" with select ["net_area"] where listing_id equals 1002
    Then FeatureGroupNotMaterializableError is raised
    And the error message contains "listing_features"
    And the error message contains "OFFLINE"

  Scenario: Filter on a non-entity-key field is rejected
    Given "town_market_features" is registered with entity key "town_id"
    When the user calls get_online_features with where avg_price_per_sqm equals 24500.0
    Then RetrievalParameterError is raised
    And the error message contains "avg_price_per_sqm"
    And the error message contains "town_id"
