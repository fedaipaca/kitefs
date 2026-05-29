Feature: Local offline store historical retrieval without joins

  Scenario: Retrieve selected listing features for training
    Given valid "listing_features" rows have been ingested
    When the user calls get_historical_features from "listing_features" with select ["net_area", "sold_price"]
    Then no exception is raised
    And the result columns are ["listing_id", "sold_at", "town_id", "net_area", "sold_price"]

  Scenario: Retrieve all listing feature fields
    Given valid "listing_features" rows have been ingested
    When the user calls get_historical_features from "listing_features" with select ["*"]
    Then no exception is raised
    And the result includes all declared listing feature columns

  Scenario: Filter listing rows by sold_at range
    Given valid "listing_features" rows have been ingested
    When the user retrieves listing features where sold_at is in April 2024
    Then no exception is raised
    And every returned row has sold_at in April 2024

  Scenario: Empty time range returns expected columns
    Given "listing_features" is registered
    And no listing rows exist for December 2030
    When the user retrieves "net_area" and "sold_price" for December 2030
    Then no exception is raised
    And the result has zero rows

  Scenario: Unknown selected feature is rejected
    Given "listing_features" is registered
    When the user calls get_historical_features from "listing_features" with select ["city_name"]
    Then RetrievalParameterError is raised
    And the error message contains "city_name"
    And the error message contains "feature"

  Scenario: Filter on a non-timestamp column is rejected
    Given "listing_features" is registered
    When the user filters on "town_id" with gte 1
    Then RetrievalParameterError is raised
    And the error message contains "town_id"
