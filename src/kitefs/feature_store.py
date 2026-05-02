"""SDK entry point — orchestrates all KiteFS operations through a single class."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd
from pandas import DataFrame

from kitefs.config import load_config
from kitefs.exceptions import (
    ConfigurationError,
    DataValidationError,
    FeatureGroupNotFoundError,
    IngestionError,
    ProviderError,
    SchemaValidationError,
)
from kitefs.offline_store import OfflineStoreManager
from kitefs.providers.factory import create_provider
from kitefs.registry import ApplyResult, RegistryManager
from kitefs.validation import validate_data, validate_data_selected, validate_schema

_T = TypeVar("_T", list[dict], dict)


def _resolve_input(data: object) -> DataFrame:
    """Resolve *data* to a DataFrame, or raise IngestionError for unsupported types."""
    if isinstance(data, DataFrame):
        return data
    if isinstance(data, str):
        path = Path(data)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            try:
                # parse_dates=True uses pandas heuristics for date detection; datetime
                # columns may not always be inferred correctly. Acceptable for MVP scope.
                return pd.read_csv(path, parse_dates=True)  # type: ignore[return-value]  # pandas stubs don't narrow to DataFrame
            except Exception as e:  # catch-all: pandas can raise ParserError, OSError, etc. for malformed files
                raise IngestionError(
                    f"Cannot read CSV file '{data}': {e}. "
                    f"Check that the file exists, is readable, and contains valid CSV data."
                ) from e
        if suffix == ".parquet":
            try:
                return pd.read_parquet(path)  # type: ignore[return-value]  # pandas stubs don't narrow to DataFrame
            except Exception as e:  # catch-all: pyarrow can raise ArrowInvalid, OSError, etc. for malformed files
                raise IngestionError(
                    f"Cannot read Parquet file '{data}': {e}. "
                    f"Check that the file exists, is readable, and contains valid Parquet data."
                ) from e
        raise IngestionError(f"Unsupported file extension '{suffix}' for '{data}'. Supported formats: .csv, .parquet.")
    raise IngestionError(
        f"Unsupported data type '{type(data).__name__}'. "
        f"Expected a Pandas DataFrame, or a path to a .csv or .parquet file."
    )


@dataclass(frozen=True)
class IngestResult:
    """Result of a feature group ingestion operation."""

    rows_written: int
    partitions_affected: tuple[str, ...]


class FeatureStore:
    """Root SDK class that wires configuration, provider, and managers.

    Instantiate with an explicit project root or let the constructor walk
    up from the current working directory to find ``kitefs.yaml``.
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        """Initialise the feature store from a KiteFS project directory.

        If *project_root* is provided, use it directly. Otherwise walk up
        from ``cwd`` to locate ``kitefs.yaml``.
        """
        resolved_root = self._resolve_project_root(project_root)

        config = load_config(resolved_root)
        provider = create_provider(config)
        self._registry_manager = RegistryManager(provider, config.definitions_path)
        self._offline_store_manager = OfflineStoreManager(provider)

    def apply(self) -> ApplyResult:
        """Register all feature group definitions into the registry."""
        return self._registry_manager.apply()

    def ingest(
        self,
        feature_group_name: str,
        data: DataFrame | str,
    ) -> IngestResult:
        """Write feature data to the offline store for a registered feature group.

        Validates schema and data according to the group's ingestion validation
        mode before writing. Extra columns are silently dropped.
        """
        definition = self._registry_manager.get_group(feature_group_name)
        df = _resolve_input(data)

        try:
            # Phase 1 — schema validation (always runs, drops extra columns).
            _, cleaned_df = validate_schema(definition, df)

            # Phase 2 — data validation per ingestion_validation mode.
            _, validated_df = validate_data(definition, cleaned_df, definition.ingestion_validation)
        except SchemaValidationError as exc:
            raise SchemaValidationError(
                f"During ingest of feature group '{feature_group_name}': {exc}",
                report=exc.report,
            ) from exc
        except DataValidationError as exc:
            raise DataValidationError(
                f"During ingest of feature group '{feature_group_name}': {exc}",
                report=exc.report,
            ) from exc

        if validated_df.empty:
            return IngestResult(rows_written=0, partitions_affected=())

        try:
            write_result = self._offline_store_manager.write(
                group_name=feature_group_name,
                df=validated_df,
                event_timestamp_col=definition.event_timestamp.name,
                source_prefix="ing",
            )
        except ProviderError as exc:
            raise ProviderError(f"During ingest of feature group '{feature_group_name}': {exc}") from exc

        return IngestResult(
            rows_written=write_result.rows_written,
            partitions_affected=write_result.partitions_affected,
        )

    def get_historical_features(
        self,
        from_: str,
        select: list[str] | str | dict[str, list[str] | str],
        where: dict[str, dict[str, Any]] | None = None,
        join: list[str] | None = None,
    ) -> DataFrame:
        """Retrieve historical feature data from the offline store.

        Supports single feature group retrieval (no-join path). The join
        path will be implemented in a future task.
        """
        # Validate all parameters upfront — raises on invalid input.
        self._registry_manager.validate_query_params(
            from_=from_, select=select, where=where, join=join, method="get_historical_features"
        )

        definition = self._registry_manager.get_group(from_)
        et_col = definition.event_timestamp.name
        ek_col = definition.entity_key.name

        # Resolve selected feature names.
        all_feature_names = [f.name for f in definition.features]
        if select == "*":
            selected_features = all_feature_names
        elif isinstance(select, list):
            selected_features = list(select)
        else:  # pragma: no cover — validate_query_params rejects other types
            selected_features = all_feature_names

        # Build output column list: structural columns + selected features.
        output_columns = [ek_col, et_col, *selected_features]

        # Resolve where → time_filter for BB-06.
        time_filter = where.get("event_timestamp") if where else None

        # Read from offline store with partition pruning.
        df = self._offline_store_manager.read(
            group_name=from_,
            event_timestamp_col=et_col,
            time_filter=time_filter,
        )

        # Empty result — synthesize correct shape.
        if df.empty:
            return DataFrame(columns=output_columns)

        # Apply select narrowing.
        narrowed_df: DataFrame = df[output_columns].reset_index(drop=True)  # type: ignore[assignment]  # pandas stubs don't narrow list indexing to DataFrame

        # Retrieval-gate validation on selected features only.
        try:
            _, validated_df = validate_data_selected(
                definition, narrowed_df, definition.offline_retrieval_validation, selected_features
            )
        except DataValidationError as exc:
            raise DataValidationError(
                f"During retrieval of feature group '{from_}': {exc}",
                report=exc.report,
            ) from exc

        # Post-validation empty check (FILTER mode may remove all rows).
        if validated_df.empty:
            return DataFrame(columns=output_columns)

        return validated_df

    def list_feature_groups(
        self,
        format: str | None = None,
        target: str | None = None,
    ) -> list[dict] | str:
        """Return a summary of all registered feature groups.

        Parameters match the documented API contract: default returns
        ``list[dict]``, ``format="json"`` returns a JSON string,
        ``target`` writes JSON to a file and returns the target path.
        """
        summaries = self._registry_manager.list_groups()
        return self._format_output(summaries, format=format, target=target)

    def describe_feature_group(
        self,
        name: str,
        format: str | None = None,
        target: str | None = None,
    ) -> dict | str:
        """Return the full definition of a specific registered feature group.

        Raises FeatureGroupNotFoundError if *name* is not in the registry.
        """
        try:
            entry = self._registry_manager.get_group_entry(name)
        except FeatureGroupNotFoundError:
            raise FeatureGroupNotFoundError(
                f"Feature group '{name}' not found in registry. Run `kitefs list` to see registered groups."
            ) from None
        return self._format_output(entry, format=format, target=target)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_output(
        data: _T,
        *,
        format: str | None,
        target: str | None,
    ) -> _T | str:
        """Apply the target-first, then format=json, then structured-return precedence."""
        if target is not None:
            Path(target).write_text(
                json.dumps(data, sort_keys=True, indent=2),
                encoding="utf-8",
            )
            return str(target)
        if format == "json":
            return json.dumps(data, sort_keys=True, indent=2)
        return data

    @staticmethod
    def _resolve_project_root(project_root: str | Path | None) -> Path:
        """Resolve the project root to a concrete directory containing kitefs.yaml."""
        if project_root is not None:
            root = Path(project_root).resolve()
            if not (root / "kitefs.yaml").exists():
                raise ConfigurationError("No KiteFS project found. Run `kitefs init` to create one.")
            return root

        # Walk upward from cwd until kitefs.yaml is found.
        current = Path.cwd().resolve()
        while True:
            if (current / "kitefs.yaml").exists():
                return current
            parent = current.parent
            if parent == current:
                # Reached filesystem root without finding a project.
                raise ConfigurationError("No KiteFS project found. Run `kitefs init` to create one.")
            current = parent
