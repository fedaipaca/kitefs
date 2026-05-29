Feature: Project scaffold and local configuration

  Scenario: kitefs init creates a usable producer project scaffold
    Given an empty working directory
    When the user runs "kitefs init"
    Then the command exits 0
    And "kitefs.yaml" exists
    And "feature_store/definitions/" exists
    And "feature_store/data/offline_store/" exists
    And "feature_store/data/online_store/" exists
    And "feature_store/registry.json" contains an empty registry
    And ".gitignore" contains entries for KiteFS data and registry files

  Scenario: kitefs init creates an example feature definition
    Given an empty working directory
    When the user runs "kitefs init"
    Then "feature_store/definitions/" contains a Python feature definition file
    And the example definition file contains "FeatureGroup"

  Scenario: kitefs init refuses to overwrite an existing project
    Given "kitefs.yaml" already exists with content "project: existing"
    When the user runs "kitefs init"
    Then the command exits non-zero
    And stderr contains "kitefs.yaml"
    And stderr contains "already"
    And "kitefs.yaml" still contains "project: existing"

  Scenario: kitefs init-config creates consumer configuration only
    Given an empty working directory
    When the user runs "kitefs init-config"
    Then the command exits 0
    And "kitefs.yaml" exists
    And "feature_store/" does not exist

  Scenario: kitefs init-config refuses to overwrite an existing project
    Given "kitefs.yaml" already exists with content "project: existing"
    When the user runs "kitefs init-config"
    Then the command exits non-zero
    And stderr contains "kitefs.yaml"
    And stderr contains "already"
    And "kitefs.yaml" still contains "project: existing"
