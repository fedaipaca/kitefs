# Feature 1: Foundation, definition types and errors

## Goal

Let users write feature group definitions as Python code and get immediate feedback when a definition is structurally wrong, before any storage or runtime is involved.

## Description

The public definition types (`FeatureGroup`, `EntityKey`, `EventTimestamp`, `Feature`, `JoinKey`, `Metadata`, `Expect`), the supporting enums, and the full exception hierarchy. Construction-time checks reject invalid definitions at authoring time, in the editor or REPL.

## Scope

- IN: Enums (`FeatureType`, `StorageTarget`, `ValidationMode`), all public exception classes, definition types with construction-time checks, top-level `kitefs` re-exports, `kitefs.__version__` string.
- NOT IN: Cross-group validation (runs in `apply`), discovery from disk, config, providers, CLI, storage.

## Expected output

A user can `from kitefs import FeatureGroup, Feature, EntityKey, EventTimestamp, FeatureType, StorageTarget, Expect, ...` and construct the `listing_features` and `town_market_features` groups from `specs/01-reference-use-case.md`. Any invalid definition raises `DefinitionError` immediately at construction.

## Implements

`FeatureType`, `StorageTarget`, `ValidationMode`, `Expect`, `EntityKey`, `EventTimestamp`, `Feature`, `JoinKey`, `Metadata`, `FeatureGroup`, full `KiteFSError` exception hierarchy as declared in `contracts.py`, `kitefs.__version__`.

## Dependencies

None.

## Behavior

1. Define `KiteFSError` and every subclass listed in `contracts.py`; all definition-time failures raise `DefinitionError`.
2. `Expect()` starts with an empty constraint list. Each operator method (`not_null`, `gt`, `gte`, `lt`, `lte`, `is_in`) appends a constraint record and returns `self`.
3. Reject non-numeric arguments for `gt`, `gte`, `lt`, `lte` that are not `int`, `float`, or `datetime.datetime`; reject empty lists for `is_in`.
4. `EntityKey.__init__` accepts only `STRING` or `INTEGER` for `dtype`.
5. `EventTimestamp.__init__` accepts only `DATETIME` for `dtype` (default is `DATETIME`).
6. `JoinKey.__init__` accepts only `STRING` or `INTEGER` for `dtype`.
7. `Feature.__init__` accepts `STRING`, `INTEGER`, `FLOAT`, or `DATETIME`.
8. `Metadata.__init__` requires non-empty `description` and `owner`; `tags` defaults to `{}`.
9. `FeatureGroup.__init__` validates: `name` matches `^[a-zA-Z_][a-zA-Z0-9_]*$` (CON-009); `features` is non-empty; `join_keys` is `None`, empty, or single-element; every field name (entity key, event timestamp, join key, features) is unique within the group; every field name matches CON-009.
10. Export all public names listed in `contracts.py` from the top-level `kitefs` package.
11. Expose `kitefs.__version__` as a string from the top-level package, reading the version from package metadata. The MVP ships as `0.x.y` following Semantic Versioning.

## Error Handling

| Error             | When                                                                  | Behavior                                                      |
| ----------------- | --------------------------------------------------------------------- | ------------------------------------------------------------- |
| `DefinitionError` | Invalid dtype for `EntityKey`, `JoinKey`, `EventTimestamp`, `Feature` | Raise at construction; message names field and allowed dtypes |
| `DefinitionError` | Empty `features`, duplicate field names, identifier regex violation   | Raise at `FeatureGroup` construction                          |
| `DefinitionError` | More than one `join_keys` entry                                       | Raise at `FeatureGroup` construction                          |
| `DefinitionError` | Empty `Metadata.description` or `Metadata.owner`                      | Raise at `Metadata` construction                              |
| `DefinitionError` | Non-numeric argument to numeric `Expect` operator; empty `is_in` list | Raise at `Expect` operator call                               |

## Example

Input:

```python
EntityKey(name="listing_id", dtype=FeatureType.FLOAT)
```

Output: `DefinitionError("EntityKey 'listing_id' dtype must be STRING or INTEGER, got FLOAT")`.

Input: the full `listing_features` `FeatureGroup` from `specs/01-reference-use-case.md`.
Output: a valid `FeatureGroup` object whose `name` is `"listing_features"`.

## BDD Scenarios

```gherkin
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
```
