## P-2 — CLI Entry and Project Scaffolding

**Goal:** Users can scaffold a producer or consumer project from the terminal before the SDK runtime exists. Downstream tasks build on these scaffold outputs.

**Demo outcome:** Fresh machine → `pip install kitefs` → `kitefs init` produces a complete producer project layout on disk; `kitefs init-config` produces a consumer-only configuration.

### T-003 — CLI Entry Point and Error Boundary

**Status:** not started
**Refined status:** yes

**Goal:** The `kitefs` console script honors the full FR-CLI-001 contract — `kitefs --help` exits `0`, `kitefs` with no subcommand prints help to stderr and exits non-zero, and any `KiteFSError` raised below the entry point renders as a plain-text actionable message on stderr with exit code `1`, while unexpected exceptions fall through with their traceback and exit code `2`.

**Scope:**

_In scope:_

- `src/kitefs/cli/__init__.py`: keep the existing Click group named `main` from T-001 unchanged (no subcommands added here); do not add `invoke_without_command=True` — Click's default missing-subcommand behavior already exits non-zero with usage on stderr via `MissingCommand`.
- `src/kitefs/cli/__init__.py`: add a thin entry-point wrapper `def cli() -> None` that invokes the Click group inside an error boundary; update `[project.scripts] kitefs = "kitefs.cli:cli"` in `pyproject.toml` so the console script targets this wrapper instead of the bare Click group.
- Error boundary in the `cli` wrapper — implement the following `except` clauses in this exact order:
  1. `except KiteFSError as e` → `print(f"Error: {e}", file=sys.stderr); sys.exit(1)`. One line on stderr, no traceback.
  2. `except SystemExit` → `raise`. Lets Click's own exit codes (set internally by `standalone_mode=True`) flow through unchanged. `click.exceptions.ClickException` is already converted to `SystemExit` by Click before it leaves `main()`, so no separate clause is needed for it.
  3. `except KeyboardInterrupt` → `raise`. Preserves Python's default SIGINT exit code (130) instead of remapping to `2`.
  4. `except BaseException as e` → `traceback.print_exception(e, file=sys.stderr); sys.exit(2)`. Catches all remaining exceptions; prints the full traceback to stderr and exits `2`. Do **not** let the exception propagate unhandled — CPython's default unhandled-exception path exits `1`, not `2`.
- Stdout vs. stderr: confirm Click's defaults route `--help` text to stdout and usage/error text from `MissingCommand` and `UsageError` to stderr; do not override these channels.
- No subcommands are wired in this task. The wrapper exists purely as the outermost boundary; producer/consumer scaffolding lands in T-004/T-005, and other subcommands land in P-8 onward.
- `tests/unit/cli/test_help.py` (new file): unit tests for `--help` and no-subcommand behavior against `main` via `CliRunner`.
- `tests/integration/test_cli_error_boundary.py` (new file): integration tests covering the error-boundary contract points (AC-3 through AC-7). The existing `tests/integration/test_cli_entry.py` is not modified; it keeps its `--help` smoke tests.

_Out of scope:_

- Any concrete subcommand body (`init`, `init-config`, `apply`, `list`, `describe`, `ingest`, `materialize`) — owned by their respective tasks.
- Color and `NO_COLOR` handling — Click 8 already disables ANSI when stdout is not a TTY and respects `NO_COLOR`; this task does not add custom logic for it. If a deviation is observed, file a follow-up task.
- Subcommand-level input validation. Each subcommand task is responsible for rejecting invalid input before doing any work; T-003 only guarantees the boundary that surfaces those rejections cleanly when they raise `KiteFSError`.
- Project-root discovery, configuration loading, or any SDK construction inside the CLI entry — the wrapper is purely presentational and does not import `kitefs.sdk` or `kitefs.config` at module top.
- Logging configuration and verbosity flags.

**Acceptance Criteria:**

