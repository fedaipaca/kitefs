---
description: "Evaluate completed tasks and produce BDD scenario specs for user-visible behavior."
argument-hint: "T-019, T-020, T-021 are done"
---

# Purpose

Decide whether completed tasks introduce user-visible behavior that needs BDD coverage. If so, produce a complete scenario specification ready for the BDD Test Writer prompt.

Treat KiteFS as a **product** — its user-facing operations, contracts, and guarantees — not its code.

---

# Product Knowledge Sources

A single behavior may span requirements, flows, API signatures, and storage contracts. Cross-reference these to build a holistic picture:

| Purpose                              | Doc                                                                |
| ------------------------------------ | ------------------------------------------------------------------ |
| Scope and goals                      | `docs/00-project-context.md`                                       |
| Concrete usage scenario              | `docs/01-reference-use-case.md`                                    |
| Requirements and acceptance criteria | `docs/02-product-requirements.md`                                  |
| Operation flows                      | `docs/03-system-behavior.md`                                       |
| Storage formats (when relevant)      | `docs/05-data-and-storage-contracts.md`                            |
| SDK signatures, CLI, errors          | `docs/06-api-and-cli-contracts.md`                                 |
| Task scope, status, dependencies     | `docs/07-implementation-plan/phase-N.md` (the relevant phase file) |

Every scenario must be consistent with **all** relevant docs. For example: A scenario about `apply` must align with its requirement in `02`, its flow in `03`, and its signature in `06`.

---

# Workflow

1. **Read task definitions** from the relevant `docs/07-implementation-plan/phase-N.md` file. A task counts as done when its status is `done`.
2. **Read relevant docs** for the behaviors those tasks touch.
3. **Identify user-visible behavior** introduced by the done tasks — new/changed SDK methods, CLI commands, error conditions, or observable output formats.
4. **Apply the Decision Gate** below. If no BDD is needed, report why and stop.
5. **Verify contracts are fully documented.** For each behavior, confirm:
   - The requirement exists in `02-product-requirements.md`.
   - The SDK or CLI signature exists in `06-api-and-cli-contracts.md` (parameters, types, return type).
   - Every error condition has a named exception and a described trigger.
   - The flow in `03-system-behavior.md` covers preconditions, steps, success outcome, and failure outcomes.
   - If anything is missing or ambiguous: **stop**, name the gap, cite the doc section that should contain it, and explain why the spec cannot be written.
6. **Produce the BDD Task Specification.** Ensure every scenario aligns with requirements, behavior specs, and API contracts collectively.

---

# Decision Gate

**BDD is needed** when done tasks introduce or change:

- A public SDK method (`FeatureStore.*`, public module functions).
- A CLI command (`kitefs <command>`).
- User-facing error messages or error conditions.
- Observable output format (return types, printed output, file artifacts users interact with).

**BDD is NOT needed** when done tasks are purely internal:

- Shared enums or error class hierarchy (types only, no behavior).
- Abstract base classes or provider interfaces (no user interaction yet).
- Internal wiring with no public surface.
- Configuration schema parsing not yet exposed via SDK/CLI.
- Storage implementation details behind a provider interface.

When BDD is not needed, respond: `No BDD coverage needed for these tasks.` followed by a one-paragraph rationale.

---

# Output Format

When BDD is needed:

```
## BDD-NNN — <Feature Title>

**Covers tasks:** T-XXX, T-YYY
**Feature file:** `tests/bdd/features/<capability_name>.feature`
**Tags:** @tag1 @tag2

### Feature Description

As a <role>, I want <capability>, so that <benefit>.

### Scenarios

#### Scenario: <Verb phrase describing what the user does>

- **Given** <precondition with concrete values>
- **And** <additional precondition, if needed>
- **When** <user action through SDK or CLI>
- **Then** <observable outcome>
- **And** <additional assertion, if needed>

Doc reference: REQ-ID

#### Scenario Outline: <Name>

Use when the same behavior applies to multiple inputs. Each row in `Examples` runs the scenario once with values substituted into `<param>` placeholders.

- **Given** <precondition with `<param>`>
- **When** <action with `<param>`>
- **Then** <outcome with `<expected>`>

Examples:

| param   | expected |
| ------- | -------- |
| value1  | result1  |
| value2  | result2  |

Doc reference: REQ-ID

### Doc References

- REQ-ID — one-line summary.
```

---

# Scenario Rules

- **One behavior per scenario.** Never combine assertions about different behaviors.
- **Concrete values.** Use realistic example data (e.g., `Given a feature group named "user_transactions"`), no vague placeholders.
- **No implementation detail.** Steps describe what the user does and observes, not internal mechanics.
- **Error scenarios include the message.** `Then` steps specify the expected error type AND key message content.
- **Complete coverage.** For each user-visible behavior: happy path, each documented error condition, and documented boundary cases.
- **Scope-bound.** Only cover behaviors introduced by the listed done tasks. Do not speculatively cover future tasks.
- **Traceable.** Every scenario maps to a documented behavior. Do not invent behaviors.
- **Unambiguous.** Every scenario has exactly one interpretation. If a behavior is ambiguous in docs, flag it instead of guessing.
- **Implementable.** Steps must be achievable through the public API or documented setup — no internal state mocking.
- **Self-contained.** The spec must be complete enough for a coding agent to implement step definitions without follow-up questions.

---

**Input:** $ARGUMENTS
