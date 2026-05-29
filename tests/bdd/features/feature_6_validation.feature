Feature: Validation engine

  Scenario: Valid rows pass in ERROR mode
    Given "town_market_features" expects "avg_price_per_sqm" to be not_null and gt 0
    And a DataFrame contains town_id 1, avg_price_per_sqm 24500.0, and event_timestamp 2024-02-01T00:00:00Z
    When the DataFrame is validated in ERROR mode
    Then no exception is raised
    And the validation report has pass_count 1
    And the validation report has fail_count 0

  Scenario: Feature expectation failure raises in ERROR mode
    Given "town_market_features" expects "avg_price_per_sqm" to be gt 0
    And a DataFrame contains town_id 3, avg_price_per_sqm -10.0, and event_timestamp 2024-02-01T00:00:00Z
    When the DataFrame is validated in ERROR mode
    Then ValidationError is raised
    And the error report contains one failure for field "avg_price_per_sqm"

  Scenario: Feature expectation failure filters rows in FILTER mode
    Given "town_market_features" expects "avg_price_per_sqm" to be gt 0
    And a DataFrame contains town_id 1 with avg_price_per_sqm 24500.0
    And the DataFrame contains town_id 3 with avg_price_per_sqm -10.0
    When the DataFrame is validated in FILTER mode
    Then the returned DataFrame contains only town_id 1
    And the validation report has pass_count 1
    And the validation report has fail_count 1

  Scenario: Null entity key is rejected in every mode
    Given "town_market_features" has entity key "town_id"
    And a DataFrame contains a null town_id and event_timestamp 2024-02-01T00:00:00Z
    When the DataFrame is validated in NONE mode
    Then ValidationError is raised
    And the error report contains a failure for field "town_id"