1. `kitefs --help` exits `0` and prints Click's auto-generated usage block to stdout.
2. `kitefs` (no arguments) exits non-zero and prints usage information to stderr (stdout remains empty for the usage text). Verified via `CliRunner(mix_stderr=False)` invoking `main` with `[]`; assert `result.exit_code != 0`, `result.output == ""` (stdout empty), and `result.stderr` non-empty.
3. The console script entry point in `pyproject.toml` resolves to `kitefs.cli:cli` (the wrapper) and the wrapper invokes the existing `main` Click group.
4. When a function below `main` raises a `KiteFSError` subclass with message `"<msg>"`, the process exits with code `1`; stderr starts with `"Error: "` and contains `str(error)` verbatim; stdout is empty; no `"Traceback"` substring appears in either stream. Verified by parametrizing across at least three subclasses from [docs/06 § Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy) (e.g. `ConfigurationError`, `FeatureGroupNotFoundError`, `OfflineStoreReadError`).
5. When a function below `main` raises a non-`KiteFSError` exception (e.g. `RuntimeError("boom")`), the process exits with code `2`; stderr contains a Python traceback whose final line is `RuntimeError: boom` (i.e. `<ClassName>: <str(error)>`); stdout is empty.
6. `click.exceptions.UsageError` raised within a subcommand callback continues to render via Click's default formatting (does not get re-wrapped by the `KiteFSError` branch). Confirmed by registering a throwaway test-only subcommand inside the test that raises `click.UsageError("bad")` and asserting Click's standard `Usage: ...\nError: bad\n` rendering and exit code `2`.
7. After a fresh `import kitefs.cli` in a subprocess, the `kitefs.*` keys in `sys.modules` form a subset of `{"kitefs", "kitefs.cli", "kitefs.enums", "kitefs.errors"}`. None of `kitefs.sdk`, `kitefs.config`, `kitefs.providers`, `kitefs.offline_store`, `kitefs.online_store`, `kitefs.registry`, `kitefs.validation`, or `kitefs.join_engine` may appear. (`kitefs.enums` and `kitefs.errors` are expected because `kitefs/__init__.py` imports them.) The `kitefs.cli` module itself imports only `click`, `sys`, `traceback`, and `kitefs.errors`.
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
- **Flag — Order of `try/except` clauses in the wrapper:** the wrapper must catch `KiteFSError` _before_ the catch-all clause, and must let `SystemExit` and `KeyboardInterrupt` propagate. _Recommendation:_ structure the wrapper as: `try: main() ... except KiteFSError as e: print(f"Error: {e}", file=sys.stderr); sys.exit(1) except SystemExit: raise except KeyboardInterrupt: raise except BaseException as e: traceback.print_exception(e, file=sys.stderr); sys.exit(2)`. `standalone_mode=True` is Click's default — pass no kwargs. `SystemExit` carries Click's intended exit code through unchanged.
- **Open Question — Should the boundary print operation context (e.g. command name, args) alongside the error?** Docs require "plain text on stderr with operation context" but do not specify whether that context is the subcommand name or comes from the exception message itself. _Recommendation:_ rely on `KiteFSError` messages to carry their own operation context (per the actionable-error standard already enforced at raise sites in T-002 and downstream tasks); the boundary contributes only the `Error: ` prefix. If future tasks need a richer prefix, extend then.
- **Assumption:** T-001 has landed before T-003, so `kitefs.cli.main` exists as a no-subcommand Click group and `[project.scripts]` already targets `kitefs.cli:main`. T-003 only renames the entry-point target to `kitefs.cli:cli` and adds the wrapper; it does not re-author the group. Validated against the T-001 spec at [P-1 § T-001](#t-001--local-package-skeleton).
- **Assumption:** T-002 has landed, so `from kitefs.errors import KiteFSError` is importable. The boundary catches the base class only; subclass-specific handling is not the boundary's concern.
- **Assumption:** Every `KiteFSError` message is single-line, consistent with the `format_actionable` helper from T-002 and the actionable-error convention in [02 § Conventions](02-product-requirements.md#conventions). The boundary does not normalize newlines. If a future raiser produces a multi-line message, AC-4 must be re-evaluated at that point.
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
**Refined status:** yes

**Goal:** Running `kitefs init` in a directory without `./kitefs.yaml` produces the complete producer scaffold — config, one example definition, the managed data directories, an empty registry, and `.gitignore` entries — exits `0` with a confirmation summary on stdout, and aborts with exit code `1` (exposing no partial scaffold) when a configuration already exists.

**Scope:**

_In scope:_

- Register the `init` subcommand on the existing `main` Click group under `src/kitefs/cli/`, invoked as `kitefs init`. No flags; `--help` works via the group's `help_option_names`. The Click handler is thin (no business logic per CLAUDE.md) and delegates to a pure scaffold function.
- Add a CLI-only scaffold module (e.g. `src/kitefs/cli/scaffold.py`) holding the pure scaffold logic. It imports only the standard library (`pathlib`, `os`, `tempfile`, `json`) and `kitefs.errors` — never `kitefs.sdk`, `kitefs.config`, `kitefs.providers`, `kitefs.registry`, `kitefs.offline_store`, `kitefs.online_store`, `kitefs.validation`, or `kitefs.join_engine`. This preserves the import-isolation contract from T-003 AC-7.
- Pre-flight: if `./kitefs.yaml` exists, write nothing and raise `ConfigurationError` (per D1 — message identifies the conflicting absolute path) so the T-003 error boundary renders `Error: <msg>` on stderr and exits `1`.
- Create the producer tree under the current working directory at the fixed, non-configurable paths (these paths are not written into `kitefs.yaml`):
  - `kitefs.yaml` — the exact producer template from [docs/06 § Full Project Configuration](06-api-and-cli-contracts.md#full-project-configuration-kitefs-init), written as **literal text** (the inline comments are part of the generated output; do not round-trip through `yaml.dump`), with the literal three-token sequence `"<current_directory_name>"` replaced by `json.dumps(Path.cwd().name, ensure_ascii=False)` so any cwd basename (including those with `"`, `\`, or non-ASCII) produces a valid YAML double-quoted scalar.
  - `feature_store/definitions/town_market_features.py` — byte-identical to the `town_market_features` block from [docs/01 § Town Market Features](01-reference-use-case.md), embedded as a module-level string constant in the scaffold module.
  - `feature_store/registry.json` — the empty registry `{"feature_groups": {}}` serialized per the [Registry JSON serialization rules](05-data-and-storage-contracts.md#serialization-rules) (`indent=2`, `sort_keys=True`, trailing `\n`).
  - `feature_store/data/offline_store/` and `feature_store/data/online_store/` as empty managed directories, created with `mkdir(parents=True, exist_ok=True)`. (`online.db` and per-group offline partition dirs are created lazily on first write, not by `init` — see [docs/05 § SQLite Online Store](05-data-and-storage-contracts.md#sqlite-online-store).)
  - `.gitignore` at the project root with entries for the managed data directory and the local registry file (`feature_store/data/` and `feature_store/registry.json`), leaving `feature_store/definitions/` trackable ([FR-REG-001](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact)). If `.gitignore` already exists, append only the entries that are not already present (line-exact match, ignoring trailing whitespace); do not overwrite. If both entries already exist, leave the file untouched.
- If `feature_store/registry.json` or `feature_store/definitions/town_market_features.py` already exists when `./kitefs.yaml` is absent, abort with `ConfigurationError` naming the conflicting absolute path; do not overwrite, do not skip.
- Atomicity: a failure partway through scaffold creation leaves no partial output. Track every **file** this invocation creates (not pre-existing directories) and remove them best-effort in reverse creation order on any exception before re-raising. Write `kitefs.yaml` last so it doubles as the commit marker (see AC-9). The two text files (`kitefs.yaml`, `registry.json`) are written via write-to-temp-then-rename within their target directory so a partial write is never visible.
- Print a confirmation summary to **stdout** exactly as specified in AC-10.
- `tests/integration/test_cli_init.py` plus unit tests for the scaffold module covering the Acceptance Criteria.

_Out of scope:_

- The `init-config` consumer scaffold — T-005.
- Registry generation, definition discovery, and validation — `apply` (P-7/P-8). The example definition file is created as text only; its runtime importability is not exercised here (definition types land in P-3).
- Loading or validating `kitefs.yaml` — the configuration loader is T-012. `init` writes the file and never reads it back through the loader.
- Creating `online.db` or any per-group offline partition directories.
- Any merge/dedup into a pre-existing `.gitignore` beyond the append-only policy in the in-scope bullets above.

**Acceptance Criteria:**

1. In an empty directory, `kitefs init` exits `0` and creates exactly: `kitefs.yaml`, `feature_store/definitions/town_market_features.py`, `feature_store/registry.json`, `feature_store/data/offline_store/`, `feature_store/data/online_store/`, and `.gitignore`.
2. The generated `kitefs.yaml` is byte-identical to the documented producer template (`docs/06-api-and-cli-contracts.md` § Full Project Configuration) except that the literal three-token sequence `"<current_directory_name>"` is replaced by `json.dumps(Path.cwd().name, ensure_ascii=False)`. It includes `remote.registry`, `remote.offline_store`, and `remote.online_store`; defaults `runtime.target` to `${KITEFS_RUNTIME_TARGET:-local}`; contains no local store path fields.
3. When the project-root basename contains characters requiring YAML escaping, the resulting `kitefs.yaml` round-trips through `yaml.safe_load(...)` and yields `project.name == Path.cwd().name`. Verified with a parametrized test using basenames `'plain'`, `'with space'`, `'with"quote'`, `'with\\backslash'`, and `'türkçe'`.
4. `feature_store/registry.json` content equals `{\n  "feature_groups": {}\n}\n` (two-space indent, trailing newline, UTF-8).
5. `feature_store/definitions/town_market_features.py` content is byte-identical to the `town_market_features` block from `docs/01-reference-use-case.md` § Town Market Features (including the leading file-path comment line and a trailing newline).
6. `.gitignore` behavior:
   - (a) absent before run → created with exactly two entries: `feature_store/data/` and `feature_store/registry.json`, each on its own line with a trailing newline.
   - (b) present without either entry → both entries appended in declaration order; original bytes unchanged.
   - (c) present with one entry already → only the missing entry appended.
   - (d) present with both entries already → file left untouched (byte-identical content asserted).
   - In all cases, `feature_store/definitions/` is **not** ignored (no rule matches it).
7. When `./kitefs.yaml` already exists, `kitefs init` exits `1`, writes nothing (no new files or directories; existing files unchanged), and stderr is exactly `Error: kitefs.yaml already exists at <absolute-path>; remove it or run \`kitefs init\` from a different directory.\n` with no traceback. The exception raised is `ConfigurationError`.
8. When `feature_store/registry.json` or `feature_store/definitions/town_market_features.py` already exists while `./kitefs.yaml` is absent, `kitefs init` exits `1` via `ConfigurationError`, writes nothing new, and stderr names the conflicting absolute path.
9. When scaffold creation fails partway (simulate by patching the `kitefs.yaml` write or the `registry.json` write to raise), the command exits non-zero and only the files this invocation created are removed. Pre-existing directories (e.g. a `feature_store/` that existed before the run) remain intact. `kitefs.yaml` is never observed in a partial state on disk.
10. The success confirmation summary is written to stdout (not stderr) and matches this exact format:
    ```
    Created KiteFS producer scaffold in <absolute-cwd>:
      kitefs.yaml
      feature_store/definitions/town_market_features.py
      feature_store/registry.json
      feature_store/data/offline_store/
      feature_store/data/online_store/
      .gitignore

    Next step: edit feature_store/definitions/, then run 'kitefs apply' to register them.
    ```
    The `.gitignore` line is replaced by `  .gitignore (appended N entry/entries)` when entries were appended to an existing file, and omitted entirely when both entries were already present.
11. Importing `kitefs.cli` (and the scaffold module) does not import `kitefs.sdk`, `kitefs.config`, `kitefs.providers`, `kitefs.registry`, `kitefs.offline_store`, `kitefs.online_store`, `kitefs.validation`, or `kitefs.join_engine` (verified by inspecting `sys.modules` after a fresh `python -c "import kitefs.cli"` in a subprocess). The scaffold module's top-level imports are exactly `pathlib`, `os`, `tempfile`, `json`, and `kitefs.errors`.
12. `just clean-build` passes after the change.

**Doc References:**

- [FR-CLI-003 — Project Initialization](02-product-requirements.md#fr-cli-003--project-initialization) — producer mode creates the full scaffold; abort when a config exists; generated config contains no local store path fields.
- [FR-REG-001 — Registry as Derived Artifact](02-product-requirements.md#fr-reg-001--registry-as-derived-artifact) — initialization creates an empty registry and a Git ignore rule for the local registry file while keeping definitions trackable.
- [`kitefs init`](03-system-behavior.md#kitefs-init) — step-by-step behavior, atomic scaffold, abort/exit outcomes.
- [docs/06 § Full Project Configuration (`kitefs init`)](06-api-and-cli-contracts.md#full-project-configuration-kitefs-init) — exact producer `kitefs.yaml` template, including comments that are part of the output.
- [docs/06 § Local Paths](06-api-and-cli-contracts.md#local-paths) — fixed local artifact paths used by `init`.
- [docs/05 § Registry JSON — Serialization Rules](05-data-and-storage-contracts.md#serialization-rules) — deterministic empty-registry serialization.
- [docs/06 § CLI Global Behavior](06-api-and-cli-contracts.md#global-behavior) — exit codes; result on stdout, errors/prompts on stderr.

**Resolved Decisions:**

- **D1 — Exception for "already initialized":** raise `ConfigurationError` (see AC-7 for exact message). Selected via the rule at `docs/06-api-and-cli-contracts.md` § Exception Hierarchy — *"`ConfigurationError` always indicates a setup problem the user must fix in `kitefs.yaml` or environment variables."* T-005 reuses this choice.
- **D2 — Atomicity:** track every **file** the invocation creates; on failure remove them best-effort in reverse creation order, then re-raise. `kitefs.yaml` is written last (de-facto commit marker). The two text files (`kitefs.yaml`, `registry.json`) use temp-file-then-rename. Pre-existing directories are tolerated and not removed on rollback. Covered by AC-9.
- **D3 — Pre-existing `feature_store/` and `.gitignore`:** directories created with `exist_ok=True`. `feature_store/registry.json` and `feature_store/definitions/town_market_features.py` are conflict-aborts via `ConfigurationError` (AC-8). `.gitignore` is append-only per AC-6.
- **D4 — Example definition contents:** byte-identical copy of `town_market_features` from `docs/01-reference-use-case.md` § Town Market Features, embedded as a string constant in the scaffold module. Runtime importability asserted only after P-3 lands; T-004 asserts byte-equality (AC-5).
- **D5 — Project-name substitution:** `json.dumps(Path.cwd().name, ensure_ascii=False)` replaces the literal `"<current_directory_name>"` (with surrounding quotes) in the template, producing a valid YAML double-quoted scalar for any cwd basename. Covered by AC-2 and AC-3.
- **D6 — Confirmation summary format:** exact wording specified in AC-10.
- **Sequencing:** T-001 and T-003 have landed; `kitefs.cli.main` and the `kitefs.cli:cli` error boundary already exist. `init` registers on `main` without re-authoring the group.

**Test Strategy:**

- _Unit tests:_ exercise the pure scaffold function against a `tmp_path` working directory — assert the created tree, file contents (template substitution, exact registry bytes, gitignore lines), that the already-exists guard raises `ConfigurationError` without writing (AC-7), and that a write failure mid-run removes only the files the invocation created (patch the `kitefs.yaml` write and the `registry.json` write, two parametrizations — AC-9). Additional:
  - Parametrize the YAML round-trip test across the five basenames in AC-3 (`monkeypatch.chdir(tmp_path / basename)` for each).
  - Cover all four `.gitignore` sub-cases from AC-6 with a parametrized fixture.
  - Cover both conflict variants from AC-8 (pre-existing `registry.json`, pre-existing `town_market_features.py`).
  - Snapshot-test `town_market_features.py` bytes against the literal block from `docs/01`.
- _Integration tests:_ `tests/integration/test_cli_init.py` via `CliRunner(mix_stderr=False)` in an isolated `tmp_path` cwd — exit `0` and exact stdout summary (literal-string comparison per AC-10, including all three `.gitignore`-line variants) on success; exit `1`, exact stderr message, and nothing written when `kitefs.yaml` already exists; a subprocess import-isolation check for AC-11.

### T-005 — kitefs init-config (Consumer Scaffold)

**Status:** not started
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

- **Resolved (mirrors T-004 D1):** `ConfigurationError` is raised when `./kitefs.yaml` already exists; the message wording mirrors T-004 AC-7 with the command name swapped to `kitefs init-config`.
- **Assumption — Sequencing:** T-004 lands before T-005 so the shared scaffold helper (project-name substitution, atomic config write, already-exists guard) already exists. _Recommendation:_ sequence T-004 → T-005; if T-005 lands first, the shared helper originates here and T-004 reuses it.
- **Assumption — Confirmation summary content:** [docs/03](03-system-behavior.md#kitefs-init-config) requires a "confirmation summary" but does not specify its content. _Recommendation:_ name the created `kitefs.yaml` and state the placeholder-edit next step; keep it to stdout.

**Test Strategy:**

- _Unit tests:_ exercise the consumer-template writer against a `tmp_path` cwd — assert the exact file content (template substitution, `remote.offline_store` absent, `remote.registry`/`remote.online_store` present, no local path fields) and that the already-exists guard raises without writing.
- _Integration tests:_ `tests/integration/test_cli_init_config.py` via `CliRunner(mix_stderr=False)` in an isolated `tmp_path` cwd — exit `0` with only `kitefs.yaml` created and a stdout summary; exit `1` with a stderr message and nothing written when `kitefs.yaml` already exists.

---
