Feature: Feature group definition types and construction-time validation

  Scenario: Construct the reference listing feature group
    Given the "listing_features" definition from the reference use case
    When the user constructs the FeatureGroup
    Then no exception is raised
    And the FeatureGroup name is "listing_features"

  Scenario: Reject an invalid entity key dtype
    Given an EntityKey named "listing_id" with dtype FLOAT
    When the user constructs the EntityKey
    Then DefinitionError is raised
    And the error message contains "listing_id"
    And the error message contains "STRING or INTEGER"

  Scenario: Reject an invalid expectation threshold
    Given a new Expect object
    When the user declares gt "zero"
    Then DefinitionError is raised
    And the error message contains "gt"
    And the error message contains "int, float, or datetime"

  Scenario: Reject metadata without an owner
    Given Metadata with description "Monthly town-level market aggregate" and an empty owner
    When the user constructs the Metadata
    Then DefinitionError is raised
    And the error message contains "owner"

  Scenario: Reject a feature group with an invalid name
    Given a FeatureGroup named "123-invalid"
    When the user constructs the FeatureGroup
    Then DefinitionError is raised
    And the error message contains "123-invalid"
    And the error message contains "identifier"

  Scenario: Reject duplicate field names within a feature group
    Given a FeatureGroup named "listing_features" whose entity key and feature are both named "listing_id"
    When the user constructs the FeatureGroup
    Then DefinitionError is raised
    And the error message contains "listing_id"
    And the error message contains "duplicate"

  Scenario: Import public definition names from the top-level package
    Given the user imports FeatureGroup, Feature, EntityKey, EventTimestamp, FeatureType, StorageTarget, Expect, JoinKey, ValidationMode, Metadata, and DefinitionError from kitefs
    When the imports complete
    Then no exception is raised
