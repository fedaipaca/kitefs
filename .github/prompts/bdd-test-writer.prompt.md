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

If the input is only an ID, first resolve the exact task text from the current chat context or workspace artifacts.
Tasks can be found in `docs/07-implementation-plan.md` with the same id or test name.
If you cannot resolve it exactly, stop and ask for the full task content.

## Scope

Produce complete, ready-to-run BDD tests under `tests/bdd`, including any necessary:

- feature files in `tests/bdd/features/`
- step definition files in `tests/bdd/steps/`
- BDD-specific fixtures or support code only when required

Reuse existing BDD fixtures, helpers, and patterns before adding new ones.

## Workflow

1. Resolve the BDD task and read only the files needed to implement it.
2. Inspect nearby BDD tests, shared fixtures, and relevant docs for the covered behavior.
3. Validate that the task is implementable as written.
4. If it is clear, write the tests.
5. Run the narrowest relevant BDD validation.
6. If validation fails, and If you are sure the test you wrote is correct and aligning with the BDD task, then stop and report the failure. Do not change the tests. Do not change production code.

## Stop Conditions

Stop immediately when any required detail is missing, ambiguous, or conflicting. Do not guess. Report the issue so the user can answer it.

Examples of stop-worthy gaps:

- the BDD task ID cannot be resolved to full task text
- the task does not define the observable behavior precisely enough
- the docs and the task disagree on inputs, outputs, or errors
- an expected error type or message is not specified clearly enough to assert
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
- Reuse fixtures for shared setup instead of copying large setup blocks across steps.
- Keep assertions strong. Do not weaken expectations to fit current code.
- Do not write or modify application code. This prompt is for BDD test authoring only.

## Validation Rules

After writing the tests, run the narrowest relevant BDD command first.

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

If blocked or failing, do not continue past the stop condition.

---

**BDD Task:** $ARGUMENTS
