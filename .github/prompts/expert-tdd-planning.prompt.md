---
description: "Plan test cases for a KiteFS task using TDD. Use before implementing code — tests define the acceptance criteria."
agent: Plan
argument-hint: "Paste the task description or requirement to plan tests for..."
tools: ["search", "read", "web/fetch"]
model: Claude Opus 4.6 (copilot)
---

Create a detailed **test plan** for the task described below. The goal is to define tests that serve as executable specifications — implementation comes later.

Before planning tests:

1. Follow the project instructions (`.github/copilot-instructions.md` and any applicable `.github/instructions/*.instructions.md` files).
2. Read the `docs/` files relevant to the task. Follow traces to related requirements, decisions, or building blocks as needed for full context.
3. Read existing test files (`tests/`) to understand conventions: naming patterns, fixture usage, helpers in `tests/helpers.py` and `tests/conftest.py`.
4. Read the existing source code that the tests will exercise — understand current interfaces, types, imports, and public API surface.

Follow the **Source Precedence** rules and all **testing conventions** from `copilot-instructions.md`.

Constraints — you must follow these:

- Do **not** plan any implementation — only tests.
- Tests target the **expected public API** (from docs and task description), not implementation internals.
- Do not duplicate tests that already exist — check existing test files first.

The test plan must include:

1. **Summary** — one paragraph describing what behavior these tests specify.
2. **Test file(s)** — which test files to create or modify, with full paths.
3. **Fixtures needed** — new fixtures to create or existing ones to reuse (from `conftest.py` / `helpers.py`), with brief descriptions of each.
4. **Test cases — success paths** — ordered list of test functions:
   - Function name (`test_<function>_<scenario>_<expected>`)
   - Scenario description (one sentence)
   - Key assertions
   - Which requirement or behavior it validates
5. **Test cases — error paths** — same format, plus:
   - Exception type expected
   - Message pattern to match
6. **Edge cases** — boundary conditions worth testing, if any.
7. **Verification** — the exact pytest command to run only these tests (e.g., `just test` or `uv run pytest tests/test_foo.py -v`).

Do **not** implement anything — only produce the test plan.

{{input}}
