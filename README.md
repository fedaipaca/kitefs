# KiteFS

KiteFS is a Python feature store library for machine learning. It manages the full lifecycle of ML features — defining feature groups as Python code, registering them in a versioned registry, storing historical data in Parquet files, and serving the latest values for real-time predictions.

KiteFS is library-first: no running server, no Docker, no infrastructure to manage. Install it with `pip`, define your features, and start building.

- **SDK**: `from kitefs import FeatureStore`
- **CLI**: `kitefs init`, `kitefs apply`, `kitefs list`, `kitefs describe`, and more
- **Python 3.12+** required
