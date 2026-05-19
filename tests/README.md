# Tests

## Layout

```
tests/
├── conftest.py          # Root shared fixtures (available to all tiers)
├── fixtures/            # Static test artifacts (data files, not pytest fixtures)
│   ├── data/            # Small sample Parquet/CSV/JSON payloads
│   ├── definitions/     # Example feature group .py files used as test inputs
│   └── registries/      # Canned registry snapshots
├── helpers/             # Shared Python helpers (factories, builders, asserters)
│   ├── builders.py      # FeatureGroup / Feature / EntityKey builders
│   ├── dataframes.py    # pandas / PyArrow DataFrame factories
│   └── tmp_store.py     # Spin up a local provider rooted at tmp_path
│
├── unit/                # Fast, isolated, no I/O outside tmp_path
│   └── <pkg>/           # Mirrors src/kitefs/<pkg>/
│       └── test_<mod>.py
│
├── integration/         # Multi-module flows through internal layers (local provider)
│   └── test_<flow>.py   # Named by user operation, not by module
│
└── bdd/                 # pytest-bdd acceptance tests
    ├── features/        # .feature files (one per user-facing capability)
    └── steps/           # Step implementations (one module per capability)
```

## Where to Put a New Test

| You are testing…                          | Put it in…                                        |
| ----------------------------------------- | ------------------------------------------------- |
| A single class or function in isolation   | `tests/unit/<pkg>/test_<module>.py`               |
| A flow crossing multiple internal modules | `tests/integration/test_<flow>.py`                |
| User-visible behavior (SDK/CLI contracts) | `tests/bdd/features/<capability>.feature` + steps |

## Naming Conventions

- Unit test files mirror source paths: `src/kitefs/validation/engine.py` → `tests/unit/validation/test_engine.py`.
- Integration test files are named by flow: `test_apply_flow.py`, `test_ingest_to_offline.py`.
- BDD feature files are named by capability: `apply.feature`, `ingest.feature`, `retrieval_offline.feature`.

## Running Tests

```bash
just test              # all tests
just test-unit         # unit only
just test-integration  # integration only
just test-bdd          # BDD only
just test-file <path>  # specific file
```

## Guidelines

- All datetimes in test fixtures must be UTC.
- Prefer `tmp_path` for any file I/O — never write to the source tree.
- Keep unit tests fast: mock or fake external boundaries, parametrize over axes.
- Integration tests use the real local provider rooted at `tmp_path`.
- BDD scenarios must reference a `Doc reference: REQ-ID` tracing back to `docs/02-product-requirements.md`.
