Feature: Remote configuration and AWS provider

  Scenario: Remote runtime constructs with valid registry configuration
    Given runtime.target resolves to "remote"
    And remote.region is "eu-central-1"
    And remote.registry.type is "aws_s3"
    And remote.registry.bucket is "company-ml"
    And remote.registry.s3_prefix is "kitefs"
    When the user creates FeatureStore()
    Then no exception is raised
    And the active runtime target is "remote"
    And the active provider is the AWS provider

  Scenario: Remote target without a remote section fails clearly
    Given runtime.target is "remote"
    And "kitefs.yaml" has no remote section
    When the user creates FeatureStore()
    Then ConfigurationError is raised
    And the error message contains "remote"

  Scenario: Missing remote offline configuration does not block online retrieval
    Given runtime.target is "remote"
    And the remote registry contains "town_market_features"
    And remote.online_store.type is "aws_dynamodb"
    And remote.online_store.dynamodb_table_prefix is "kitefs_"
    And remote.offline_store is absent
    When the user calls get_online_features for "town_market_features" where town_id equals 1
    Then no ConfigurationError about offline storage is raised

  Scenario: Missing needed remote offline configuration fails before ingestion
    Given runtime.target is "remote"
    And remote.offline_store is absent
    When the user calls store.ingest("town_market_features", df)
    Then ConfigurationError is raised
    And the error message contains "remote offline"

  Scenario: Interpolated remote type field is rejected
    Given runtime.target is "remote"
    And remote.registry.type is "${KITEFS_REMOTE_REGISTRY_TYPE:-aws_s3}"
    When the user creates FeatureStore()
    Then ConfigurationError is raised
    And the error message contains "remote.registry.type"
    And the error message contains "literal"

  Scenario: Missing boto3 extra fails with installation guidance
    Given runtime.target is "remote"
    And the AWS extra is not installed
    When the user creates FeatureStore()
    Then ProviderError is raised
    And the error message contains "boto3"
    And the error message contains "kitefs[aws]"
