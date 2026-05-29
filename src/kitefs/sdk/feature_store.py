from __future__ import annotations

import contextlib
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from kitefs.config import RuntimeConfig, load_runtime_config
from kitefs.errors import IngestionShapeError, RegistryReadError, format_actionable
from kitefs.offline_store import prepare_ingestion_table
from kitefs.providers import Provider, build_provider
from kitefs.registry import (
    build_registry_document,
    discover_feature_groups,
    summarize_registry,
    validate_cross_definition,
)
from kitefs.registry import (
    describe_feature_group as _describe_feature_group,
)
from kitefs.sdk.results import ApplyResult, FeatureGroupDescription, FeatureGroupSummary, IngestResult
from kitefs.validation import validate_dataframe


class FeatureStore:
    """User-facing SDK entry point.

    Reads ./kitefs.yaml from the current working directory, resolves the
    runtime target, and wires up the matching provider.
    """

    def __init__(self) -> None:
        root = Path.cwd()
        self._config: RuntimeConfig = load_runtime_config(root)
        self._provider: Provider = build_provider(self._config, root)

    @property
    def runtime_target(self) -> str:
        """Resolved runtime target: 'local' or 'remote'."""
        return self._config.target

    def apply(self, *, publish: bool = False) -> ApplyResult:
        """Compile feature definitions into the local registry.

        Discovers all FeatureGroup instances in ./feature_store/definitions/*.py,
        validates them as a set, then atomically writes ./feature_store/registry.json.
        Returns an ApplyResult listing the registered group names sorted alphabetically.

        publish=True is reserved for a future remote-write feature and is accepted
        but has no effect in this implementation.
        """
        definitions_dir = Path.cwd() / "feature_store" / "definitions"
        groups = discover_feature_groups(definitions_dir)
        validate_cross_definition(groups)

        store = self._provider.registry_store()
        try:
            prior = store.read()
        except RegistryReadError as exc:
            if isinstance(exc.__cause__, FileNotFoundError):
                prior = {"feature_groups": {}}
            else:
                raise

        document = build_registry_document(
            groups,
            prior_document=prior,
            now=datetime.now(UTC),
        )
        store.write(document)

        return ApplyResult(
            registered_groups=sorted(g.name for g in groups),
            published=False,
        )

    def list_feature_groups(self) -> list[FeatureGroupSummary]:
        """Return a summary for each registered feature group, sorted alphabetically by name.

        Returns an empty list when the registry contains no groups.
        Raises RegistryReadError if the registry is missing or undecodable.
        """
        document = self._provider.registry_store().read()
        return summarize_registry(document)

    def describe_feature_group(self, name: str) -> FeatureGroupDescription:
        """Return the full description for the named feature group.

        Raises FeatureGroupNotFoundError if name is not in the registry.
        Raises RegistryReadError if the registry is missing or undecodable.
        """
        document = self._provider.registry_store().read()
        return _describe_feature_group(document, name)

    def ingest(
        self,
        feature_group: str,
        data: pd.DataFrame | str | os.PathLike[str],
    ) -> IngestResult:
        """Append validated feature rows to the local offline store.

        Accepts a pandas DataFrame, a .csv file path, or a .parquet file path.
        Runs the validation engine using the group's ingestion_validation mode,
        then writes accepted rows as Hive-partitioned Parquet files under
        feature_store/data/offline_store/{group}/year=YYYY/month=MM/.

        Args:
            feature_group: Registered feature group name.
            data: A DataFrame, or a path string/os.PathLike ending in .csv or .parquet.

        Returns:
            IngestResult with accepted/rejected row counts, written file paths,
            and the ValidationReport (None when ingestion_validation is NONE).

        Raises:
            FeatureGroupNotFoundError: Group not in the registry.
            IngestionShapeError: Required column missing or unsupported file extension.
            ValidationError: Structural failure, or feature failure in ERROR mode.
            OfflineStoreWriteError: Physical write failure.
            RegistryReadError: Registry missing or undecodable.
        """
        document = self._provider.registry_store().read()
        description = _describe_feature_group(document, feature_group)

        frame = _normalize_input(data)
        frame = _coerce_datetime_columns(frame, description)
        total_rows = len(frame)

        accepted_frame, report = validate_dataframe(
            description, frame, description.ingestion_validation, operation="ingestion"
        )

        accepted_rows = len(accepted_frame)
        rejected_rows = total_rows - accepted_rows

        if accepted_rows == 0:
            return IngestResult(
                feature_group=feature_group,
                accepted_rows=0,
                rejected_rows=rejected_rows,
                written_files=[],
                validation_report=report,
            )

        table = prepare_ingestion_table(description, accepted_frame)
        written_files = self._provider.offline_store().write(
            feature_group,
            table,
            event_timestamp_column=description.event_timestamp.name,
            source_prefix="ing",
        )

        return IngestResult(
            feature_group=feature_group,
            accepted_rows=accepted_rows,
            rejected_rows=rejected_rows,
            written_files=written_files,
            validation_report=report,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS = {".csv", ".parquet"}


def _normalize_input(data: pd.DataFrame | str | os.PathLike[str]) -> pd.DataFrame:
    """Convert *data* to a pandas DataFrame.

    - DataFrame → copy (defensive; validation must not mutate the caller's frame).
    - Path ending in .csv → pd.read_csv().
    - Path ending in .parquet → pd.read_parquet().
    - Any other path suffix → raises IngestionShapeError with a clear message.
    """
    if isinstance(data, pd.DataFrame):
        return data.copy()

    path = Path(os.fspath(data))
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)

    raise IngestionShapeError(
        format_actionable(
            group="<unknown>",
            problem=(f"unsupported input file extension {suffix!r}; only .csv and .parquet are accepted"),
            next_step="pass a .csv or .parquet file path, or a pandas DataFrame directly",
        )
    )


def _coerce_datetime_columns(
    frame: pd.DataFrame,
    description: FeatureGroupDescription,
) -> pd.DataFrame:
    """Parse string/object datetime columns to proper pandas datetime dtypes.

    Converts the event_timestamp column and any DATETIME feature columns whose
    current pandas dtype is not already a datetime type.  This allows CSV inputs
    whose timestamps are ISO-8601 strings to pass through the validation engine.
    UTC-aware strings produce UTC-aware datetimes (validated as UTC upstream).
    Naive strings produce naive datetimes (treated as UTC per CON-006).
    """
    from kitefs.enums import FeatureType

    frame = frame.copy()

    datetime_cols = [description.event_timestamp.name]
    for feat in description.features:
        if feat.dtype == FeatureType.DATETIME:
            datetime_cols.append(feat.name)
    for jk in description.join_keys:
        if jk.dtype == FeatureType.DATETIME:
            datetime_cols.append(jk.name)

    for col in datetime_cols:
        if col not in frame.columns:
            continue
        series = frame[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            continue
        # Parse; infer_datetime_format and utc=True so tz-aware strings get
        # timezone info preserved as UTC-aware.  Naive strings stay naive.
        with contextlib.suppress(ValueError, TypeError):
            frame[col] = pd.to_datetime(series, utc=False, format="mixed")

    return frame
