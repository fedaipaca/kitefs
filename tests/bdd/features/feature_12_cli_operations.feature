Feature: CLI wrappers for SDK operations

  Scenario: Apply through CLI succeeds
    Given "listing_features.py" and "town_market_features.py" exist in "feature_store/definitions/"
    When the user runs "kitefs apply"
    Then the command exits 0
    And stdout contains "listing_features"
    And stdout contains "town_market_features"

  Scenario: CLI apply expected errors are printed without traceback
    Given "feature_store/definitions/" contains no FeatureGroup definitions
    When the user runs "kitefs apply"
    Then the command exits 1
    And stderr contains "Error:"
    And stderr contains "FeatureGroup"
    And stderr does not contain "Traceback"

  Scenario: CLI ingest succeeds for a CSV file
    Given "town_market_features" is registered
    And "data/town_market_2024_02.csv" contains 6 valid town market rows
    When the user runs "kitefs ingest town_market_features data/town_market_2024_02.csv"
    Then the command exits 0
    And stdout contains "Ingested 6 row"
    And stdout contains "town_market_features"

  Scenario: CLI ingest rejects unsupported file extension
    Given a valid local project
    When the user runs "kitefs ingest town_market_features data/town_market.xlsx"
    Then the command exits 1
    And stderr contains ".csv"
    And stderr contains ".parquet"

  Scenario: CLI materialize named group succeeds
    Given "town_market_features" has offline rows
    When the user runs "kitefs materialize town_market_features"
    Then the command exits 0
    And stdout contains "Succeeded"
    And stdout contains "town_market_features"

  Scenario: Publish aborts when confirmation is not yes
    Given a valid local project
    When the user runs "kitefs apply --publish" and types "no"
    Then the command exits non-zero
    And stderr contains "aborted"
