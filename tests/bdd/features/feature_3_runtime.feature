Feature: Configuration runtime and local provider boundary

  Scenario: Construct FeatureStore in an initialized local project
    Given an initialized local project for the reference use case
    When the user creates FeatureStore()
    Then no exception is raised
    And the active runtime target is "local"

  Scenario: Missing kitefs.yaml fails clearly
    Given no "kitefs.yaml" exists in the current directory
    When the user creates FeatureStore()
    Then ConfigurationError is raised
    And the error message contains "kitefs.yaml"
    And the error message contains "kitefs init"

  Scenario: Unsupported runtime target fails clearly
    Given "kitefs.yaml" has runtime.target "staging"
    When the user creates FeatureStore()
    Then ConfigurationError is raised
    And the error message contains "staging"
    And the error message contains "local"
    And the error message contains "remote"

  Scenario: KITEFS_RUNTIME_TARGET overrides the resolved file value
    Given "kitefs.yaml" has runtime.target "local"
    And the environment variable KITEFS_RUNTIME_TARGET is "remote"
    And a valid remote section is configured
    When the user creates FeatureStore()
    Then no exception is raised
    And the active runtime target is "remote"
