# kitefs

A Python feature store library for offline/online feature storage, registry, materialization, validation, and serving. Designed for Machine Learning practitioners who need feature management with minimal operational overhead.

- **SDK**: Python API for notebooks, scripts, and applications (`from kitefs import FeatureStore`)
- **CLI**: Command-line interface (`kitefs init`, `kitefs apply`, `kitefs ingest`, etc.)
- **Library-first**: No running server, no Docker — just `pip install` and go

## Install from TestPyPI

> TestPyPI is a separate package index used for testing. The `--extra-index-url` flag tells pip to fetch dependencies (like `click` and `pyyaml`) from the real PyPI, since TestPyPI may not have them.

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ kitefs==0.1.0
```

Verify the installation:

```bash
# Should display the available commands
kitefs --help

# Create a new KiteFS project in the current directory
kitefs init
```

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — Fast Python package manager
- **[just](https://github.com/casey/just)** — Command runner (like `make`, but simpler)

### Install uv

Follow the instructions at https://github.com/astral-sh/uv?tab=readme-ov-file#installation to install `uv` for your platform.

### Install just

Follow the instructions at https://github.com/astral-sh/uv?tab=readme-ov-file#installation to install `just` for your platform.

## Getting Started

```bash
# To clone the repository and set up the project, run:
git clone https://github.com/fedaipaca/kitefs.git
cd kitefs

# To install dependencies, run:
uv sync

# To list available commands, run:
just
```

## Available Commands

Run `just` with no arguments to see all commands:

```bash
just
```

| Command           | Description                              |
| ----------------- | ---------------------------------------- |
| `just dev`        | Run the project locally                  |
| `just test`       | Run all tests                            |
| `just lint`       | Check code for lint issues               |
| `just format`     | Auto-format code                         |
| `just fix`        | Auto-fix lint issues                     |
| `just check`      | Run lint + tests (quick pre-commit check)|
| `just build`      | Build the package                        |
| `just clean`      | Remove build artifacts and caches        |
| `just clean-build`| Clean then build from scratch            |

## Project Structure

```
kitefs/
├── src/
│   └── kitefs/          # Directory contains source code files
├── tests/               # Directory contains test files
├── docs/                # Design documents
├── pyproject.toml       # Project config, dependencies, tool settings
├── justfile             # Task runner commands
└── uv.lock              # Locked dependencies
```
