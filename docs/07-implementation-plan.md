# Implementation Plan

## Purpose

This file defines implementation sequencing for the KiteFS feature store library. It owns task planning and delivery boundaries only.

## Owns

- Phases.
- Tasks.
- Branch names.
- Task status: done or not started.
- Task scope and boundaries.
- Dependencies between tasks.
- What each task delivers.

## Does Not Own

- Project context. See [00-project-context.md](00-project-context.md).
- Reference use case. See [01-reference-use-case.md](01-reference-use-case.md).
- Requirements definitions. See [02-product-requirements.md](02-product-requirements.md).
- Behavior specifications. See [03-system-behavior.md](03-system-behavior.md).
- Architectural design. See [04-architecture.md](04-architecture.md).
- Data and storage contracts. See [05-data-and-storage-contracts.md](05-data-and-storage-contracts.md).
- API signatures. See [06-api-and-cli-contracts.md](06-api-and-cli-contracts.md).

## Conventions

- **Task ID:** `T-NNN` — monotonically increasing, zero-padded.
- **Phase ID:** `P-N` — sequential.
- **Branch naming:** `feat/T-NNN-short-slug`.
- **Status:** `not started` or `done`.
- **Development flow:** Vertical. Each phase delivers a demoable outcome where possible.
- **Task scope:** Single-purpose. Small, self-contained changes.

---

## P-2 — CLI Entry and Project Scaffolding

**Goal:** Users can scaffold a producer or consumer project from the terminal before the SDK runtime exists. Downstream tasks build on these scaffold outputs.

**Demo outcome:** Fresh machine → `pip install kitefs` → `kitefs init` produces a complete producer project layout on disk; `kitefs init-config` produces a consumer-only configuration.

### T-003 — CLI Entry Point and Error Boundary

**Status:** not started
**Branch:** `feat/T-003-cli-entry`
**Refined status:** yes

**Goal:** The `kitefs` console script honors the full FR-CLI-001 contract — `kitefs --help` exits `0`, `kitefs` with no subcommand prints help to stderr and exits non-zero, and any `KiteFSError` raised below the entry point renders as a plain-text actionable message on stderr with exit code `1`, while unexpected exceptions fall through with their traceback and exit code `2`.

**Scope:**

_In scope:_

