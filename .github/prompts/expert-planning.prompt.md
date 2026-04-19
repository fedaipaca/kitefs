---
description: "Create an implementation plan for a KiteFS task. Use before starting any multi-step implementation work."
agent: Plan
argument-hint: "Paste the task description or requirement to plan for..."
tools: ["search", "read", "web/fetch"]
model: Claude Opus 4.6 (copilot)
---

Create a detailed **implementation plan** for the task described below.

Before planning:

1. Follow the project instructions (`.github/copilot-instructions.md` and any applicable `.github/instructions/*.instructions.md` files).
2. Read the `docs/` files relevant to the task. Follow traces to related requirements, decisions, or building blocks as needed for full context.
3. Read the existing source code and tests that will be affected.

Follow the **Source Precedence** rules from `copilot-instructions.md`:

- For existing implemented modules, treat current code and tests as the source of truth for behavior. Docs provide design intent.
- For new modules, use docs as the design guide but keep assumptions explicit.
- If docs conflict with each other or with existing code, identify the conflict in the plan -with proper recommendations taking into account your expertise and project goals- rather than silently choosing one side.

The plan must include:

1. **Summary** — one paragraph describing the task and its outcome.
2. **Relevant files** — list every file to create, modify, or delete, grouped by category (source, tests, config).
3. **Step-by-step implementation** — ordered steps, each describing what to do and why. Group into logical phases if the task is large.
4. **-if needed- Assumptions** — any design decisions not explicitly specified, with rationale.
5. **-if needed- Conflicts or open questions** — any mismatches found between docs, existing code, or the task description. For each, state what the conflict is and recommend a resolution.
6. **Verification** — how to confirm the implementation is correct (specific test commands, checks, expected outcomes).
7. **Branch name** — suggest a branch name following `feat/task-{n}/{short-description}`. If branch is already created skip branch creation. This information can be provided by user, or can be understand before implementation by checking the current branch.
8. **just commands** - mention related just commands to run, and explicitly mention `just clean build` should pass.

Do **not** implement anything — only produce the plan.

{{input}}
