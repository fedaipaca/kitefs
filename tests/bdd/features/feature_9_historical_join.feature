Feature: Point-in-time historical retrieval with joins

  Scenario: Latest eligible market row is selected for listing 1002
    Given listing_features contains listing 1002 sold on 2024-04-05 14:00:00 in town 1
    And town_market_features has rows for town 1 dated 2024-02-01, 2024-03-01, 2024-04-01, 2024-05-01
    When I retrieve listing features joined to town market features
    Then listing 1002 gets town_market_features_avg_price_per_sqm from the 2024-04-01 row
    And the 2024-05-01 market row is not used

  Scenario: Base row with no eligible joined row keeps null joined columns
    Given listing 1010 was sold at 2024-01-20T17:00:00Z in town_id 3
    And the earliest "town_market_features" row is dated 2024-02-01T00:00:00Z
    When the user retrieves "listing_features" joined to "town_market_features"
    Then no exception is raised
    And the row for listing_id 1010 is present
    And town_market_features_avg_price_per_sqm is null for listing_id 1010

  Scenario: More than one joined group is rejected
    Given "listing_features" is registered
    And "city_market_features" is registered
    When the user calls get_historical_features with join ["town_market_features", "city_market_features"]
    Then JoinError is raised
    And the error message contains "at most one"

  Scenario: List select is rejected when join is provided
    Given "listing_features" and "town_market_features" are registered
    When the user calls get_historical_features with join ["town_market_features"] and select ["net_area"]
    Then RetrievalParameterError is raised
    And the error message contains "select"
    And the error message contains "dict"

  Scenario: Join without a registered relationship is rejected
    Given "town_market_features" and "city_market_features" are registered
    And "town_market_features" does not declare a join key to "city_market_features"
    When the user retrieves "town_market_features" joined to "city_market_features"
    Then JoinError is raised
    And the error message contains "city_market_features"
    And the error message contains "JoinKey"
