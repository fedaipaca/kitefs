# KiteFS

KiteFS is a Python feature store library for machine learning. It manages the full lifecycle of ML features — defining feature groups as Python code, registering them in a versioned registry, storing historical data in Parquet files, and serving the latest values for real-time predictions.

KiteFS is library-first: no running server, no Docker, no infrastructure to manage. Install it with `pip`, define your features, and start building.

- **SDK**: `from kitefs import FeatureStore`
- **CLI**: `kitefs init`, `kitefs apply`, `kitefs list`, `kitefs describe`, and more
- **Python 3.12+** required

## Installation

KiteFS is currently in alpha. To install the latest pre-release version:

```bash
pip install --pre kitefs
```

## Usage

### Quick Start (CLI)

```bash
# 1. Initialize a new KiteFS project
kitefs init

# 2. Edit feature_store/definitions/example_features.py
#    to define your feature groups as Python code

# 3. Register definitions into the registry
kitefs apply

# 4. List registered feature groups
kitefs list

# 5. Inspect a specific feature group
kitefs describe <feature_group_name>
```

### SDK

```python
from kitefs import FeatureStore

# Initialize — finds kitefs.yaml by walking up from cwd
fs = FeatureStore()

# Register all feature group definitions
result = fs.apply()
print(f"Registered {result.group_count} group(s)")

# List all registered feature groups
groups = fs.list_feature_groups()

# Describe a specific feature group
details = fs.describe_feature_group("listing_features")

# Export as JSON
json_output = fs.list_feature_groups(format="json")

# Write JSON to a file
fs.describe_feature_group("listing_features", target="output.json")
```

### Available Features

- **Project scaffolding** (`kitefs init`) — initialize a new KiteFS project with config, directory structure, and example definitions
- **Feature group definitions** — define feature groups as Python code using frozen dataclasses (`FeatureGroup`, `Feature`, `EntityKey`, `EventTimestamp`, `Expect`, etc.)
- **Registry** (`kitefs apply`, `kitefs list`, `kitefs describe`) — register, list, and inspect feature groups via a deterministic JSON registry suitable for Git versioning
- **Local provider** — local filesystem storage with Hive-style Parquet partitioning for the offline store
- **Configuration** — YAML-based project configuration (`kitefs.yaml`) with environment variable overrides

### In Development

The following features are planned but not yet available:

- **Data validation** — schema and data validation engine with configurable strictness modes (ERROR, FILTER, NONE) to enforce quality constraints on ingested data
- **Data ingestion** (`kitefs ingest`) — ingest DataFrames, CSV, or Parquet files into the offline store with automatic partitioning and validation
- **Historical retrieval** — query the offline store with column selection and time-range filtering for training dataset generation
- **Point-in-time joins** — temporally correct joins across feature groups to prevent data leakage in training sets
- **Materialization** (`kitefs materialize`) — sync the latest feature values from the offline store to a SQLite-backed online store
- **Online serving** — single-key lookups for real-time feature serving from the online store
- **AWS provider** — S3 + DynamoDB backend for production deployments, installable via `pip install kitefs[aws]`
- **Registry sync** — push and pull the registry between local and remote storage
- **Mock data generation** (`kitefs mock`) — generate synthetic test data that respects schema and expectations
- **Smart sampling** (`kitefs sample`) — pull a representative data subset from a remote store for local development

## Contributing

### Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **[just](https://github.com/casey/just)** — command runner

### Setup

```bash
git clone https://github.com/fedaipaca/kitefs.git
cd kitefs
uv sync
```

### Run checks

```bash
# Lint + format check + type check + tests
just check
```
