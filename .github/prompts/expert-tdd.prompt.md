---
description: "Create a TDD plan for a KiteFS task — tests first, then implementation. Use for complex tasks where test-driven development catches design issues early."
agent: Plan
argument-hint: "Paste the task description or requirement to plan for..."
tools: ["search", "read", "web/fetch"]
---

Create a detailed **TDD plan** for the task described below. The plan follows test-driven development: define tests first as executable specifications, then plan the implementation to satisfy them.

Before planning:

1. Follow the project instructions (`.github/copilot-instructions.md` and any applicable `.github/instructions/*.instructions.md` files).
2. Read the `docs/` files relevant to the task. Follow traces to related requirements, decisions, or building blocks as needed for full context.
3. Read existing test files (`tests/`) to understand conventions: naming patterns, fixture usage, helpers in `tests/helpers.py` and `tests/conftest.py`.
4. Read the existing source code — understand current interfaces, types, imports, and public API surface.

Follow the **Source Precedence** rules and all **code style and testing conventions** from `copilot-instructions.md`.

Constraints — you must follow these:

- Tests target the **expected public API** (from docs and task description), not implementation internals.
- Do not duplicate tests that already exist — check existing test files first.
- If a task requirement is not covered by the tests planned in Phase 1 (tests), add it in Phase 2 (implementation) as gap coverage.

The plan must include:

1. **Summary** — one paragraph describing the task, its outcome, and the TDD approach.

2. **Relevant files** — every file to create or modify, grouped by category (source, tests, config).

3. **Phase 1 — Tests** — define the test cases first. These become the acceptance criteria for Phase 2.
   - **Test file(s)** — which test files to create or modify, with full paths.
   - **Fixtures needed** — new fixtures to create or existing ones to reuse (from `conftest.py` / `helpers.py`), with brief descriptions.
   - **Test cases — success paths** — ordered list of test functions:
     - Function name (`test_<function>_<scenario>_<expected>`)
     - Scenario description (one sentence)
     - Key assertions
     - Which requirement or behavior it validates
   - **Test cases — error paths** — same format, plus:
     - Exception type expected
     - Message pattern to match
   - **Edge cases** — boundary conditions worth testing, if any.

4. **Phase 2 — Implementation** — plan the code to pass all Phase 1 tests, then check for gaps.
   - **Phase 2a — Pass the tests**: step-by-step implementation, each describing what to do and why. For each step, reference which test(s) it satisfies.
   - **Phase 2b — Gap coverage**: cross-check the task description and docs against Phase 1 tests. If any requirement is NOT covered, specify the additional test(s) and implementation needed.

5. **Phase 3 — Verification**
   - The exact pytest command to run the tests (e.g., `just test` or `uv run pytest tests/test_foo.py -v`).
   - Explicitly state `just clean build` must pass.

6. **-if needed- Design decisions** — architectural choices informed by docs that affect the approach.
7. **-if needed- Assumptions** — any decisions not explicitly specified, with rationale.
8. **-if needed- Conflicts or open questions** — mismatches between docs, existing code, or the task description. For each, state the conflict and recommend a resolution.
9. **Branch name** — suggest a branch name following `feat/task-{n}/{short-description}`. If branch is already created skip branch creation. This information can be provided by user, or can be understood before implementation by checking the current branch.

Do **not** implement anything — only produce the plan.

{{input}}
