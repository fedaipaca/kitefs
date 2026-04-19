---
description: "Plan code implementation to pass existing tests. Use after tests are written and reviewed — the tests define what to build."
agent: Plan
argument-hint: "Point to the test file(s) or paste the task description..."
tools: ["search", "read", "web/fetch"]
model: Claude Opus 4.6 (copilot)
---

Create a detailed **implementation plan** for the task described below. The plan has two phases: first pass all existing tests, then ensure the full task is satisfied.

Before planning:

1. Follow the project instructions (`.github/copilot-instructions.md` and any applicable `.github/instructions/*.instructions.md` files).
2. Read the **test file(s)** for this task — these are the primary acceptance criteria. Understand every test function, what it asserts, and what public API surface it expects.
3. Read the existing source code that will be modified or extended.
4. Read the **task description and docs** (requirements, traces, decision records) to understand the full scope — tests may not cover everything.

Follow the **Source Precedence** rules and all **code style and testing conventions** from `copilot-instructions.md`.

Constraints — you must follow these:

- Do **not** modify existing tests — implement code to pass them as-is.
- If a test appears incorrect or inconsistent with docs, **flag it explicitly** with your recommendation, but do not plan to change it. The user decides.
- After satisfying existing tests, cross-check the task description and docs for requirements the tests may have missed. Plan additional tests and implementation for any gaps found.

The implementation plan must include:

1. **Summary** — one paragraph: what to implement, covering both test satisfaction and full task completion.
2. **Test inventory** — list the existing test functions being targeted (read from the test files), grouped by category (success paths, error paths, edge cases).
3. **Relevant files** — every file to create or modify, grouped by category (source, tests, config).
4. **Step-by-step implementation** — ordered steps, each describing what to do and why. For each step, reference which test(s) it satisfies. Split into:
   - **Phase A — Pass existing tests**: implement code to make all existing tests pass.
   - **Phase B — Gap coverage**: any task requirements not covered by existing tests. For each gap, specify the additional test(s) to create and the implementation needed.
5. **-if needed- Design decisions** — architectural choices informed by docs (KTD-*, building blocks, patterns) that affect the implementation approach.
6. **-if needed- Assumptions** — any design decisions not explicitly covered by tests or docs, with rationale.
7. **-if needed- Conflicts or open questions** — mismatches between tests, docs, or existing code. For each, state the conflict and recommend a resolution.
8. **Verification** — `just test` or specific pytest command to confirm all tests pass, plus `just clean build` must pass.

Do **not** implement anything — only produce the plan.

{{input}}
