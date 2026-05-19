---
description: "Write runnable pytest-bdd tests from a BDD task ID or full BDD task content. Use when implementing feature files, scenarios, and step definitions under tests/bdd."
name: "BDD Test Writer"
argument-hint: "BDD-012 | <paste full BDD task spec>"
---

# BDD Test Writer

Write the BDD tests for a single BDD task. This prompt consumes a finished BDD task spec, such as the output of [bdd-task.prompt.md](./bdd-task.prompt.md), and turns it into runnable `pytest` + `pytest-bdd` coverage.

Assume the general repository guardrails in [copilot-instructions.md](../copilot-instructions.md) are already active. This prompt adds only task-specific rules for authoring BDD tests.

## Input

`$ARGUMENTS` is either:

- a BDD task ID such as `BDD-012`
- the full BDD task content

If the input is only an ID, first resolve the exact task text from the current chat context or workspace artifacts, including `docs/07-implementation-plan.md` entries with the same ID or test name.
If you cannot resolve it exactly, stop and ask for the full task content.

## Scope

Produce complete, ready-to-run BDD tests under `tests/bdd`, including any necessary:

- feature files in `tests/bdd/features/`
- step definition files in `tests/bdd/steps/`
- BDD-specific fixtures or support code, only when existing ones are insufficient

## Workflow

1. Resolve the BDD task and read only the files needed to implement it.
2. Inspect existing related BDD tests, shared fixtures, and relevant docs for the covered behavior.
3. Confirm the task has enough detail to write unambiguous tests.
4. Write the tests.
5. Run the narrowest relevant BDD command.
6. If tests fail but correctly match the task and docs, stop and report per Validation Rules.

## Stop Conditions

Stop immediately when any required detail is missing, ambiguous, or conflicting. Do not guess. Report the issue so the user can answer it.

Examples of stop-worthy gaps:

- the task does not define the observable behavior precisely enough
- the docs and the task disagree on inputs, outputs, or errors
- an expected error type or message is not clear enough to assert
- required setup data or fixture shape is missing

When stopping, provide:

- the blocking issue
- why it prevents writing reliable BDD tests
- the exact question or missing detail the user should answer

## Authoring Rules

- Use `pytest` and `pytest-bdd` only.
- Keep scenarios user-visible and behavior-focused.
- Write clear feature titles, scenario names, and step text.
- Cover the behavior in the task completely: happy path, documented error paths, and documented boundary cases.
- Do not add speculative scenarios or undocumented behavior.
- Prefer concrete example data over placeholders.
- Keep step definitions readable, deterministic, and minimal.
- Keep assertions strong. Do not weaken expectations to fit current code.
- Reuse existing fixtures and helpers for shared setup instead of duplicating code across steps.
- Do not write or modify application code.

## Validation Rules

If the new tests fail and you are sure the test is correct:

- stop immediately
- do not edit the new tests to make them pass
- do not start implementing the product behavior
- report the failure clearly

Your failure report must include:

- the command you ran
- which feature or scenario failed
- the key failure output or mismatch
- whether the failure looks like a task ambiguity, documentation gap, or implementation gap

## Output

If successful, briefly report:

- which files you created or changed
- which validation command you ran
- that the BDD tests are ready to run

---

**BDD Task:** $ARGUMENTS
