Feature: Feature 15 — Remote S3 offline store ingestion and historical retrieval

  Scenario: Remote ingest writes partitioned S3 Parquet
    Given runtime.target resolves to "remote"
    And the remote registry contains "town_market_features"
    And the remote offline store is configured at "s3://company-ml/kitefs"
    And the input DataFrame contains 6 valid rows with event_timestamp 2024-02-01T00:00:00Z
    When the user calls store.ingest("town_market_features", df)
    Then no exception is raised
    And result.accepted_rows is 6
    And result.written_files contains exactly 1 S3 URI
    And the S3 URI starts with "s3://company-ml/kitefs/data/offline_store/town_market_features/year=2024/month=02/"

  Scenario: Remote historical retrieval returns the same columns as local retrieval
    Given equivalent local and remote offline data exists for "listing_features"
    When the user retrieves "net_area" and "sold_price" from "listing_features" using the remote runtime
    Then no exception is raised
    And the returned columns match the local result columns

  Scenario: Remote joined historical retrieval preserves point-in-time behavior
    Given equivalent local and remote offline data exists for "listing_features" and "town_market_features"
    When the user retrieves "listing_features" joined to "town_market_features" using the remote runtime
    Then no exception is raised
    And listing_id 1002 has town_market_features_event_timestamp 2024-04-01T00:00:00Z
    And listing_id 1002 has town_market_features_avg_price_per_sqm 25400.0

  Scenario: Remote retrieval returns an empty DataFrame when no S3 objects exist
    Given runtime.target resolves to "remote"
    And "listing_features" is registered
    And no S3 objects exist under the offline prefix for "listing_features"
    When the user retrieves "net_area" and "sold_price" from "listing_features"
    Then no exception is raised
    And the result has zero rows

  Scenario: Missing remote offline configuration fails clearly
    Given runtime.target resolves to "remote"
    And remote.offline_store.bucket is empty
    When the user calls store.ingest("town_market_features", df)
    Then ConfigurationError is raised
    And the error message contains "remote offline"
    And the error message contains "bucket"
