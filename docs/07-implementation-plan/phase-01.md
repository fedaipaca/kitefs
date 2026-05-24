## P-1 — Project Skeleton and Foundations

**Goal:** A buildable, testable Python package with dev tooling, the shared error model, and shared enums in place.

### T-001 — Local Package Skeleton

**Status:** done
**Branch:** `feat/T-001-package-skeleton`
**Refined status:** yes

**Goal:** A clean-venv `uv pip install -e .` produces an importable `kitefs` package with one empty sub-package per BB-XX, a working `kitefs --help` console script (placeholder Click group, no subcommands), and `just` recipes that pass on the empty skeleton — all with base dependencies only, no AWS extras.

**Scope:**

_In scope:_

- `pyproject.toml`: keep existing base dependencies (`click`, `pandas`, `pyarrow`, `pyyaml`) and dev group (`pyright`, `pytest`, `pytest-bdd`, `ruff`); confirm `requires-python = ">=3.12"` and `uv_build` backend; add `[project.scripts] kitefs = "kitefs.cli:main"`.
- `src/kitefs/__init__.py`: replace placeholder `hello()` with module body containing `__version__ = "0.1.0"` only. No re-exports yet.
- `src/kitefs/cli/__init__.py`: define `main` as a Click group with no subcommands so `kitefs --help` prints Click's auto-generated usage. No error boundary, no subcommand wiring.
- `src/kitefs/py.typed`: empty marker file present.
- Confirm every BB sub-package directory exists per [Building Block to Source Path Mapping](04-architecture.md#building-block-to-source-path-mapping) with an empty `__init__.py`: `cli/`, `sdk/`, `definitions/`, `registry/`, `validation/`, `offline_store/`, `online_store/`, `join_engine/`, `providers/` (with `local/` and `aws/` subfolders; `base.py` deferred to T-014), `config/`, `errors/`, plus the empty `enums.py` file. No symbols defined.
- Verify `just lint`, `just format-check`, `just type-check`, `just test`, `just build`, and `just clean-build` pass on the empty skeleton.

_Out of scope:_

- AWS optional extras and the `[aws]` extra group (deferred to T-041).
- Real CLI subcommands and the CLI error boundary (T-003 onward).
- Exception classes and shared enum members (T-002).
- Provider ABCs and `providers/base.py` body (T-014).
- Public re-exports of definition types, `FeatureStore`, return-type dataclasses (T-022).
- Test scaffolding beyond `tests/` directories that already exist.

**Acceptance Criteria:**

1. In a clean Python 3.12+ venv, `uv pip install -e .` from the repo root completes successfully and exposes `kitefs` as an installed distribution.
2. `kitefs --help` prints Click's auto-generated usage block to stdout and exits with code `0`.
3. `python -c "import kitefs; print(kitefs.__version__)"` succeeds and prints `0.1.0`. No `boto3` import is triggered (no `boto3` import anywhere under `src/kitefs/` outside `providers/aws/`, which is empty here).
4. Every BB sub-package listed in the source-path-mapping table exists under `src/kitefs/` with an `__init__.py` (empty body acceptable). `enums.py` and `py.typed` exist at the package root.
5. `just clean-build` (which chains `clear → check → test → build`) exits `0` on the unmodified skeleton.
6. The base install does not declare or pull in any AWS-specific runtime dependency; `pyproject.toml` contains no `[aws]` extras group.
7. For now `src/kitefs/providers/aws/__init__.py` must be completely blank and must not import `boto3`. This solidifies the constraint that importing the base package on a machine without AWS extras will not fail.

**Doc References:**

- [CON-001 — Python 3.12+](02-product-requirements.md#con-001--python-312) — declared in package metadata.
- [CON-002 — Pip-Installable Library](02-product-requirements.md#con-002--pip-installable-library) — single pip-installable package, no companion service.
- [CON-005 — No Server or Daemon](02-product-requirements.md#con-005--no-server-or-daemon) — only SDK calls or CLI invocations exist.
- [NFR-MAINT-001 — Modular Architecture](02-product-requirements.md#nfr-maint-001--modular-architecture) — separate concerns mapped to sub-packages.
- [Packaging Model](04-architecture.md#packaging-model) — `src/kitefs/` layout, `kitefs` console script, AWS extra deferred.
- [Building Block to Source Path Mapping](04-architecture.md#building-block-to-source-path-mapping) — exact directory mapping per BB.
- [FR-CLI-001 — Installed CLI Entry Point](02-product-requirements.md#fr-cli-001--installed-cli-entry-point) — partial coverage; full FR-CLI-001 conformance lands in T-003.

**Flags, Open Questions, Assumptions, Recommendations:**

- **Flag — Partial FR-CLI-001 coverage:** the placeholder CLI satisfies "command available after install" and "`--help` works" but does NOT yet enforce the full FR-CLI-001 contract (no-subcommand → non-zero exit with help, plain-text error rendering). T-003 owns the full contract. _Answer:_ accept Click's default invoke-without-subcommand behavior (which already exits non-zero with usage); do not add custom no-subcommand handling here. T-003 owns the full contract
- **Assumption:** `pyproject.toml` and `justfile` are already partially set up in the repo and only need the `[project.scripts]` addition plus the `kitefs.cli:main` target. Validated against the current files.
- **Assumption:** `src/kitefs/__init__.py` carries only `__version__` for now; full re-exports are scheduled by T-002 (errors/enums) and T-022 (definition types and `FeatureStore`).
- **Open Question — `__version__` source:** hard-coded `"0.1.0"` vs. dynamic `importlib.metadata.version("kitefs")`. _Answer:_ hard-code for the skeleton — dynamic resolution adds complexity not required here and is easy to flip later.

**Test Strategy:**

- _Unit tests:_ `tests/unit/test_package_metadata.py` — assert `kitefs.__version__` is a string equal to the value in `pyproject.toml`; assert importing `kitefs` does not raise.
- _Integration tests:_ `tests/integration/test_cli_entry.py` — using `click.testing.CliRunner`, invoke `kitefs --help` and assert exit code `0` and non-empty `result.output`. No subprocess test required; `pip install -e .` and the `kitefs` console script are verified manually as part of `just clean-build`.

### T-002 — Error Model and Shared Enums

**Status:** not started
**Branch:** `feat/T-002-errors-and-enums`
**Refined status:** yes

**Goal:** The full `KiteFSError` exception hierarchy from [docs/06 § Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy) and the three shared enums (`FeatureType`, `StorageTarget`, `ValidationMode`) are defined as importable symbols from the top-level `kitefs` package, with no behavior logic beyond declaration and a small message-formatting helper.

**Scope:**

_In scope:_

- `src/kitefs/errors/__init__.py`: define `KiteFSError` as the base class and every concrete exception class listed in [docs/06 § Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy):
  - `ConfigurationError`, `DefinitionError`, `DefinitionDiscoveryError`, `DefinitionValidationError`
  - `RegistryError` → `RegistryReadError`, `RegistryWriteError`
  - `FeatureGroupNotFoundError`, `FeatureGroupNotMaterializableError`
  - `ValidationError` (with a `report` attribute typed via forward reference; see Open Questions)
  - `IngestionShapeError`
  - `RetrievalParameterError`, `JoinError`
  - `OfflineStoreError` → `OfflineStoreReadError`, `OfflineStoreWriteError`
  - `OnlineStoreError` → `OnlineStoreReadError`, `OnlineStoreWriteError`
  - `ProviderError`
- One small helper for actionable error messages (e.g. `format_actionable(*, setting=None, group=None, field=None, problem, next_step) -> str` returning a single-line plain string). Used optionally by raisers; not enforced via subclass logic.
- `src/kitefs/enums.py`: define `FeatureType` (`STRING`, `INTEGER`, `FLOAT`, `DATETIME`), `StorageTarget` (`OFFLINE`, `OFFLINE_AND_ONLINE`), and `ValidationMode` (`ERROR`, `FILTER`, `NONE`) as `enum.Enum` subclasses with string values matching the names.
- `src/kitefs/__init__.py`: re-export every public exception class, `KiteFSError`, and the three enums so `from kitefs import KiteFSError, ConfigurationError, FeatureType, ...` works. Definition types and `FeatureStore` re-exports remain deferred to T-022.

_Out of scope:_

- `ValidationReport` / `ValidationFailure` dataclasses — owned by T-011 (validation engine). T-002 references `ValidationReport` only via a `TYPE_CHECKING` forward reference annotation on `ValidationError.report`.
- CLI error boundary that catches and renders these (T-003).
- Any raise-site code that uses these exceptions (lands in tasks that introduce each behavior).
- Provider-specific cause chaining (`__cause__`) wiring — implemented as raisers are added.

**Acceptance Criteria:**

1. `KiteFSError` exists in `kitefs.errors` and is a subclass of `Exception`.
2. Every exception class enumerated in [docs/06 § Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy) exists with the documented inheritance: `RegistryReadError` and `RegistryWriteError` inherit from `RegistryError`; `OfflineStoreReadError` / `OfflineStoreWriteError` inherit from `OfflineStoreError`; `OnlineStoreReadError` / `OnlineStoreWriteError` inherit from `OnlineStoreError`; all bases inherit from `KiteFSError`.
3. Every exception class is reachable via `from kitefs import <ClassName>` and via `from kitefs.errors import <ClassName>`.
4. `ValidationError` defines a `report` attribute (typed annotation referencing `ValidationReport` via forward reference under `TYPE_CHECKING`); constructing `ValidationError("msg", report=<sentinel>)` stores the sentinel on the instance and returns it via `error.report`.
5. `FeatureType`, `StorageTarget`, and `ValidationMode` are `enum.Enum` subclasses defined in `kitefs.enums` with the exact members listed in [docs/06 § Public Package Surface › Enums](06-api-and-cli-contracts.md#enums); each is reachable via `from kitefs import <EnumName>`.
6. The actionable-message helper is a pure function with no I/O and is importable from `kitefs.errors`. Calling it with all kwargs returns a single-line `str`.
7. Importing `kitefs.errors` triggers no provider-specific imports (no `boto3`, `sqlite3`, `pyarrow`, `pandas`).

**Doc References:**

- [Exception Hierarchy](06-api-and-cli-contracts.md#exception-hierarchy) — authoritative class list and inheritance diagram.
- [Selection Rules](06-api-and-cli-contracts.md#selection-rules) — taxonomy intent (configuration vs. operation, shape vs. validation, store-error provider-cause rule).
- [`ValidationError` Attribute](06-api-and-cli-contracts.md#validationerror-attribute) — `report: ValidationReport` contract.
- [AP-7 — Explicit Failure with Actionable Errors](04-architecture.md#architectural-design-principles) — single shared error taxonomy across SDK and CLI.
- [Error Model](04-architecture.md#error-model) — actionable-error standard.
- [02 § Conventions](02-product-requirements.md#conventions) — definition of "actionable error".
- [FR-DEF-002 — Field Type Definitions](02-product-requirements.md#fr-def-002--field-type-definitions) — supported `FeatureType` values.
- [FR-DEF-003 — Storage Target](02-product-requirements.md#fr-def-003--storage-target) — `StorageTarget` values.
- [FR-DEF-005 — Per-Operation Validation Modes](02-product-requirements.md#fr-def-005--per-operation-validation-modes) — `ValidationMode` values.
- [docs/06 § Public Package Surface › Enums](06-api-and-cli-contracts.md#enums) — exact member names.

**Flags, Open Questions, Assumptions, Recommendations:**

- **Flag — `ValidationError.report` typing cycle:** `ValidationReport` is documented in [docs/06 § Return Types](06-api-and-cli-contracts.md#return-types) and conceptually lives in `kitefs.sdk.results` (T-011). Defining the concrete dataclass in T-002 would pull SDK return-type concerns into the foundation layer; not defining it leaves `ValidationError.report` typed loosely. _Answer:_ annotate via `if TYPE_CHECKING: from kitefs.sdk.results import ValidationReport` and use a string forward reference (`report: "ValidationReport"`); accept `report` as a constructor argument with no runtime isinstance check. T-011 owns the dataclass itself.
- **Open Question — Enum value style:** `enum.Enum` with string values matching member names (e.g. `FeatureType.STRING.value == "STRING"`) is the simplest serialization fit for the registry JSON contract. _Answer:_ use `enum.Enum` (not `IntEnum` or `StrEnum`) with explicit string values; verify against [05 § Feature Group Entry Schema](05-data-and-storage-contracts.md) when T-021 lands and adjust if mismatched.
- **Open Question — Helper signature:** docs do not prescribe a specific helper API. _Answer:_ keep the helper internal to `kitefs.errors` for now (`format_actionable(*, setting=None, group=None, field=None, problem, next_step) -> str`); raise-site callers import it by name. Refactor freely as the first real raiser arrives in T-003 / T-012.
- **Assumption:** No exception class needs custom `__init__` beyond `Exception`'s default; `ValidationError` adds `report`, every other class is `pass`-bodied. Validated against the docs — no other attributes are documented.

**Test Strategy:**

- _Unit tests:_ `tests/unit/errors/test_hierarchy.py` — parametrized over every concrete exception class, assert `issubclass(cls, KiteFSError)` and the documented intermediate base (e.g. `OfflineStoreReadError → OfflineStoreError → KiteFSError`); assert each is reachable via `from kitefs import <name>` and `from kitefs.errors import <name>`.
- _Unit tests:_ `tests/unit/errors/test_validation_error.py` — construct `ValidationError("msg", report=object())`, assert `error.report is sentinel`, `str(error) == "msg"`.
- _Unit tests:_ `tests/unit/errors/test_actionable_message.py` — given representative kwargs, assert the helper returns a single-line non-empty string containing each provided value.
- _Unit tests:_ `tests/unit/test_enums.py` — assert each enum's member set equals the documented set; assert `FeatureType` reachable from top-level package.
- _Integration tests:_ none required; the contracts are import- and inheritance-shaped only, fully verifiable at the unit layer.

---
