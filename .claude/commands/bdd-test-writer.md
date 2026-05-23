---
description: "Write runnable pytest-bdd tests from a BDD task ID or full BDD task content. Use when implementing feature files, scenarios, and step definitions under tests/bdd."
argument-hint: "BDD-012 | <paste full BDD task spec>"
---

# BDD Test Writer

Write complete, runnable BDD tests for exactly one BDD task.

## Input

`$ARGUMENTS` is either:

- a BDD task ID, e.g. `BDD-012`
- the full BDD task content

If only an ID is provided:

1. Resolve the exact task text from the current chat context or workspace artifacts.
2. Include matching entries from `docs/07-implementation-plan.md` when relevant.
3. If the task cannot be resolved exactly, stop and ask for the full task content.

## Scope

Create or update only BDD test assets under `tests/bdd`, such as:

- `tests/bdd/features/*.feature`
- `tests/bdd/steps/*.py`
- BDD-specific fixtures or support code, only when existing helpers are insufficient

Do not modify application code.

## Workflow

1. Resolve the BDD task.
2. Read only the docs, existing BDD tests, fixtures, helpers, and code needed to author the tests.
3. Verify the task defines observable behavior clearly enough to test.
4. Write feature scenarios and step definitions.
5. Run the narrowest relevant BDD validation command.
6. If tests fail and tests correctly match the task and docs; then stop and report the failure.

## Stop Conditions

Stop instead of guessing when required details are missing, ambiguous, or conflicting.

Stop-worthy gaps include:

- unclear observable behavior
- task/docs/code conflict
- unspecified expected error type or message
- missing setup data or fixture shape
- unresolved BDD task ID

When stopping, report:

- the blocking issue
- why it prevents reliable BDD tests
- the exact question the user must answer

## Authoring Rules

- Use `pytest` and `pytest-bdd`.
- Keep scenarios user-visible and behavior-focused.
- Cover only the task’s documented behavior:
  - happy paths
  - documented error paths
  - documented boundary cases
- Do not add speculative scenarios.
- Use concrete example data.
- Prefer existing fixtures and helpers before adding new support code.
- Keep step definitions deterministic, minimal, and readable.
- Use strong assertions; do not weaken tests to match current implementation.
- Do not write or modify application code.

## Validation Rules

If new tests fail but match the task and docs:

- do not edit the tests to force a pass
- do not implement product behavior
- report the failure clearly, and stop for user input.

Include:

- command run
- failing feature/scenario
- key failure output or mismatch
- classification: task ambiguity, documentation gap, or implementation gap

## Output

On success, report briefly:

- files created or changed
- validation command run
- whether the BDD tests are ready to run

---

**BDD Task:** $ARGUMENTS
