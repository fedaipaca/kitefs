Feature: Local offline store ingestion

  Scenario: Ingest a month of town market rows
    Given "town_market_features" is registered
    And the input DataFrame contains 6 valid rows with event_timestamp 2024-02-01T00:00:00Z
    When the user calls store.ingest("town_market_features", df)
    Then no exception is raised
    And result.feature_group is "town_market_features"
    And result.accepted_rows is 6
    And result.rejected_rows is 0
    And result.written_files contains exactly 1 path
    And the written file is under "feature_store/data/offline_store/town_market_features/year=2024/month=02/"

  Scenario: Ingest accepts a CSV file path
    Given "town_market_features" is registered
    And "data/town_market_2024_02.csv" contains 6 valid town market rows
    When the user calls store.ingest("town_market_features", "data/town_market_2024_02.csv")
    Then no exception is raised
    And result.accepted_rows is 6
    And result.written_files contains exactly 1 path

  Scenario: Ingest rejects an unknown feature group
    Given the registry contains only "town_market_features"
    And the input DataFrame contains valid town market rows
    When the user calls store.ingest("neighborhood_features", df)
    Then FeatureGroupNotFoundError is raised
    And the error message contains "neighborhood_features"
    And no offline file is written

  Scenario: Ingest rejects an unsupported file extension
    Given "town_market_features" is registered
    When the user calls store.ingest("town_market_features", "data/town_market.xlsx")
    Then IngestionShapeError is raised
    And the error message contains ".csv"
    And the error message contains ".parquet"
    And no offline file is written

  Scenario: Missing required column raises a shape error
    Given "town_market_features" is registered
    And the input DataFrame contains "town_id" and "event_timestamp" but not "avg_price_per_sqm"
    When the user calls store.ingest("town_market_features", df)
    Then IngestionShapeError is raised
    And the error message contains "avg_price_per_sqm"
    And no offline file is written

  Scenario: FILTER mode with no accepted rows writes nothing
    Given "town_market_features" is registered with ingestion_validation FILTER
    And the input DataFrame contains 2 rows whose avg_price_per_sqm values are -10.0 and -20.0
    When the user calls store.ingest("town_market_features", df)
    Then no exception is raised
    And result.accepted_rows is 0
    And result.rejected_rows is 2
    And result.written_files is empty
