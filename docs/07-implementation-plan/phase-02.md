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
- **Open Question — Exception type for "already initialized":** [docs/06 § Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy) has no dedicated "already exists" error, and `ConfigurationError` is defined as _missing/invalid_ `kitefs.yaml`, not _present_. _Recommendation:_ raise `ConfigurationError` (closest documented category — a setup state the user must resolve) with an actionable message; alternatively raise base `KiteFSError`. Either renders correctly through the T-003 boundary at exit `1`. Needs a decision; keep it consistent with T-005.
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
