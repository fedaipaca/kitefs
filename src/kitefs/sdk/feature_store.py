from __future__ import annotations

import contextlib
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from kitefs.config import RuntimeConfig, load_runtime_config
from kitefs.errors import IngestionShapeError, JoinError, RegistryReadError, RetrievalParameterError, format_actionable
from kitefs.join_engine import point_in_time_join
from kitefs.offline_store import build_offline_schema, prepare_ingestion_table
from kitefs.providers import Provider, TimestampFilter, build_local_provider, build_provider
from kitefs.registry import (
    build_registry_document,
    discover_feature_groups,
    summarize_registry,
    validate_cross_definition,
)
from kitefs.registry import (
    describe_feature_group as _describe_feature_group,
)
from kitefs.sdk.results import (
    ApplyResult,
    FeatureGroupDescription,
    FeatureGroupSummary,
    IngestResult,
    MaterializeResult,
)
from kitefs.validation import validate_dataframe


class FeatureStore:
    """User-facing SDK entry point.

    Reads ./kitefs.yaml from the current working directory, resolves the
    runtime target, and wires up the matching provider.
    """

    def __init__(self) -> None:
        self._root: Path = Path.cwd()
        self._config: RuntimeConfig = load_runtime_config(self._root)
        self._provider: Provider = build_provider(self._config, self._root)

    @property
    def runtime_target(self) -> str:
        """Resolved runtime target: 'local' or 'remote'."""
        return self._config.target

    def apply(self, *, publish: bool = False) -> ApplyResult:
        """Compile feature definitions into the local registry.

        Discovers all FeatureGroup instances in ./feature_store/definitions/*.py,
        validates them as a set, then atomically writes ./feature_store/registry.json.
        Returns an ApplyResult listing the registered group names sorted alphabetically.

        publish=True is reserved for Feature 14, which will also push to the remote
        registry after the local write. Plain apply always writes the local working
        registry regardless of the configured runtime target.
        """
        definitions_dir = self._root / "feature_store" / "definitions"
        groups = discover_feature_groups(definitions_dir)
        validate_cross_definition(groups)

        store = build_local_provider(self._root).registry_store()
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

    def materialize(self, feature_group: str | None = None) -> MaterializeResult:
        """Populate the online store from the latest offline rows.

        Reads all offline rows for one named online-capable group or every
        registered online-capable group, extracts exactly one latest row per
        entity key by event timestamp, and atomically replaces the group's
        SQLite table contents.

        Args:
            feature_group: Name of a single registered group to materialize.
                When None (default), all groups with storage_target
                OFFLINE_AND_ONLINE are materialized.

        Returns:
            MaterializeResult with succeeded, skipped, and failed groups.
            An all-groups run with no eligible groups returns an empty result.

        Raises:
            FeatureGroupNotFoundError: Named group is not in the registry.
            FeatureGroupNotMaterializableError: Named group has storage_target OFFLINE.
            OfflineStoreReadError: Offline data cannot be read (before per-group tracking).
            RegistryReadError: Registry is missing or undecodable.
        """
        from kitefs.enums import StorageTarget
        from kitefs.errors import FeatureGroupNotFoundError, FeatureGroupNotMaterializableError
        from kitefs.online_store import select_latest_rows
        from kitefs.sdk.results import FailedGroup, MaterializeResult, SkippedGroup

        _DATETIME_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"

        registry_store = self._provider.registry_store()
        document = registry_store.read()
        all_groups = document.get("feature_groups", {})

        # Resolve target list.
        if feature_group is not None:
            if feature_group not in all_groups:
                raise FeatureGroupNotFoundError(
                    format_actionable(
                        group=feature_group,
                        problem="feature group is not registered",
                        next_step="run store.apply() to register the group, or check the group name",
                    )
                )
            entry = all_groups[feature_group]
            if entry.get("storage_target") != StorageTarget.OFFLINE_AND_ONLINE.value:
                raise FeatureGroupNotMaterializableError(
                    format_actionable(
                        group=feature_group,
                        problem=(
                            f"storage_target is {entry.get('storage_target')}"
                            " — only OFFLINE_AND_ONLINE groups can be materialized"
                        ),
                        next_step=(
                            "change the group's storage_target to OFFLINE_AND_ONLINE and re-apply, or omit this group"
                        ),
                    )
                )
            targets = [feature_group]
        else:
            targets = sorted(
                name
                for name, entry in all_groups.items()
                if entry.get("storage_target") == StorageTarget.OFFLINE_AND_ONLINE.value
            )

        succeeded: list[str] = []
        skipped: list[SkippedGroup] = []
        failed: list[FailedGroup] = []

        for name in targets:
            description = _describe_feature_group(document, name)
            schema = build_offline_schema(description)

            # Read all offline rows — no timestamp filter.
            offline_table = self._provider.offline_store().read(
                name,
                event_timestamp_column=description.event_timestamp.name,
                schema=schema,
                timestamp_filter=None,
            )

            if len(offline_table) == 0:
                skipped.append(SkippedGroup(name=name, reason="no offline data"))
                continue

            latest_rows = select_latest_rows(
                offline_table,
                entity_key_column=description.entity_key.name,
                event_timestamp_column=description.event_timestamp.name,
            )

            try:
                self._provider.online_store().materialize(
                    name,
                    latest_rows,
                    entity_key_column=description.entity_key.name,
                )
            except Exception as exc:
                failed.append(FailedGroup(name=name, error_message=str(exc)))
                continue

            # Update last_materialized_at in the document and persist.
            document["feature_groups"][name]["last_materialized_at"] = datetime.now(UTC).strftime(_DATETIME_FMT)
            registry_store.write(document)
            succeeded.append(name)

        return MaterializeResult(succeeded=succeeded, skipped=skipped, failed=failed)

    def get_online_features(
        self,
        *,
        from_: str,
        select: list[str] | None = None,
        where: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return the latest stored feature values for a single entity key.

        Performs a point lookup against the local SQLite online store.
        No row-level validation runs on the serving path.

        Args:
            from_: Registered feature group name.
            select: Required.  A list of feature field names, or ["*"] to select
                all declared feature fields.  Structural fields (entity key,
                event timestamp, join keys) are always returned automatically.
            where: Required.  Entity-key filter of the form
                {entity_key_name: {"eq": value}}.  Only the group's registered
                entity key is accepted as the filter field; only the "eq"
                operator is supported; the value must be a single literal
                type-compatible with the entity key dtype.

        Returns:
            A dict containing the entity key, event timestamp, any declared join
            keys, and the selected feature fields on hit.  Returns {} on miss,
            including when the group has never been materialized.

        Raises:
            FeatureGroupNotFoundError: Group not in the registry.
            FeatureGroupNotMaterializableError: Group storage_target is OFFLINE.
            RetrievalParameterError: Invalid select or where parameters.
            OnlineStoreReadError: SQLite lookup fails.
            RegistryReadError: Registry missing or unreadable.
        """
        from kitefs.enums import StorageTarget
        from kitefs.errors import FeatureGroupNotMaterializableError

        document = self._provider.registry_store().read()
        description = _describe_feature_group(document, from_)

        if description.storage_target != StorageTarget.OFFLINE_AND_ONLINE:
            raise FeatureGroupNotMaterializableError(
                format_actionable(
                    group=from_,
                    problem=(
                        f"storage_target is {description.storage_target.value}"
                        " — only OFFLINE_AND_ONLINE groups can be served online"
                    ),
                    next_step=(
                        "change the group's storage_target to OFFLINE_AND_ONLINE and re-apply,"
                        " or use get_historical_features for OFFLINE groups"
                    ),
                )
            )

        selected_names = _resolve_no_join_select(select, description)
        entity_key_value = _build_online_entity_lookup(where, description)

        output_columns = _structural_columns(description) + selected_names

        raw = self._provider.online_store().get(
            from_,
            entity_key_value,
            entity_key_column=description.entity_key.name,
            select=output_columns,
        )

        if not raw:
            return {}

        return _coerce_online_result(raw, description)

    def get_historical_features(
        self,
        *,
        from_: str,
        select: list[str] | dict[str, list[str]] | None = None,
        join: list[str] | None = None,
        where: dict[str, dict[str, Any]] | None = None,
    ) -> pd.DataFrame:
        """Retrieve historical feature rows from one registered feature group.

        Validates the request, applies event-timestamp filtering to a
        partition-pruned read from the local offline store, optionally joins one
        additional feature group point-in-time, runs offline retrieval validation,
        and returns a pandas DataFrame.

        Args:
            from_: Registered feature group name (the base group).
            select: Required.  Without join, a list of feature field names or
                ["*"]; with join, a dict keyed by base and joined group names.
            join: None or a list containing at most one joined feature group.
            where: Optional event-timestamp filter.  Shape:
                {event_timestamp_name: {op: datetime}} where op is one of
                gt, gte, lt, lte and the value is a datetime.datetime.
                Pass None (default) to return all rows.

        Returns:
            A pandas DataFrame with the group's structural columns (entity key,
            event timestamp, join keys) plus the selected feature columns.
            Returns an empty DataFrame when no rows match the filter.

        Raises:
            FeatureGroupNotFoundError: Group not in the registry.
            RetrievalParameterError: Invalid select or where parameters.
            OfflineStoreReadError: Physical read failure.
            ValidationError: Retrieval validation rejects rows in ERROR mode.
            RegistryReadError: Registry missing or unreadable.
        """
        document = self._provider.registry_store().read()
        joined_group = _resolve_join_group(join, from_)
        description = _describe_feature_group(document, from_)

        if joined_group is not None:
            joined_description = _describe_feature_group(document, joined_group)
            base_join_key = _find_join_key(description, joined_group)
            selected_base_names, selected_joined_names = _resolve_join_select(select, description, joined_description)
            timestamp_filter = _build_timestamp_filter(where, description.event_timestamp.name, from_)

            base_schema = build_offline_schema(description)
            base_table = self._provider.offline_store().read(
                from_,
                event_timestamp_column=description.event_timestamp.name,
                schema=base_schema,
                timestamp_filter=timestamp_filter,
            )
            base_frame = base_table.to_pandas()
            base_columns = _structural_columns(description) + selected_base_names
            joined_columns = _structural_columns(joined_description) + selected_joined_names
            output_columns = base_columns + _prefixed_columns(joined_group, joined_columns)

            if len(base_frame) == 0:
                return base_frame[base_columns].reindex(columns=output_columns)

            base_frame = base_frame[base_columns]
            selected_base_desc = _selected_description(description, selected_base_names)
            accepted_base, _ = validate_dataframe(
                selected_base_desc,
                base_frame,
                description.offline_retrieval_validation,
                operation="retrieval",
            )

            joined_schema = build_offline_schema(joined_description)
            joined_table = self._provider.offline_store().read(
                joined_group,
                event_timestamp_column=joined_description.event_timestamp.name,
                schema=joined_schema,
                timestamp_filter=None,
            )
            joined_frame = joined_table.to_pandas()[joined_columns]
            if len(joined_frame) > 0:
                selected_joined_desc = _selected_description(joined_description, selected_joined_names)
                joined_frame, _ = validate_dataframe(
                    selected_joined_desc,
                    joined_frame,
                    joined_description.offline_retrieval_validation,
                    operation="retrieval",
                )

            return point_in_time_join(
                base_frame=accepted_base,
                joined_frame=joined_frame,
                base_join_key_column=base_join_key,
                base_event_timestamp_column=description.event_timestamp.name,
                joined_entity_key_column=joined_description.entity_key.name,
                joined_event_timestamp_column=joined_description.event_timestamp.name,
                joined_output_columns=joined_columns,
                joined_group_name=joined_group,
            )

        selected_names = _resolve_no_join_select(select, description)
        timestamp_filter = _build_timestamp_filter(where, description.event_timestamp.name, from_)

        schema = build_offline_schema(description)
        table = self._provider.offline_store().read(
            from_,
            event_timestamp_column=description.event_timestamp.name,
            schema=schema,
            timestamp_filter=timestamp_filter,
        )

        frame = table.to_pandas()

        structural = _structural_columns(description)
        output_columns = structural + selected_names

        # Return early for empty results — no validation needed.
        if len(frame) == 0:
            return frame[output_columns]

        frame = frame[output_columns]

        # Run retrieval validation only on selected feature columns.
        selected_desc = _selected_description(description, selected_names)
        accepted_frame, _ = validate_dataframe(
            selected_desc, frame, description.offline_retrieval_validation, operation="retrieval"
        )
        return accepted_frame


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS = {".csv", ".parquet"}

_ALLOWED_WHERE_OPS: frozenset[str] = frozenset({"gt", "gte", "lt", "lte"})


def _resolve_join_group(join: list[str] | None, base_group_name: str) -> str | None:
    """Validate the join parameter and return the requested joined group name."""
    if join is None or join == []:
        return None
    if isinstance(join, str):
        raise RetrievalParameterError(
            format_actionable(
                group=base_group_name,
                problem="join must be a list of feature group names, not a bare string",
                next_step='pass join=["group_name"] or omit join= for no-join retrieval',
            )
        )
    if not isinstance(join, list):
        raise RetrievalParameterError(
            format_actionable(
                group=base_group_name,
                problem="join must be None or a list with at most one feature group name",
                next_step='pass join=["group_name"] or omit join= for no-join retrieval',
            )
        )
    if len(join) > 1:
        raise JoinError(
            format_actionable(
                group=base_group_name,
                problem="historical retrieval supports at most one joined feature group",
                next_step="pass a single group name in join= or run separate retrievals",
            )
        )

    joined_group = join[0]
    if not isinstance(joined_group, str) or not joined_group.strip():
        raise RetrievalParameterError(
            format_actionable(
                group=base_group_name,
                problem="join item must be a non-empty feature group name string",
                next_step='pass join=["group_name"]',
            )
        )
    return joined_group


def _resolve_join_select(
    select: list[str] | dict[str, list[str]] | None,
    base_description: FeatureGroupDescription,
    joined_description: FeatureGroupDescription,
) -> tuple[list[str], list[str]]:
    """Validate dict-shaped select for joined historical retrieval."""
    if select is None:
        raise RetrievalParameterError(
            format_actionable(
                group=base_description.name,
                problem="select is required",
                next_step="pass a dict keyed by the base and joined feature group names",
            )
        )
    if not isinstance(select, dict):
        raise RetrievalParameterError(
            format_actionable(
                group=base_description.name,
                problem="select must be a dict when join= is provided",
                next_step=(
                    f'pass select={{"{base_description.name}": ["feature"], "{joined_description.name}": ["feature"]}}'
                ),
            )
        )

    expected = {base_description.name, joined_description.name}
    actual = set(select.keys())
    if actual != expected:
        raise RetrievalParameterError(
            format_actionable(
                group=base_description.name,
                problem=f"select keys for join must be exactly {sorted(expected)}, got {sorted(actual)}",
                next_step="include one select entry for the base group and one for the joined group",
            )
        )

    base_selected = _resolve_no_join_select(select[base_description.name], base_description)
    joined_selected = _resolve_no_join_select(select[joined_description.name], joined_description)
    return base_selected, joined_selected


def _find_join_key(base_description: FeatureGroupDescription, joined_group_name: str) -> str:
    """Return the base join-key column that references the joined group."""
    for join_key in base_description.join_keys:
        if join_key.referenced_group == joined_group_name:
            return join_key.name
    raise JoinError(
        format_actionable(
            group=base_description.name,
            problem=f"no JoinKey references joined group '{joined_group_name}'",
            next_step="declare a JoinKey on the base group that references the joined feature group",
        )
    )


def _prefixed_columns(group_name: str, columns: list[str]) -> list[str]:
    """Return joined output column names prefixed with the joined group name."""
    return [f"{group_name}_{column}" for column in columns]


def _resolve_no_join_select(
    select: list[str] | dict[str, list[str]] | None,
    description: FeatureGroupDescription,
) -> list[str]:
    """Validate and resolve the select parameter for the no-join retrieval path.

    Accepts a list of feature field names or ["*"] for all features.
    Rejects None, dict-shaped select, bare "*", empty lists, mixed wildcard
    lists, and names that are not declared feature fields.

    Returns a list of resolved feature field names in the caller's order, or
    in registry (alphabetical) order for the wildcard form.
    """
    if select is None:
        raise RetrievalParameterError(
            format_actionable(
                group=description.name,
                problem="select is required",
                next_step='pass a list of feature field names or ["*"] to select all features',
            )
        )
    if isinstance(select, dict):
        raise RetrievalParameterError(
            format_actionable(
                group=description.name,
                problem='dict-shaped select requires join=; use list[str] or ["*"] for no-join retrieval',
                next_step='use select=["feature1", "feature2"] or select=["*"]',
            )
        )
    if isinstance(select, str):
        raise RetrievalParameterError(
            format_actionable(
                group=description.name,
                problem="select must be a list, not a bare string",
                next_step='wrap it in a list: select=["*"] to select all features',
            )
        )
    if not isinstance(select, list):
        raise RetrievalParameterError(
            format_actionable(
                group=description.name,
                problem='select must be a list of feature field names or ["*"]',
                next_step='pass select=["feature1", "feature2"] or select=["*"]',
            )
        )
    if len(select) == 0:
        raise RetrievalParameterError(
            format_actionable(
                group=description.name,
                problem="select must not be empty",
                next_step='pass at least one feature field name or use select=["*"]',
            )
        )
    # Wildcard form: ["*"] only; ["*", "other"] is rejected.
    if "*" in select:
        if len(select) > 1:
            raise RetrievalParameterError(
                format_actionable(
                    group=description.name,
                    problem=(
                        '["*"] is the only valid wildcard form; '
                        'mixed selections such as ["*", "feature_name"] are rejected'
                    ),
                    next_step='use select=["*"] to select all features or name specific features',
                )
            )
        return [f.name for f in description.features]

    # Explicit name list: each name must be a declared feature field.
    declared = {f.name for f in description.features}
    for name in select:
        if not isinstance(name, str):
            raise RetrievalParameterError(
                format_actionable(
                    group=description.name,
                    problem=f"select item {name!r} is not a string; all items must be feature field names",
                    next_step="pass a list of string feature field names",
                )
            )
        if name not in declared:
            raise RetrievalParameterError(
                format_actionable(
                    group=description.name,
                    field=name,
                    problem=f"'{name}' is not a declared feature field of group '{description.name}'",
                    next_step=f"valid feature fields are: {sorted(declared)}",
                )
            )
    return list(select)


def _build_timestamp_filter(
    where: dict[str, dict[str, Any]] | None,
    event_timestamp_name: str,
    group_name: str,
) -> TimestampFilter | None:
    """Validate and convert the where parameter to a TimestampFilter.

    Accepts None (no filter) or {event_timestamp_name: {op: datetime}}.
    Rejects filters on other fields, unsupported operators, and non-datetime
    values.  Returns None when where is None.
    """
    if where is None:
        return None

    if not isinstance(where, dict) or len(where) != 1:
        raise RetrievalParameterError(
            format_actionable(
                group=group_name,
                problem="where must be a dict with exactly one key (the event timestamp column name)",
                next_step=f"use where={{'{event_timestamp_name}': {{'gte': ..., 'lte': ...}}}}",
            )
        )

    field_name = next(iter(where))
    if field_name != event_timestamp_name:
        raise RetrievalParameterError(
            format_actionable(
                group=group_name,
                field=field_name,
                problem=(
                    f"where filter on '{field_name}' is not supported; "
                    f"only the event timestamp column '{event_timestamp_name}' can be filtered"
                ),
                next_step=f"use where={{'{event_timestamp_name}': {{'gte': ..., 'lte': ...}}}}",
            )
        )

    ops = where[field_name]
    if not isinstance(ops, dict) or not ops:
        raise RetrievalParameterError(
            format_actionable(
                group=group_name,
                field=field_name,
                problem="where operators must be a non-empty dict with keys in {gt, gte, lt, lte}",
                next_step=f"use where={{'{event_timestamp_name}': {{'gte': datetime_value, 'lte': datetime_value}}}}",
            )
        )

    for op, val in ops.items():
        if op not in _ALLOWED_WHERE_OPS:
            raise RetrievalParameterError(
                format_actionable(
                    group=group_name,
                    field=field_name,
                    problem=f"unsupported operator '{op}'; supported operators are {sorted(_ALLOWED_WHERE_OPS)}",
                    next_step="use 'gt', 'gte', 'lt', or 'lte' as the operator",
                )
            )
        if not isinstance(val, datetime):
            raise RetrievalParameterError(
                format_actionable(
                    group=group_name,
                    field=field_name,
                    problem=f"where value for operator '{op}' must be a datetime.datetime, got {type(val).__name__}",
                    next_step="pass datetime.datetime values in where filters",
                )
            )

    return TimestampFilter(
        gt=ops.get("gt"),
        gte=ops.get("gte"),
        lt=ops.get("lt"),
        lte=ops.get("lte"),
    )


def _structural_columns(description: FeatureGroupDescription) -> list[str]:
    """Return the names of structural columns in output order.

    Order: entity key, event timestamp, then join keys in registry order.
    Structural columns are always included in historical retrieval output.
    """
    cols = [description.entity_key.name, description.event_timestamp.name]
    for jk in description.join_keys:
        cols.append(jk.name)
    return cols


def _selected_description(
    description: FeatureGroupDescription,
    selected_feature_names: list[str],
) -> FeatureGroupDescription:
    """Return a description containing only the selected feature fields.

    Used so validate_dataframe checks only the feature columns that are
    actually present in the projected retrieval result, not the full set.
    """
    selected_set = set(selected_feature_names)
    selected_features = [f for f in description.features if f.name in selected_set]
    return replace(description, features=selected_features)


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


_ONLINE_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _build_online_entity_lookup(
    where: dict[str, dict[str, Any]] | None,
    description: FeatureGroupDescription,
) -> str | int:
    """Validate the online where filter and return the entity key value.

    Requires:
    - where is a non-None dict with exactly one entry.
    - the key equals the group's registered entity key name.
    - the operator mapping contains exactly the key "eq".
    - the value is type-compatible with the entity key dtype.

    Returns the entity key value as a Python str or int.

    Raises:
        RetrievalParameterError: Any validation failure.
    """
    group_name = description.name
    ek_name = description.entity_key.name
    ek_dtype = description.entity_key.dtype

    if where is None:
        raise RetrievalParameterError(
            format_actionable(
                group=group_name,
                problem="where is required for online retrieval",
                next_step=f'pass where={{"{ek_name}": {{"eq": <value>}}}}',
            )
        )
    if not isinstance(where, dict) or len(where) != 1:
        raise RetrievalParameterError(
            format_actionable(
                group=group_name,
                problem="where must be a dict with exactly one entry keyed by the entity key field name",
                next_step=f'pass where={{"{ek_name}": {{"eq": <value>}}}}',
            )
        )
    field_name = next(iter(where))
    if field_name != ek_name:
        raise RetrievalParameterError(
            format_actionable(
                group=group_name,
                field=field_name,
                problem=(
                    f"where filter on '{field_name}' is not supported; "
                    f"online retrieval only accepts the entity key '{ek_name}' as the filter field"
                ),
                next_step=f'use where={{"{ek_name}": {{"eq": <value>}}}}',
            )
        )
    ops = where[field_name]
    if not isinstance(ops, dict):
        raise RetrievalParameterError(
            format_actionable(
                group=group_name,
                field=field_name,
                problem="the operator mapping for the entity key must be a non-empty dict",
                next_step=f'use where={{"{ek_name}": {{"eq": <value>}}}}',
            )
        )
    if set(ops.keys()) != {"eq"}:
        raise RetrievalParameterError(
            format_actionable(
                group=group_name,
                field=field_name,
                problem=(f"the only accepted online filter operator is 'eq'; got {sorted(ops.keys())}"),
                next_step=f'use where={{"{ek_name}": {{"eq": <value>}}}}',
            )
        )
    value = ops["eq"]
    if not _is_entity_key_value_compatible(value, ek_dtype):
        raise RetrievalParameterError(
            format_actionable(
                group=group_name,
                field=field_name,
                problem=(f"where value {value!r} is not type-compatible with entity key dtype {ek_dtype.value}"),
                next_step=f"pass a single {ek_dtype.value.lower()} literal for '{ek_name}'",
            )
        )
    return value  # type: ignore[return-value]


def _is_entity_key_value_compatible(value: Any, dtype: Any) -> bool:
    """Return True when value is a Python type compatible with the entity key dtype.

    Entity keys may only be INTEGER or STRING (per CON-004 and FR-DEF-002).
    bool is rejected for INTEGER because isinstance(True, int) would otherwise
    pass silently.
    """
    from kitefs.enums import FeatureType

    if dtype == FeatureType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if dtype == FeatureType.STRING:
        return isinstance(value, str)
    return False


def _coerce_online_result(
    raw: dict[str, Any],
    description: FeatureGroupDescription,
) -> dict[str, Any]:
    """Convert raw SQLite values to standard Python types.

    Datetime columns are serialized as ISO-8601 UTC strings in the online store.
    This function parses those strings back to UTC-aware datetime.datetime objects.
    All other column types pass through unchanged.
    """
    from kitefs.enums import FeatureType

    dtype_map: dict[str, Any] = {
        description.event_timestamp.name: description.event_timestamp.dtype,
    }
    for feat in description.features:
        dtype_map[feat.name] = feat.dtype
    for jk in description.join_keys:
        dtype_map[jk.name] = jk.dtype

    result: dict[str, Any] = {}
    for key, value in raw.items():
        if value is not None and dtype_map.get(key) == FeatureType.DATETIME and isinstance(value, str):
            result[key] = datetime.strptime(value, _ONLINE_DATETIME_FMT).replace(tzinfo=UTC)
        else:
            result[key] = value
    return result