- `src/kitefs/cli/__init__.py`: keep the existing Click group named `main` from T-001 (no subcommands added here); set `context_settings={"help_option_names": ["-h", "--help"]}` only if it does not already exist; do not add `invoke_without_command=True` (the default missing-subcommand behavior already exits non-zero with usage on stderr per Click's `MissingCommand`).
- `src/kitefs/cli/__init__.py`: add a thin entry-point wrapper (e.g. `def cli() -> None`) that invokes the Click group inside an error boundary; update `[project.scripts] kitefs = "kitefs.cli:cli"` in `pyproject.toml` so the console script targets this wrapper instead of the bare Click group.
- Error boundary in the wrapper:
  - Let `click.exceptions.ClickException` and `SystemExit` propagate unchanged so Click's own usage/help/exit-code handling continues to work.
  - Catch `kitefs.errors.KiteFSError` (and subclasses), print `f"Error: {error}"` to `sys.stderr` (one line, no traceback, no `repr`), and exit with code `1`.
  - Any other `Exception` is re-raised so the Python default excepthook prints the traceback and the process exits with code `2` via `sys.exit(2)` from a `try/except BaseException` outermost layer that prints the traceback via `traceback.print_exception` to stderr before exiting `2`. Keyboard interrupt (`KeyboardInterrupt`) propagates with Python's default behavior — do not catch it.
- Stdout vs. stderr: confirm Click's defaults route `--help` text to stdout and usage/error text from `MissingCommand` and `UsageError` to stderr; do not override these channels.
- No subcommands are wired in this task. The wrapper exists purely as the outermost boundary; producer/consumer scaffolding lands in T-004/T-005, and other subcommands land in P-8 onward.
- `tests/integration/test_cli_entry.py` (or a dedicated `tests/integration/test_cli_error_boundary.py`): cover the contract points listed in Acceptance Criteria using `click.testing.CliRunner` against `main`, plus subprocess invocation of the installed `kitefs` console script for the wrapper-level paths that `CliRunner` cannot cover (raw exception → exit `2` with traceback on stderr).

_Out of scope:_

- Any concrete subcommand body (`init`, `init-config`, `apply`, `list`, `describe`, `ingest`, `materialize`) — owned by their respective tasks.
- Color and `NO_COLOR` handling — Click 8 already disables ANSI when stdout is not a TTY and respects `NO_COLOR`; this task does not add custom logic for it. If a deviation is observed, file a follow-up task.
- Subcommand-level input validation. Each subcommand task is responsible for rejecting invalid input before doing any work; T-003 only guarantees the boundary that surfaces those rejections cleanly when they raise `KiteFSError`.
- Project-root discovery, configuration loading, or any SDK construction inside the CLI entry — the wrapper is purely presentational and does not import `kitefs.sdk` or `kitefs.config` at module top.
- Logging configuration and verbosity flags.

**Acceptance Criteria:**

1. `kitefs --help` exits `0` and prints Click's auto-generated usage block to stdout.
2. `kitefs` (no arguments) exits non-zero and prints usage information to stderr (stdout remains empty for the usage text). Verified via subprocess against the installed console script.
3. The console script entry point in `pyproject.toml` resolves to `kitefs.cli:cli` (the wrapper) and the wrapper invokes the existing `main` Click group.
4. When a function below `main` raises a `KiteFSError` subclass with message `"<msg>"`, the process exits with code `1` and stderr contains exactly one line matching `"Error: <msg>\n"`; stdout is empty; no Python traceback appears in either stream. Verified by parametrizing across at least three subclasses from [docs/06 § Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy) (e.g. `ConfigurationError`, `FeatureGroupNotFoundError`, `OfflineStoreReadError`).
5. When a function below `main` raises a non-`KiteFSError` exception (e.g. `RuntimeError("boom")`), the process exits with code `2` and stderr contains a Python traceback ending with the raised exception's repr; stdout is empty.
6. `click.exceptions.UsageError` raised within a subcommand callback continues to render via Click's default formatting (does not get re-wrapped by the `KiteFSError` branch). Confirmed by registering a throwaway test-only subcommand inside the test that raises `click.UsageError("bad")` and asserting Click's standard `Usage: ...\nError: bad\n` rendering and exit code `2`.
7. Importing `kitefs.cli` does not import `kitefs.sdk`, `kitefs.config`, `kitefs.providers`, `kitefs.offline_store`, `kitefs.online_store`, `kitefs.registry`, `kitefs.validation`, or `kitefs.join_engine` (verified by inspecting `sys.modules` after a fresh `import kitefs.cli` in a subprocess). The CLI module imports only `click`, `sys`, `traceback`, and `kitefs.errors`.
8. `just clean-build` continues to pass after the change.

**Doc References:**

- [FR-CLI-001 — Installed CLI Entry Point](02-product-requirements.md#fr-cli-001--installed-cli-entry-point) — entry point exists, `--help` works, no-subcommand exits non-zero with help, actionable errors without raw tracebacks for normal user errors.
- [AP-7 — Explicit Failure with Actionable Errors](04-architecture.md#architectural-design-principles) — single shared error taxonomy across SDK and CLI; CLI is the outermost error boundary.
- [CLI Error Boundary](03-system-behavior.md#cli-error-boundary) — exit `0` on success, non-zero on failure, plain text on stderr, no tracebacks for expected user errors.
- [Error Model](04-architecture.md#error-model) — unexpected errors fall through with their traceback; expected errors meet the actionable-error standard.
- [docs/06 § CLI Global Behavior](06-api-and-cli-contracts.md#global-behavior) — `0` success, `1` user errors, `2` unexpected internal; result on stdout, errors on stderr; Click as the framework.
- [docs/06 § Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy) — concrete `KiteFSError` subclasses the boundary must catch.

**Flags, Open Questions, Assumptions, Recommendations:**

- **Flag — Exit code for `kitefs` with no subcommand:** Click's default `MissingCommand` exits with `2`, but [docs/06 § Global Behavior](06-api-and-cli-contracts.md#global-behavior) reserves `2` for "unexpected internal errors" and `1` for "user errors (invalid input, missing groups, configuration problems)". A missing subcommand is arguably user input invalid, not internal. _Recommendation:_ accept Click's default (`2`) without remapping — FR-CLI-001's only stated requirement is "non-zero exit code", and remapping `MissingCommand → 1` would require swallowing and re-raising Click's exception, increasing surface area for bugs. If a stricter mapping is required later, file a follow-up after observing real usage. The acceptance criteria above intentionally assert "non-zero" rather than a specific code for AC-2.
- **Flag — Order of `try/except` clauses in the wrapper:** the wrapper must catch `KiteFSError` _before_ the bare `Exception` clause, and must let `click.exceptions.ClickException`/`SystemExit`/`KeyboardInterrupt` propagate. _Recommendation:_ structure the wrapper as: `try: main(standalone_mode=True) ... except KiteFSError as e: print(f"Error: {e}", file=sys.stderr); sys.exit(1) except SystemExit: raise except KeyboardInterrupt: raise except BaseException: traceback.print_exc(); sys.exit(2)`. Click already calls `sys.exit` internally with `standalone_mode=True`, so `SystemExit` carries Click's intended exit code through unchanged.
- **Open Question — Should the boundary print operation context (e.g. command name, args) alongside the error?** Docs require "plain text on stderr with operation context" but do not specify whether that context is the subcommand name or comes from the exception message itself. _Recommendation:_ rely on `KiteFSError` messages to carry their own operation context (per the actionable-error standard already enforced at raise sites in T-002 and downstream tasks); the boundary contributes only the `Error: ` prefix. If future tasks need a richer prefix, extend then.
- **Assumption:** T-001 has landed before T-003, so `kitefs.cli.main` exists as a no-subcommand Click group and `[project.scripts]` already targets `kitefs.cli:main`. T-003 only renames the entry-point target to `kitefs.cli:cli` and adds the wrapper; it does not re-author the group. Validated against the T-001 spec at [P-1 § T-001](#t-001--local-package-skeleton).
- **Assumption:** T-002 has landed, so `from kitefs.errors import KiteFSError` is importable. The boundary catches the base class only; subclass-specific handling is not the boundary's concern.
- **Assumption:** Exit code `2` for unexpected internal errors is implemented by an explicit `sys.exit(2)` after `traceback.print_exc()`, _not_ by allowing Python's default unhandled-exception path (which exits `1`). Without this, AC-5 would fail. Validated by inspecting CPython behavior — unhandled exceptions exit `1`, so the wrapper must override.

**Test Strategy:**

- _Unit tests:_ `tests/unit/cli/test_help.py` — invoke `main` via `CliRunner` with `["--help"]`; assert `result.exit_code == 0` and `"Usage:" in result.output`. Invoke `main` via `CliRunner` with `[]` and assert `result.exit_code != 0` and the usage text is present in `result.output` (CliRunner merges streams unless `mix_stderr=False`; use `mix_stderr=False` to assert stdout is empty and stderr carries the usage line for the no-subcommand case).
- _Integration tests:_ `tests/integration/test_cli_error_boundary.py` —
  - Register a temporary subcommand on a copy of the Click group (or on `main` inside the test, removed in teardown) that raises a parametrized `KiteFSError` subclass; invoke via `CliRunner(mix_stderr=False)` and assert exit code `1`, stdout empty, stderr equals `"Error: <msg>\n"`, no `"Traceback"` substring.
  - Same setup, but the temporary subcommand raises `RuntimeError("boom")`; invoke via subprocess against the installed `kitefs` script (CliRunner does not preserve traceback formatting) and assert exit code `2`, stdout empty, stderr contains `"Traceback"` and `"RuntimeError: boom"`.
  - Same setup, but the temporary subcommand raises `click.UsageError("bad")`; assert Click's default rendering and exit code (Click defaults to `2` for `UsageError`) — the boundary must not interfere.
  - Subprocess-launch `python -c "import kitefs.cli; import sys; print(sorted(k for k in sys.modules if k.startswith('kitefs.')))"` and assert no forbidden modules from AC-7 are imported.

### T-004 — kitefs init (Producer Scaffold)

**Status:** not started
**Branch:** `feat/T-004-cli-init`
**Refined status:** yes

**Goal:** Running `kitefs init` in a directory without `./kitefs.yaml` produces the complete producer scaffold — config, one example definition, the managed data directories, an empty registry, and `.gitignore` entries — exits `0` with a confirmation summary on stdout, and aborts with exit code `1` (exposing no partial scaffold) when a configuration already exists.

**Scope:**

_In scope:_

- Register the `init` subcommand on the existing `main` Click group under `src/kitefs/cli/`, invoked as `kitefs init`. No flags; `--help` works via the group's `help_option_names`. The Click handler is thin (no business logic per CLAUDE.md) and delegates to a pure scaffold function.
- Add a CLI-only scaffold module (e.g. `src/kitefs/cli/scaffold.py`) holding the pure scaffold logic. It imports only the standard library (`pathlib`, `os`, `tempfile`, `json`) and `kitefs.errors` — never `kitefs.sdk`, `kitefs.config`, `kitefs.providers`, `kitefs.registry`, `kitefs.offline_store`, `kitefs.online_store`, `kitefs.validation`, or `kitefs.join_engine`. This preserves the import-isolation contract from T-003 AC-7.
- Pre-flight: if `./kitefs.yaml` exists, write nothing and raise a `KiteFSError` subclass (see Open Questions) so the T-003 error boundary renders `Error: <msg>` on stderr and exits `1`.
- Create the producer tree under the current working directory at the fixed, non-configurable paths (these paths are not written into `kitefs.yaml`):
  - `kitefs.yaml` — the exact producer template from [docs/06 § Full Project Configuration](06-api-and-cli-contracts.md#full-project-configuration-kitefs-init), written as **literal text** (the inline comments are part of the generated output; do not round-trip through `yaml.dump`), with `<current_directory_name>` replaced by the project-root directory basename.
  - `feature_store/definitions/` containing one example feature group definition `.py` file (contents — see Assumptions).
  - `feature_store/registry.json` — the empty registry `{"feature_groups": {}}` serialized per the [Registry JSON serialization rules](05-data-and-storage-contracts.md#serialization-rules) (`indent=2`, `sort_keys=True`, trailing `\n`).
  - `feature_store/data/offline_store/` and `feature_store/data/online_store/` as empty managed directories. (`online.db` and per-group offline partition dirs are created lazily on first write, not by `init` — see [docs/05 § SQLite Online Store](05-data-and-storage-contracts.md#sqlite-online-store).)
  - `.gitignore` at the project root with entries for the managed data directory and the local registry file (`feature_store/data/` and `feature_store/registry.json`), leaving `feature_store/definitions/` trackable ([FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact)).
- Atomicity: a failure partway through scaffold creation leaves no partial output. Track every path this invocation creates and remove them best-effort in reverse order on any exception before re-raising. Write `kitefs.yaml` last so it doubles as the commit marker (see Flags).
- Print a confirmation summary to **stdout** listing the created paths and a next-step hint (e.g. `kitefs apply`).
- `tests/integration/test_cli_init.py` plus unit tests for the scaffold module covering the Acceptance Criteria.

_Out of scope:_

- The `init-config` consumer scaffold — T-005.
- Registry generation, definition discovery, and validation — `apply` (P-7/P-8). The example definition file is created as text only; its runtime importability is not exercised here (definition types land in P-3).
- Loading or validating `kitefs.yaml` — the configuration loader is T-012. `init` writes the file and never reads it back through the loader.
- Creating `online.db` or any per-group offline partition directories.
- Any merge/dedup into a pre-existing `.gitignore` beyond the policy chosen in Open Questions.

**Acceptance Criteria:**

1. In an empty directory, `kitefs init` exits `0` and creates exactly: `kitefs.yaml`, `feature_store/definitions/<example>.py`, `feature_store/registry.json`, `feature_store/data/offline_store/`, `feature_store/data/online_store/`, and `.gitignore`.
2. The generated `kitefs.yaml` is byte-identical to the documented producer template except that `<current_directory_name>` is replaced by the project-root basename; it includes `remote.registry`, `remote.offline_store`, and `remote.online_store`, defaults `runtime.target` to `${KITEFS_RUNTIME_TARGET:-local}`, and contains no local store path fields.
3. `feature_store/registry.json` content equals `{\n  "feature_groups": {}\n}\n` (two-space indent, trailing newline).
4. `.gitignore` ignores `feature_store/data/` and `feature_store/registry.json` and does not ignore `feature_store/definitions/`.
5. When `./kitefs.yaml` already exists, `kitefs init` exits `1`, writes nothing (no new files or directories; existing files unchanged), and prints an actionable plain-text message on stderr with no traceback.
6. When scaffold creation fails partway (simulate by patching a write to raise mid-run, or making a target path unwritable), the command exits non-zero and none of the paths this invocation would have created remain on disk.
7. The success confirmation summary is written to stdout (not stderr) and names the created paths.
8. Importing `kitefs.cli` (and the scaffold module) does not import `kitefs.sdk`, `kitefs.config`, `kitefs.providers`, `kitefs.registry`, `kitefs.offline_store`, `kitefs.online_store`, `kitefs.validation`, or `kitefs.join_engine` (verified by inspecting `sys.modules` after a fresh import in a subprocess).
9. `just clean-build` passes after the change.

**Doc References:**

- [FR-CLI-003 — Project Initialization](02-product-requirements.md#fr-cli-003--project-initialization) — producer mode creates the full scaffold; abort when a config exists; generated config contains no local store path fields.
- [FR-REG-001 — Registry as Derived Artifact](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact) — initialization creates an empty registry and a Git ignore rule for the local registry file while keeping definitions trackable.
- [`kitefs init`](03-system-behavior.md#kitefs-init) — step-by-step behavior, atomic scaffold, abort/exit outcomes.
- [docs/06 § Full Project Configuration (`kitefs init`)](06-api-and-cli-contracts.md#full-project-configuration-kitefs-init) — exact producer `kitefs.yaml` template, including comments that are part of the output.
- [docs/06 § Local Paths](06-api-and-cli-contracts.md#local-paths) — fixed local artifact paths used by `init`.
- [docs/05 § Registry JSON — Serialization Rules](05-data-and-storage-contracts.md#serialization-rules) — deterministic empty-registry serialization.
- [docs/06 § CLI Global Behavior](06-api-and-cli-contracts.md#global-behavior) — exit codes; result on stdout, errors/prompts on stderr.

**Flags, Open Questions, Assumptions, Recommendations:**

- **Flag — Atomicity strategy:** the scaffold spans multiple independent top-level entries (`kitefs.yaml` at root, the `feature_store/` tree, `.gitignore`), so a single atomic rename cannot commit the whole set. _Recommendation:_ track created paths and remove them best-effort in reverse order on failure, and write `kitefs.yaml` last as the de-facto commit marker. The watchpoint's "write-to-temp-then-rename" applies cleanly to the individual `kitefs.yaml` and `registry.json` files but not to the directory set as a whole.
- **Open Question — Exception type for "already initialized":** [docs/06 § Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy) has no dedicated "already exists" error, and `ConfigurationError` is defined as *missing/invalid* `kitefs.yaml`, not *present*. _Recommendation:_ raise `ConfigurationError` (closest documented category — a setup state the user must resolve) with an actionable message; alternatively raise base `KiteFSError`. Either renders correctly through the T-003 boundary at exit `1`. Needs a decision; keep it consistent with T-005.
- **Open Question — Pre-existing `.gitignore` or `feature_store/` when `./kitefs.yaml` is absent:** [docs/03 § kitefs init](03-system-behavior.md#kitefs-init) gates only on `./kitefs.yaml`. _Recommendation:_ if `.gitignore` already exists, append the KiteFS entries guarded by a marker comment (idempotent, no duplicates) rather than overwrite; if `feature_store/` already exists, create only the missing children without clobbering existing files. Confirm before implementing.
- **Assumption — Example definition contents:** [docs/03](03-system-behavior.md#kitefs-init) says "one example feature group definition" but does not specify the contents. _Recommendation:_ ship one minimal, self-contained group mirroring the constructor shapes in [docs/06 § Definition Types](06-api-and-cli-contracts.md#definition-types) (e.g. a trimmed `town_market_features` from [docs/01](01-reference-use-case.md)). Its import/executability becomes provable only once P-3 (definition types) lands; this task asserts file existence plus a content sanity check (e.g. contains `FeatureGroup(`), not import success.
- **Assumption — T-001 and T-003 have landed:** the `main` Click group exists and the `kitefs.cli:cli` error boundary is in place. `init` registers on `main`; this task does not author the group or the wrapper.
- **Assumption — Project name source:** `<current_directory_name>` resolves to `Path.cwd().name`. The template already double-quotes the value; a directory name containing a `"` is an unlikely edge case — flag if it must be handled.

**Test Strategy:**

- _Unit tests:_ exercise the pure scaffold function against a `tmp_path` working directory — assert the created tree, file contents (template substitution, exact registry bytes, gitignore lines), that the already-exists guard raises the chosen `KiteFSError` subclass without writing, and that a write failure mid-run removes all paths the invocation created (patch a write to raise).
- _Integration tests:_ `tests/integration/test_cli_init.py` via `CliRunner(mix_stderr=False)` in an isolated `tmp_path` cwd — exit `0` and stdout summary on success; exit `1`, stderr message, and nothing written when `kitefs.yaml` already exists; a subprocess import-isolation check for AC-8.

### T-005 — kitefs init-config (Consumer Scaffold)

**Status:** not started
**Branch:** `feat/T-005-cli-init-config`
**Refined status:** yes

**Goal:** Running `kitefs init-config` in a directory without `./kitefs.yaml` creates only the consumer `kitefs.yaml` (remote target; remote registry and online store, no offline store), exits `0` with a confirmation summary on stdout, and aborts with exit code `1` when a configuration already exists.

**Scope:**

_In scope:_

- Register the `init-config` subcommand on the existing `main` Click group, invoked as `kitefs init-config`. No flags; `--help` works. Thin handler delegating to the shared scaffold module.
- Reuse the scaffold module from T-004 for the project-name substitution, the atomic single-file write of `kitefs.yaml`, and the already-exists guard. Add a consumer-template writer that emits only `kitefs.yaml`.
- Pre-flight: if `./kitefs.yaml` exists, write nothing and raise the same `KiteFSError` subclass chosen in T-004 (exit `1`, plain stderr message).
- Write `kitefs.yaml` only, from the exact consumer template in [docs/06 § Consumer Configuration](06-api-and-cli-contracts.md#consumer-configuration-kitefs-init-config), as literal text (comments included), with `<current_directory_name>` replaced by the project-root basename. `runtime.target` defaults to `${KITEFS_RUNTIME_TARGET:-remote}`; the template includes `remote.registry` and `remote.online_store` and omits `remote.offline_store`; it contains no local store path fields.
- Do **not** create `feature_store/`, definitions, data directories, an example, or `.gitignore`.
- Print a confirmation summary to **stdout** naming the created config and noting that the `bucket` / `dynamodb_table_prefix` placeholders must be edited before the first `list`, `describe`, or `get_online_features` call.
- `tests/integration/test_cli_init_config.py` plus unit tests for the consumer-template writer.

_Out of scope:_

- The producer scaffold — T-004.
- Any configuration loading/validation, remote reachability checks, or operations — later phases (T-012 config loader, T-044 per-operation remote validation, P-12+).

**Acceptance Criteria:**

1. In an empty directory, `kitefs init-config` exits `0` and creates exactly one file — `kitefs.yaml` — and creates no `feature_store/` directory and no `.gitignore`.
2. The generated `kitefs.yaml` is byte-identical to the documented consumer template except that `<current_directory_name>` is replaced by the project-root basename; `runtime.target` defaults to `${KITEFS_RUNTIME_TARGET:-remote}`; it includes `remote.registry` and `remote.online_store`, omits `remote.offline_store`, and contains no local store path fields.
3. When `./kitefs.yaml` already exists, `kitefs init-config` exits `1`, writes nothing, and prints an actionable plain-text message on stderr with no traceback.
4. The success confirmation summary is written to stdout (not stderr), names the created config, and states the placeholder-edit next step.
5. Importing `kitefs.cli` (and the scaffold module) does not import any of the modules listed in T-004 AC-8 (import isolation per T-003 AC-7).
6. `just clean-build` passes after the change.

**Doc References:**

- [FR-CLI-003 — Project Initialization](02-product-requirements.md#fr-cli-003--project-initialization) — consumer mode creates configuration only; a consumer project can list/describe and perform online retrieval from a configured remote without further setup; generated config contains no local store path fields.
- [`kitefs init-config`](03-system-behavior.md#kitefs-init-config) — step-by-step behavior, abort/exit outcomes, config-only output.
- [docs/06 § Consumer Configuration (`kitefs init-config`)](06-api-and-cli-contracts.md#consumer-configuration-kitefs-init-config) — exact consumer `kitefs.yaml` template, including comments.
- [docs/06 § Generated File Shapes](06-api-and-cli-contracts.md#generated-file-shapes) — both variants share top-level keys; `init-config` omits `remote.offline_store`.
- [docs/06 § CLI Global Behavior](06-api-and-cli-contracts.md#global-behavior) — exit codes; result on stdout, errors on stderr.

**Flags, Open Questions, Assumptions, Recommendations:**

- **Open Question — Exception type for "already initialized":** identical to the T-004 Open Question; keep the chosen `KiteFSError` subclass consistent across both commands.
- **Assumption — Sequencing:** T-004 lands before T-005 so the shared scaffold helper (project-name substitution, atomic config write, already-exists guard) already exists. _Recommendation:_ sequence T-004 → T-005; if T-005 lands first, the shared helper originates here and T-004 reuses it.
- **Assumption — Confirmation summary content:** [docs/03](03-system-behavior.md#kitefs-init-config) requires a "confirmation summary" but does not specify its content. _Recommendation:_ name the created `kitefs.yaml` and state the placeholder-edit next step; keep it to stdout.

**Test Strategy:**

- _Unit tests:_ exercise the consumer-template writer against a `tmp_path` cwd — assert the exact file content (template substitution, `remote.offline_store` absent, `remote.registry`/`remote.online_store` present, no local path fields) and that the already-exists guard raises without writing.
- _Integration tests:_ `tests/integration/test_cli_init_config.py` via `CliRunner(mix_stderr=False)` in an isolated `tmp_path` cwd — exit `0` with only `kitefs.yaml` created and a stdout summary; exit `1` with a stderr message and nothing written when `kitefs.yaml` already exists.

---

## P-3 — Feature Definition Types

**Goal:** Users can author feature groups in Python with construction-time validation (BB-03).

### T-006 — Atomic Field Classes

**Status:** not started
**Branch:** `feat/T-006-field-classes`
**Goal:** Implement `EntityKey`, `EventTimestamp`, `Feature`, `JoinKey`, and `Metadata`.
**Description:** Each class validates its own constraints at construction time (e.g. entity key dtype must be `STRING` or `INTEGER`, event timestamp must be `DATETIME`, metadata `description` and `owner` required when metadata is present). Raises `DefinitionError` on violations. Re-export from the top-level package.
**Watchpoints:** Per-class construction-time constraints are fully enumerated in `docs/06-api-and-cli-contracts.md`. Refinement must enumerate each as an explicit acceptance criterion rather than leaving them implicit in prose.
**Requirements and References:** [FR-DEF-001](02-product-requirements.md#fr-def-001--feature-group-definition-as-code), [FR-DEF-002](02-product-requirements.md#fr-def-002--field-type-definitions)

### T-007 — Expect Builder

**Status:** not started
**Branch:** `feat/T-007-expect-builder`
**Goal:** Implement the `Expect` fluent builder for feature expectations.
**Description:** Support `not_null`, `gt`, `gte`, `lt`, `lte`, `is_in`. Validate argument types at call time. Raises `DefinitionError` on invalid arguments. Reject expectations on structural fields at the point where they would be attached.
**Requirements and References:** [FR-DEF-004](02-product-requirements.md#fr-def-004--feature-expectations)

### T-008 — FeatureGroup Composite

**Status:** not started
**Branch:** `feat/T-008-feature-group`
**Goal:** Implement `FeatureGroup` with within-group structural checks.
**Description:** Validates: required fields present, non-empty features list, exactly one entity key, exactly one event timestamp, at most one join key, unique field names across structural and feature fields, identifier names match the CON-009 regex, event timestamp is `DATETIME`. Holds per-operation validation modes with declared defaults. Raises `DefinitionError` on violations.
**Watchpoints:** CON-009 identifier-name regex is enforced _here at construction time_. Cross-set checks (duplicate group names, reserved names `year`/`month`, join references, dtype matching) belong to T-020 — do not duplicate them here.
**Requirements and References:** [FR-DEF-001](02-product-requirements.md#fr-def-001--feature-group-definition-as-code), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes), [CON-004](02-product-requirements.md#con-004--single-entity-key), [CON-009](02-product-requirements.md#con-009--identifier-naming-rules)

---

## P-4 — Validation Engine

**Goal:** A stateless validation engine ready to plug into operation gates (BB-05). The engine depends only on definition types and enums, so it lands before any storage or runtime work.

### T-009 — Structural Checks

**Status:** not started
**Branch:** `feat/T-009-structural-checks`
**Goal:** Validate row-level structural fields (presence, type compatibility, UTC).
**Description:** Check that entity key, event timestamp, and join key values are present, type-compatible with the declaration, and — for datetimes — UTC per CON-006. These checks are always enforced regardless of validation mode.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [CON-006](02-product-requirements.md#con-006--utc-only-datetimes)

### T-010 — Feature Expectation Checks

**Status:** not started
**Branch:** `feat/T-010-expectation-checks`
**Goal:** Validate feature field values against declared types and expectations.
**Description:** Apply type checks and declared `Expect` operators (`gt`, `gte`, `lt`, `lte`, `is_in`, `not_null`) per feature field. Return per-row, per-field failure details.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-DEF-004](02-product-requirements.md#fr-def-004--feature-expectations)

### T-011 — Mode-Aware Orchestration and Report

**Status:** not started
**Branch:** `feat/T-011-validation-modes`
**Goal:** Orchestrate validation with mode semantics (`ERROR`, `FILTER`, `NONE`) and produce reports.
**Description:** Structural-check failures reject the operation in every mode. `ERROR` rejects the entire operation on any feature-check failure. `FILTER` excludes failing rows and continues (empty result is allowed and reported). `NONE` skips feature checks. Produce a validation report with summary counts and per-failure details sufficient to identify which rows and fields failed and why.
**Watchpoints:** Structural checks (T-009) run in _every_ mode including `NONE` — `NONE` skips feature checks only, not structural checks. `FILTER` with all rows failing must produce an empty result with a report, not raise an error.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes)

---

## P-5 — Configuration Manager

**Goal:** `kitefs.yaml` is loaded and validated end-to-end per the prescribed sequence, with runtime target resolution (BB-10).

### T-012 — Configuration Loader

**Status:** not started
**Branch:** `feat/T-012-config-loader`
**Goal:** Implement the full `kitefs.yaml` load-and-validate pipeline in one coherent task.
**Description:** Read `./kitefs.yaml` from the project root and run the prescribed configuration loading sequence: parse the file; validate required project-level fields (version, project name, runtime target); validate fixed literal fields (remote store backend types) as literal values; apply environment variable interpolation (`${VAR:-default}`) to configurable fields only; reject interpolation expressions in fixed fields; validate the fully resolved configuration. Validate the structural shape of the optional `remote` section (required keys present, value types correct, unsupported backend identifiers rejected, remote runtime target requires a remote section) without checking whether individual store settings are complete or reachable — that check is deferred to operation time (T-031). Distinguish missing configuration (suggests initialization) from invalid configuration (identifies the offending setting and the source variable when interpolation is involved).
**Watchpoints:** Large task — refinement should produce acceptance criteria across all five distinct concerns: (1) parse, (2) required-field validation, (3) fixed-literal vs. interpolatable field distinction, (4) `${VAR:-default}` interpolation semantics, (5) structural remote-section shape. Operation-time remote completeness checks are deferred to T-044, not here.
**Requirements and References:** [FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration), [FR-CFG-003](02-product-requirements.md#fr-cfg-003--environment-variable-interpolation), [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation), [Configuration Loading Sequence](03-system-behavior.md#configuration-loading-sequence)

### T-013 — Runtime Target Override

**Status:** not started
**Branch:** `feat/T-013-target-override`
**Goal:** Allow runtime target switching via environment variable.
**Description:** Check for a `KITEFS_RUNTIME_TARGET` environment variable. When set, it overrides the `runtime.target` field from config without modifying the file.
**Requirements and References:** [FR-CFG-002](02-product-requirements.md#fr-cfg-002--runtime-target-switching)

---

## P-6 — Provider Boundary and Local Provider

**Goal:** Storage abstraction exists with a working local implementation (BB-09).

### T-014 — Provider ABCs

**Status:** not started
**Branch:** `feat/T-014-provider-abcs`
**Goal:** Define `Provider`, `RegistryStore`, `OfflineStore`, `OnlineStore` abstract base classes.
**Description:** Create `src/kitefs/providers/base.py` with the three store interfaces and the `Provider` factory ABC. Core modules will depend on these interfaces only. No provider-specific imports here.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [NFR-MAINT-001](02-product-requirements.md#nfr-maint-001--modular-architecture), [Provider Abstraction Boundary](04-architecture.md#provider-abstraction-boundary)

### T-015 — Local RegistryStore

**Status:** not started
**Branch:** `feat/T-015-local-registry-store`
**Goal:** Implement the `RegistryStore` interface for the local provider, backed by a single JSON file.
**Description:** Provide whole-document read and overwrite of the registry artifact at the fixed local path `./feature_store/registry.json`. Serialization is deterministic so the file can be inspected and diffed per the storage contract. This is the only place that touches the local registry file on disk; higher-level registry logic in BB-04 calls this interface and never reads or writes the file directly.
**Watchpoints:** "Deterministic serialization" is a four-part spec in `docs/05-data-and-storage-contracts.md` — `sort_keys=True`, features sorted by name, join_keys sorted by name, trailing newline. `json.dumps` default order is not sufficient.
**Requirements and References:** [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact), [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [Registry JSON](05-data-and-storage-contracts.md#registry-json)

### T-016 — Local OfflineStore

**Status:** not started
**Branch:** `feat/T-016-local-offline-store`
**Goal:** Implement local offline storage with Parquet files and the prescribed partition layout.
**Description:** Write Parquet files under the managed directory with year/month partitioning and the documented file-naming convention (including the ingestion source prefix and short-id collision resolution). Reads support partition-scoped access. Writes are atomic (write-to-temp then rename) so that a failed write leaves no partial file visible.
**Watchpoints:** Reads must use `pyarrow.dataset` with `partitioning='hive'` and scanner filter pushdown — not manual filesystem walk or filename parsing. Partition path (year=/month=) is the only authoritative time signal; file-name timestamp is not used for filtering.
**Requirements and References:** [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes), [Offline Store Layout](05-data-and-storage-contracts.md)

### T-017 — Local OnlineStore

**Status:** not started
**Branch:** `feat/T-017-local-online-store`
**Goal:** Implement local online storage with SQLite (one table per online-capable group).
**Description:** Create and manage SQLite tables for materialized online data per the documented schema. Support latest-per-entity upserts and key-based point lookups. Preserve prior committed state on write failure (no partial visibility).
**Watchpoints:** Write pattern is full-table replacement within one transaction (`BEGIN; DELETE FROM …; executemany INSERT …; COMMIT`) — not upsert. Set `journal_mode=WAL` and `busy_timeout=5000` on every connection open, not only at creation time.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-018 — Provider Factory Wiring

**Status:** not started
**Branch:** `feat/T-018-provider-factory`
**Goal:** Wire the provider factory to return the local provider based on configuration.
**Description:** Build the `LocalProvider` bundle that returns the three local store implementations. Factory selects provider based on the resolved runtime target. AWS provider returns a not-implemented stub until P-12. Core modules receive only the interface types — never provider-specific clients.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [FR-CFG-002](02-product-requirements.md#fr-cfg-002--runtime-target-switching), [CON-007](02-product-requirements.md#con-007--local-and-aws-providers-only)

---

## P-7 — Registry Manager and First SDK Slice

**Goal:** `FeatureStore.apply`, `list_feature_groups`, and `describe_feature_group` work end-to-end on local (BB-04, BB-02).

**Demo outcome:** Users declare groups in Python, call `apply`, then list and describe them programmatically.

### T-019 — Definition Discovery

**Status:** not started
**Branch:** `feat/T-019-definition-discovery`
**Goal:** Automatically discover feature group objects from the definitions directory.
**Description:** Scan `./feature_store/definitions/` for Python modules. Collect all module-level `FeatureGroup` instances regardless of variable name. Files outside `definitions/` are not scanned. Report an actionable message when no definitions are found.
**Requirements and References:** [FR-REG-002](02-product-requirements.md#fr-reg-002--definition-discovery)

### T-020 — Cross-Definition Validation

**Status:** not started
**Branch:** `feat/T-020-cross-validation`
**Goal:** Validate discovered definitions as a complete set before any registry write.
**Description:** Check for duplicate group names, invalid join references, join dtype mismatches between referencing and referenced join keys, and reserved field names (e.g. `year`, `month`). Collect all errors and report together in a single error before any registry write begins.
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation), [CON-009](02-product-requirements.md#con-009--identifier-naming-rules)

### T-021 — Registry Artifact Builder

**Status:** not started
**Branch:** `feat/T-021-registry-builder`
**Goal:** Build the registry artifact from validated definitions.
**Description:** Produce a JSON-serializable registry structure per the storage contract. Preserve runtime-managed fields (notably `last_materialized_at`) for groups that survive regeneration. Update `applied_at` per registered group to the current UTC time on success.
**Watchpoints:** Output must be byte-deterministic per the Registry JSON contract (see T-015 watchpoint). Groups absent from the new definition set drop their registry entry entirely — no tombstoning.
**Requirements and References:** [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact), [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-022 — FeatureStore Construction and Public Surface

**Status:** not started
**Branch:** `feat/T-022-feature-store-init`
**Goal:** Implement `FeatureStore.__init__` and finalize the top-level package re-exports.
**Description:** Constructor treats the current working directory as the project root, follows the configuration loading sequence, and builds the provider. Raises `ConfigurationError` on missing or invalid configuration. Wire the public package surface (`from kitefs import FeatureStore, FeatureGroup, EntityKey, ...`) per the contracts doc.
**Requirements and References:** [FR-CFG-001](02-product-requirements.md#fr-cfg-001--project-configuration), [NFR-MAINT-001](02-product-requirements.md#nfr-maint-001--modular-architecture), [Public Package Surface](06-api-and-cli-contracts.md#public-package-surface)

### T-023 — FeatureStore.apply (Local)

**Status:** not started
**Branch:** `feat/T-023-sdk-apply`
**Goal:** Wire `FeatureStore.apply` for local-only registry generation.
**Description:** Orchestrate discovery → cross-validation → artifact build → local registry write. Return `ApplyResult`. A failure before registry writes begin leaves the registry unchanged. Publish mode is deferred to P-12.
**Watchpoints:** The atomicity invariant — any failure during discovery, cross-validation, or artifact build must leave the on-disk registry unchanged. Acceptance criteria must include a test scenario for each failure point.
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-024 — List and Describe Feature Groups

**Status:** not started
**Branch:** `feat/T-024-list-describe`
**Goal:** Implement `list_feature_groups` and `describe_feature_group` on the SDK.
**Description:** Read from the active registry. Return summaries or full descriptions including runtime-managed fields when present. Empty registry returns an empty list (not an error). Unknown group raises `FeatureGroupNotFoundError`. A missing or unreachable selected registry fails with an actionable error.
**Requirements and References:** [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe)

---

## P-8 — Local CLI Surface

**Goal:** End-to-end local producer workflow runs from the terminal (BB-01).

**Demo outcome:** Fresh machine quickstart — install → `kitefs init` → write a group → `kitefs apply` → `kitefs list`.

### T-025 — kitefs apply

**Status:** not started
**Branch:** `feat/T-025-cli-apply`
**Goal:** Expose `apply` as a CLI subcommand.
**Description:** Call `FeatureStore.apply`. Wire the `--publish` and `--no-confirm` flags (actual remote write is deferred to P-12). Render `ApplyResult` as human-readable output.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations), [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation)

### T-026 — kitefs list and kitefs describe

**Status:** not started
**Branch:** `feat/T-026-cli-list-describe`
**Goal:** Expose list and describe as CLI subcommands with output format options.
**Description:** Default human-readable table output. Support `--format text|json` for output format selection. Support `--output <path>` to write to a file.
**Watchpoints:** `--format json` must emit the on-disk registry entry shape, not the `FeatureGroupDescription` dataclass repr — requires explicit translation. Error message for missing registry differs by runtime target (local: suggest `init` + `apply`; remote: suggest producer `apply --publish`).
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations), [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe)

---

## P-9 — Offline Ingestion

**Goal:** Users can ingest a DataFrame or file into the offline store with validation (write-path vertical slice).

**Demo outcome:** Declare → apply → ingest data → Parquet files visible on disk in the expected partition layout.

### T-027 — Offline Store Manager Write Path

**Status:** not started
**Branch:** `feat/T-027-offline-write`
**Goal:** Implement append-only write coordination in the offline store manager (BB-06).
**Description:** Accept validated data, write through the `OfflineStore` interface with the ingestion source prefix and partition layout. Never modify or delete prior files. Multi-partition batch writes guarantee per-file atomicity.
**Requirements and References:** [FR-ING-002](02-product-requirements.md#fr-ing-002--append-only-writes), [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes)

### T-028 — FeatureStore.ingest

**Status:** not started
**Branch:** `feat/T-028-sdk-ingest`
**Goal:** Wire SDK `ingest` for DataFrame input with shape checks and the ingestion validation gate.
**Description:** Verify the target group exists, check the input contains the entity key, event timestamp, join key, and declared feature fields, drop undeclared columns, apply the group's ingestion validation mode via the validation engine, then write through the offline store manager. Return `IngestResult` with row counts and the validation report (when produced).
**Watchpoints:** Five phases run in strict order with distinct error types: group lookup (`FeatureGroupNotFoundError`) → shape check (`IngestionShapeError`) → row-level structural checks (always-on, independent of mode) → feature checks (mode-driven, `ValidationError` with `error.report` in ERROR mode) → write. `IngestResult.written_files` carries absolute paths for local writes.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion), [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation), [CON-003](02-product-requirements.md#con-003--pandas-as-primary-dataframe)

### T-029 — File Input Support (CSV/Parquet)

**Status:** not started
**Branch:** `feat/T-029-file-input`
**Goal:** Allow `FeatureStore.ingest` to accept a local `.csv` or `.parquet` file path in addition to a DataFrame.
**Description:** Detect format by file extension and load into a DataFrame inside the SDK, then follow the normal ingest flow. Reject unsupported extensions. File loading is the SDK's responsibility — the CLI passes the path directly without parsing.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion), [NFR-UX-001](02-product-requirements.md#nfr-ux-001--standard-python-interfaces)

### T-030 — kitefs ingest CLI

**Status:** not started
**Branch:** `feat/T-030-cli-ingest`
**Goal:** Expose ingestion as a CLI subcommand.
**Description:** Accept group name and file path arguments. Pass the path directly to the SDK `ingest`. Render result and any validation report to stdout/stderr.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations)

---

## P-10 — Historical Retrieval and Point-in-Time Joins

**Goal:** Training datasets retrievable with point-in-time correctness (read-path vertical slice).

**Demo outcome:** Users build a leak-free training set joining two feature groups.

### T-031 — Offline Store Manager Read Path

**Status:** not started
**Branch:** `feat/T-031-offline-read`
**Goal:** Implement offline reads with event-timestamp filtering and partition pruning.
**Description:** Read Parquet data through the `OfflineStore` interface. Apply partition-level pruning for year/month. Support timestamp comparison operators (`gt`, `gte`, `lt`, `lte`) on the event timestamp column.
**Watchpoints:** Use `pyarrow.dataset` with `partitioning='hive'` and scanner filter pushdown — do not enumerate files manually or parse filenames for filtering.
**Requirements and References:** [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval)

### T-032 — get_historical_features (Single Group)

**Status:** not started
**Branch:** `feat/T-032-historical-single`
**Goal:** Implement single-group historical retrieval with `select` and `where`.
**Description:** Validate request shape (group exists, `select` provided and fields valid, filters target the event timestamp column with supported operators) before any read. Read offline data with filters. Return a DataFrame containing the group's structural columns plus the selected feature fields.
**Requirements and References:** [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval), [NFR-UX-001](02-product-requirements.md#nfr-ux-001--standard-python-interfaces)

### T-033 — Join Engine

**Status:** not started
**Branch:** `feat/T-033-join-engine`
**Goal:** Implement point-in-time correct joins (BB-08).
**Description:** Stateless, no I/O. For each base row, find the most recent joined row with event timestamp ≤ base timestamp. Equality is eligible; rows with later timestamps are never selected. Ties resolve deterministically. Re-running against unchanged data returns the same rows in the same order. Unmatched base rows remain with null joined columns.
**Watchpoints:** Tie-break semantics (equal join-key + equal event timestamp) must use a pinned secondary sort key — refinement must define it explicitly so re-runs against unchanged data are provably identical, not just probably identical.
**Requirements and References:** [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins), [AP-6](04-architecture.md#architectural-design-principles)

### T-034 — get_historical_features (Joined)

**Status:** not started
**Branch:** `feat/T-034-historical-joined`
**Goal:** Support one joined feature group in historical retrieval.
**Description:** Validate join shape (at most one joined group, registered join relationship exists, `select` dict shape valid) before any read. Read base and joined groups, apply the join engine, prefix joined columns with the joined group name; base columns remain unprefixed.
**Watchpoints:** `select` shape changes for the join path: `list[str] | "*"` for single-group, `dict[str, list[str] | "*"]` keyed by group name with join. Structural fields (entity key, event timestamp, join key) are always returned regardless of `select` — callers cannot exclude them.
**Requirements and References:** [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins)

### T-035 — Offline Retrieval Validation Gate

**Status:** not started
**Branch:** `feat/T-035-retrieval-validation`
**Goal:** Apply validation to retrieved offline data per each group's retrieval mode.
**Description:** After reading data, apply the validation engine with the group's `offline_retrieval_validation` mode. For joined retrieval, validate the base group and the joined group independently per their respective modes.
**Requirements and References:** [FR-VAL-001](02-product-requirements.md#fr-val-001--data-validation), [FR-DEF-005](02-product-requirements.md#fr-def-005--per-operation-validation-modes)

---

## P-11 — Materialization and Online Serving

**Goal:** Latest feature values served from the online store (serving-path vertical slice).

**Demo outcome:** Full local pipeline — apply → ingest → materialize → online retrieval.

### T-036 — Online Store Manager

**Status:** not started
**Branch:** `feat/T-036-online-manager`
**Goal:** Implement the online store manager for writes and reads (BB-07).
**Description:** Coordinate latest-per-entity materialization writes and key-based reads through the `OnlineStore` interface. Preserve prior committed online state on write failure. Surface the underlying error message for per-group failures.
**Watchpoints:** "Latest-per-entity" describes the _result_, not the write pattern. The SQLite implementation (T-017) uses full-table replacement — not upsert. On write failure the table state is whatever was last committed; no partial writes are visible.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-037 — FeatureStore.materialize (Named Group)

**Status:** not started
**Branch:** `feat/T-037-materialize-named`
**Goal:** Materialize a single named online-eligible group.
**Description:** Validate the named group exists and is online-eligible; reject offline-only and unknown groups with actionable errors. Read latest-per-entity from offline, write to online. A group with no offline data is reported as skipped. Idempotent. Report a per-group outcome and update `last_materialized_at` in the local working registry on success.
**Watchpoints:** `last_materialized_at` is written to the _local_ working registry on success regardless of runtime target — it propagates to the remote registry only via a subsequent `apply --publish`. Write failures go into `MaterializeResult.failed`, not raised as exceptions.
**Requirements and References:** [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups)

### T-038 — FeatureStore.materialize (All Groups)

**Status:** not started
**Branch:** `feat/T-038-materialize-all`
**Goal:** Materialize all online-eligible groups with per-group failure isolation.
**Description:** Silently exclude offline-only groups. Run materialization for each remaining group. Report per-group outcomes (succeeded, skipped, failed) through the same result shape as the named-group case. A per-group failure does not stop the run or roll back other groups.
**Watchpoints:** Offline-only groups are silently excluded from the run _and_ from the result — they do not appear in succeeded, skipped, or failed buckets. A per-group failure does not roll back already-completed groups.
**Requirements and References:** [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-039 — kitefs materialize CLI

**Status:** not started
**Branch:** `feat/T-039-cli-materialize`
**Goal:** Expose materialization as a CLI subcommand.
**Description:** Accept an optional group name. Call SDK `materialize`. Render per-group outcomes to stdout.
**Requirements and References:** [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations)

### T-040 — FeatureStore.get_online_features

**Status:** not started
**Branch:** `feat/T-040-online-retrieval`
**Goal:** Implement single-entity online retrieval.
**Description:** Validate request shape (group exists and is online-eligible, `select` provided, `where` targets the entity key with a single `eq` operator, value is type-compatible). Return a dict on hit (structural fields plus selected features), empty dict on miss. No validation gate on online retrieval.
**Requirements and References:** [FR-ONL-002](02-product-requirements.md#fr-onl-002--single-entity-online-retrieval), [NFR-UX-001](02-product-requirements.md#nfr-ux-001--standard-python-interfaces)

---

## P-12 — Remote Registry and Publish

**Goal:** AWS packaging is introduced. Remote registry operations work. Users can publish and discover features from AWS.

**Demo outcome:** `apply --publish` writes to S3 → remote `list` and `describe` read from S3 → an `init-config` project can list and describe remote groups.

### T-041 — AWS Packaging Extra and Provider Stub

**Status:** not started
**Branch:** `feat/T-041-aws-packaging`
**Goal:** Introduce the `[aws]` optional install extra and the `providers/aws/` sub-package.
**Description:** Add the `[aws]` optional dependency group to `pyproject.toml` covering boto3 and any other AWS-only dependencies. Create the `providers/aws/` sub-package as the only place AWS clients may be imported. Replace the not-implemented AWS provider stub from T-018 with a real factory entry that resolves AWS implementations. Confirm `pip install kitefs` (without extras) still imports the base package cleanly without any AWS dependency available.
**Watchpoints:** Add a packaging-level integration test that `import kitefs` succeeds in a clean environment without the `[aws]` extra — verifies no top-level boto3 import path was accidentally introduced.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [CON-007](02-product-requirements.md#con-007--local-and-aws-providers-only), [Packaging Model](04-architecture.md#packaging-model)

### T-042 — AWS Credential Chain and Error Mapping

**Status:** not started
**Branch:** `feat/T-042-aws-credentials`
**Goal:** Rely on the standard AWS credential chain and map permission errors.
**Description:** Use the standard boto3 credential resolution (env vars, AWS config, IAM role). Map missing or insufficient credentials/permissions to actionable errors that identify the affected store. Never leak secret values.
**Requirements and References:** [FR-PROV-002](02-product-requirements.md#fr-prov-002--aws-credential-chain)

### T-043 — AWS RegistryStore

**Status:** not started
**Branch:** `feat/T-043-aws-registry`
**Goal:** Implement AWS registry storage as a JSON object in S3.
**Description:** Read and overwrite the registry JSON at the configured S3 key (`s3://{bucket}/{s3_prefix}/registry.json`). Same interface as local.
**Requirements and References:** [FR-PROV-001](02-product-requirements.md#fr-prov-001--provider-boundary), [FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact)

### T-044 — Per-Operation Remote Configuration Validation

**Status:** not started
**Branch:** `feat/T-044-remote-op-validation`
**Goal:** Validate remote store availability before each operation that needs it.
**Description:** Before an operation touches a remote store, check that the required remote sub-section (registry, offline, or online) is present, fully configured, and internally valid. Fail with an actionable error that identifies the missing or invalid capability and the operation that triggered the check. This is the lazy validation counterpart to T-012's structural parse.
**Requirements and References:** [FR-CFG-004](02-product-requirements.md#fr-cfg-004--per-operation-configuration-validation)

### T-045 — apply --publish End-to-End

**Status:** not started
**Branch:** `feat/T-045-apply-publish`
**Goal:** Enable `apply --publish` to write local then remote registries with confirmation.
**Description:** Unless `--no-confirm` is passed, the CLI prompts for the exact confirmation word **before** the `./kitefs.yaml` check; any response other than the exact word aborts. On confirm: write the local registry, then write the remote registry. Handle partial failure (local succeeds, remote fails) so the local working registry may contain regenerated content while the remote remains stale, and the operation reports failure.
**Requirements and References:** [FR-REG-003](02-product-requirements.md#fr-reg-003--registry-generation), [FR-CLI-002](02-product-requirements.md#fr-cli-002--required-cli-operations), [Project Root Discovery](03-system-behavior.md#project-root-discovery)

### T-046 — Remote List and Describe Verification

**Status:** not started
**Branch:** `feat/T-046-remote-list-describe`
**Goal:** Verify list and describe work against the remote registry from both project types.
**Description:** Confirm that `list` and `describe` read from the S3 registry when the runtime target is remote. Confirm a project created by `init-config` can list and describe from the published registry without further setup.
**Requirements and References:** [FR-REG-004](02-product-requirements.md#fr-reg-004--registry-discovery-list-and-describe), [FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization)

---

## P-13 — Remote Offline Store

**Goal:** Remote ingestion and historical retrieval produce equivalent results to local.

**Demo outcome:** Ingest to S3 → `get_historical_features` with PIT join returns the same results as the local provider.

### T-047 — AWS OfflineStore

**Status:** not started
**Branch:** `feat/T-047-aws-offline`
**Goal:** Implement AWS offline storage with S3 Parquet via PyArrow and boto3.
**Description:** Same partition layout and file-naming convention as local. Atomic writes via S3 put semantics. Reads support partition-scoped access and event-timestamp filtering. Importable only from `providers/aws/` so the base package install does not require boto3.
**Requirements and References:** [FR-OFF-001](02-product-requirements.md#fr-off-001--offline-storage-backend), [NFR-REL-001](02-product-requirements.md#nfr-rel-001--atomic-offline-file-writes)

### T-048 — Remote Offline End-to-End Verification

**Status:** not started
**Branch:** `feat/T-048-remote-offline-e2e`
**Goal:** Verify ingestion and historical retrieval (single and joined) work against S3 and match local.
**Description:** Confirm `ingest` writes Parquet files to S3 in the same partition layout and naming as local, and that append-only semantics hold. Confirm `get_historical_features` with single-group and joined retrieval produces equivalent results on local and remote for the same logical data.
**Requirements and References:** [FR-ING-001](02-product-requirements.md#fr-ing-001--offline-ingestion), [FR-ING-002](02-product-requirements.md#fr-ing-002--append-only-writes), [FR-OFF-002](02-product-requirements.md#fr-off-002--historical-feature-retrieval), [FR-OFF-003](02-product-requirements.md#fr-off-003--point-in-time-correct-joins)

---

## P-14 — Remote Online Store and Consumer Serving

**Goal:** Remote materialization and online serving work. A consumer project serves features from DynamoDB.

**Demo outcome:** Remote materialize → `get_online_features` from DynamoDB → consumer `init-config` project retrieves online features.

### T-049 — AWS OnlineStore

**Status:** not started
**Branch:** `feat/T-049-aws-online`
**Goal:** Implement AWS online storage with DynamoDB per-group tables.
**Description:** Create and manage per-group DynamoDB tables with the documented naming (`{dynamodb_table_prefix}{group_name}`). Support latest-per-entity upserts and key-based reads. Surface underlying errors for per-group failure isolation. Importable only from `providers/aws/`.
**Requirements and References:** [FR-ONL-001](02-product-requirements.md#fr-onl-001--online-storage-backend), [NFR-REL-002](02-product-requirements.md#nfr-rel-002--online-materialization-failure-handling)

### T-050 — Remote Online End-to-End and Consumer Acceptance

**Status:** not started
**Branch:** `feat/T-050-remote-online-consumer`
**Goal:** Verify materialization, online retrieval, and consumer-only project flows work end-to-end against DynamoDB.
**Description:** Confirm `materialize` writes latest-per-entity rows to DynamoDB, isolates per-group failures, and updates `last_materialized_at` only on success. Confirm `get_online_features` returns equivalent results on local and remote. Confirm a project created by `init-config` can perform online retrieval against the configured remote online store without further setup.
**Requirements and References:** [FR-MAT-001](02-product-requirements.md#fr-mat-001--materialize-online-eligible-groups), [FR-ONL-002](02-product-requirements.md#fr-onl-002--single-entity-online-retrieval), [FR-CLI-003](02-product-requirements.md#fr-cli-003--project-initialization)

---

## P-15 — MVP Acceptance Demo (Reference Use Case)

**Goal:** Demonstrate KiteFS end-to-end through the reference use case on both local and remote runtime targets, proving the MVP works as a working alpha.

> **Placeholder.** Task breakdown for this phase will be handled separately. See [Reference Use Case](01-reference-use-case.md) for the scenario this phase will exercise.

---

## P-16 — Post-MVP Backlog

**Goal:** Track future capabilities outside MVP scope. Includes `pull`, batch online retrieval, mock data generation, smart sampling, and incremental materialization.

> **Placeholder.** Task breakdown for this phase will be handled separately. Requirements expected to land here: [FR-REG-005](02-product-requirements.md#fr-reg-005--remote-registry-pull), [FR-ONL-003](02-product-requirements.md#fr-onl-003--batch-online-retrieval), [FR-MOCK-001](02-product-requirements.md#fr-mock-001--mock-data-generation), [FR-SAM-001](02-product-requirements.md#fr-sam-001--smart-sampling), [FR-MAT-002](02-product-requirements.md#fr-mat-002--incremental-materialization).

---

## Requirements Coverage Matrix

Every MVP requirement in [02-product-requirements.md](02-product-requirements.md) is covered by at least one task in P-1 through P-14. Post-MVP requirements (FR-REG-005, FR-ONL-003, FR-MOCK-001, FR-SAM-001, FR-MAT-002) are tracked in P-16.

| Requirement   | Task(s)                                                       |
| ------------- | ------------------------------------------------------------- |
| FR-DEF-001    | T-006, T-008                                                  |
| FR-DEF-002    | T-002, T-006, T-008                                           |
| FR-DEF-003    | T-002                                                         |
| FR-DEF-004    | T-007, T-010                                                  |
| FR-DEF-005    | T-002, T-008, T-011                                           |
| FR-REG-001    | T-004, T-015, T-021, T-043                                    |
| FR-REG-002    | T-019                                                         |
| FR-REG-003    | T-020, T-021, T-023, T-025, T-045                             |
| FR-REG-004    | T-024, T-026, T-046                                           |
| FR-REG-005    | P-16 (deferred)                                               |
| FR-ING-001    | T-028, T-029, T-048                                           |
| FR-ING-002    | T-027, T-048                                                  |
| FR-OFF-001    | T-016, T-027, T-047                                           |
| FR-OFF-002    | T-031, T-032, T-048                                           |
| FR-OFF-003    | T-033, T-034, T-048                                           |
| FR-MAT-001    | T-037, T-038, T-050                                           |
| FR-MAT-002    | P-16 (deferred)                                               |
| FR-ONL-001    | T-017, T-036, T-049                                           |
| FR-ONL-002    | T-040, T-050                                                  |
| FR-ONL-003    | P-16 (deferred)                                               |
| FR-VAL-001    | T-009, T-010, T-011, T-028, T-035                             |
| FR-PROV-001   | T-014, T-015, T-016, T-017, T-018, T-041, T-043, T-047, T-049 |
| FR-PROV-002   | T-042                                                         |
| FR-CFG-001    | T-012, T-022                                                  |
| FR-CFG-002    | T-013, T-018                                                  |
| FR-CFG-003    | T-012                                                         |
| FR-CFG-004    | T-012, T-028, T-044                                           |
| FR-CLI-001    | T-003                                                         |
| FR-CLI-002    | T-025, T-026, T-030, T-039, T-045                             |
| FR-CLI-003    | T-004, T-005, T-046, T-050                                    |
| FR-MOCK-001   | P-16 (deferred)                                               |
| FR-SAM-001    | P-16 (deferred)                                               |
| NFR-REL-001   | T-016, T-027, T-047                                           |
| NFR-REL-002   | T-017, T-036, T-038, T-049                                    |
| NFR-UX-001    | T-028, T-029, T-032, T-040                                    |
| NFR-MAINT-001 | T-001, T-014, T-022                                           |
| CON-001       | T-001                                                         |
| CON-002       | T-001                                                         |
| CON-003       | T-028, T-032                                                  |
| CON-004       | T-008                                                         |
| CON-005       | T-001                                                         |
| CON-006       | T-009                                                         |
| CON-007       | T-018, T-041                                                  |
| CON-008       | P-16 (deferred)                                               |
| CON-009       | T-008, T-020                                                  |
