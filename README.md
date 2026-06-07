# KiteFS

KiteFS is a Python feature store library for machine learning. It manages the full lifecycle of ML features — defining feature groups as Python code, registering them in a versioned registry, storing historical data as Parquet, retrieving point-in-time-correct training datasets, and serving the latest values for real-time predictions.

KiteFS is library-first: no running server, no Docker, no infrastructure to manage. Install it, define your features, and start building.

> **Alpha:** KiteFS is in early development (`0.3.0a0`). APIs may change between releases.

## Features

- Define feature groups as Python code with typed features and validation rules.
- Compile definitions into a versioned, deterministic registry.
- Store historical feature rows as Hive-partitioned Parquet (offline store).
- Retrieve point-in-time-correct training datasets, with optional point-in-time joins.
- Materialize and serve the latest value per entity for real-time inference (online store).
- Run locally (Parquet + SQLite) or on AWS (S3 + DynamoDB).

## Installation

KiteFS is currently a pre-release, so you must opt in to alpha versions.

```bash
pip install --pre kitefs
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv add --prerelease=allow kitefs
```

For the AWS backend (S3 + DynamoDB):

```bash
pip install --pre "kitefs[aws]"
```

Once a stable release is published, `pip install kitefs` (or `uv add kitefs`) will work without the pre-release flag.

Requires **Python 3.12+**.

## Quick start

Scaffold a project:

```bash
kitefs init
```

Define a feature group (e.g. `feature_store/definitions/town_market_features.py`):

```python
from kitefs import (
    EntityKey,
    EventTimestamp,
    Expect,
    Feature,
    FeatureGroup,
    FeatureType,
    StorageTarget,
    ValidationMode,
)

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="event_timestamp"),
    features=[
        Feature(
            name="avg_price_per_sqm",
            dtype=FeatureType.FLOAT,
            expect=Expect().not_null().gt(0),
        ),
    ],
    ingestion_validation=ValidationMode.ERROR,
)
```

Compile definitions into the registry:

```bash
kitefs apply
```

Ingest data, build a training dataset, and serve the latest values from the SDK:

```python
from kitefs import FeatureStore

store = FeatureStore()

# Append validated rows to the offline store (DataFrame, .csv, or .parquet).
store.ingest("town_market_features", "town_market_2025.csv")

# Retrieve a point-in-time-correct training dataset.
training_df = store.get_historical_features(
    from_="town_market_features",
    select=["avg_price_per_sqm"],
)

# Populate the online store with the latest value per entity.
store.materialize("town_market_features")

# Serve the latest features for one entity.
features = store.get_online_features(
    from_="town_market_features",
    select=["avg_price_per_sqm"],
    where={"town_id": {"eq": 1}},
)
```

## CLI

| Command                        | Description                                             |
| ------------------------------ | ------------------------------------------------------- |
| `kitefs init`                  | Scaffold a new producer project.                        |
| `kitefs init-config`           | Create a consumer-only configuration.                   |
| `kitefs apply`                 | Compile feature definitions into the registry.          |
| `kitefs list`                  | List registered feature groups.                         |
| `kitefs describe <name>`       | Show full details for a feature group.                  |
| `kitefs ingest <group> <path>` | Append validated rows to the offline store.             |
| `kitefs materialize [group]`   | Populate the online store from the latest offline rows. |

## Documentation

- [Repository](https://github.com/fedaipaca/kitefs)
- [Getting Started guide](https://github.com/fedaipaca/kitefs/blob/main/docs/Getting-Started-kitefs.md)

## License

Apache-2.0.
