"""Cross-definition validation: checks the full discovered set as a single unit."""

from __future__ import annotations

import re
from collections import Counter

from kitefs.definitions import FeatureGroup
from kitefs.enums import FeatureType
from kitefs.errors import DefinitionValidationError, format_actionable

_RESERVED_NAMES = frozenset({"year", "month"})
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_ENTITY_KEY_DTYPES = frozenset({FeatureType.STRING, FeatureType.INTEGER})
_EVENT_TS_DTYPES = frozenset({FeatureType.DATETIME})
_JOIN_KEY_DTYPES = frozenset({FeatureType.STRING, FeatureType.INTEGER})


def validate_cross_definition(groups: list[FeatureGroup]) -> None:
    """Validate the discovered set of FeatureGroups as a whole. Aggregates all failures.

    Raises DefinitionValidationError with every violation if any are found.
    """
    errors: list[str] = []
    known_names = {g.name for g in groups}

    # -------- Defensive per-group structural checks --------
    # Re-validate invariants that constructors normally enforce, catching
    # corruption or post-construction mutation before the registry is written.
    for group in groups:
        if not _IDENTIFIER_RE.match(group.name):
            errors.append(
                format_actionable(
                    group=group.name,
                    problem=f"FeatureGroup name '{group.name}' must be a valid identifier",
                    next_step="use a name matching ^[a-zA-Z_][a-zA-Z0-9_]*$",
                )
            )

        if not group.features:
            errors.append(
                format_actionable(
                    group=group.name,
                    problem="FeatureGroup must have at least one feature",
                    next_step="add at least one Feature to the features list",
                )
            )

        if len(group.join_keys) > 1:
            errors.append(
                format_actionable(
                    group=group.name,
                    problem=f"FeatureGroup may have at most one join_key, got {len(group.join_keys)}",
                    next_step="reduce join_keys to one entry or remove it",
                )
            )

        ek_dtype = group.entity_key.dtype
        if not isinstance(ek_dtype, FeatureType) or ek_dtype not in _ENTITY_KEY_DTYPES:
            label = ek_dtype.value if isinstance(ek_dtype, FeatureType) else repr(ek_dtype)
            errors.append(
                format_actionable(
                    group=group.name,
                    field=group.entity_key.name,
                    problem=f"EntityKey dtype must be STRING or INTEGER, got {label}",
                    next_step="use one of STRING, INTEGER",
                )
            )

        et_dtype = group.event_timestamp.dtype
        if not isinstance(et_dtype, FeatureType) or et_dtype not in _EVENT_TS_DTYPES:
            label = et_dtype.value if isinstance(et_dtype, FeatureType) else repr(et_dtype)
            errors.append(
                format_actionable(
                    group=group.name,
                    field=group.event_timestamp.name,
                    problem=f"EventTimestamp dtype must be DATETIME, got {label}",
                    next_step="use DATETIME or omit dtype (defaults to DATETIME)",
                )
            )

        for feature in group.features:
            if not isinstance(feature.dtype, FeatureType):
                errors.append(
                    format_actionable(
                        group=group.name,
                        field=feature.name,
                        problem=f"Feature dtype must be a FeatureType, got {feature.dtype!r}",
                        next_step="use one of FeatureType.STRING, .INTEGER, .FLOAT, .DATETIME",
                    )
                )

        for jk in group.join_keys:
            jk_dtype = jk.dtype
            if not isinstance(jk_dtype, FeatureType) or jk_dtype not in _JOIN_KEY_DTYPES:
                label = jk_dtype.value if isinstance(jk_dtype, FeatureType) else repr(jk_dtype)
                errors.append(
                    format_actionable(
                        group=group.name,
                        field=jk.name,
                        problem=f"JoinKey dtype must be STRING or INTEGER, got {label}",
                        next_step="use one of STRING, INTEGER",
                    )
                )

        all_field_names = [
            group.entity_key.name,
            group.event_timestamp.name,
            *(jk.name for jk in group.join_keys),
            *(f.name for f in group.features),
        ]
        seen_names: set[str] = set()
        for field_name in all_field_names:
            if not _IDENTIFIER_RE.match(field_name):
                errors.append(
                    format_actionable(
                        group=group.name,
                        field=field_name,
                        problem=f"field name '{field_name}' must be a valid identifier",
                        next_step="use a name matching ^[a-zA-Z_][a-zA-Z0-9_]*$",
                    )
                )
            if field_name in seen_names:
                errors.append(
                    format_actionable(
                        group=group.name,
                        field=field_name,
                        problem=f"duplicate field name '{field_name}' in FeatureGroup",
                        next_step=(
                            "ensure all field names (entity key, event timestamp, join keys, features) are unique"
                        ),
                    )
                )
            seen_names.add(field_name)

    name_counts = Counter(g.name for g in groups)
    for name, count in sorted(name_counts.items()):
        if count > 1:
            errors.append(
                format_actionable(
                    group=name,
                    problem=f"duplicate group name '{name}' found in {count} definition files",
                    next_step="ensure each FeatureGroup has a unique name across all definition files",
                )
            )

    for group in groups:
        all_fields = [
            group.entity_key,
            group.event_timestamp,
            *group.join_keys,
            *group.features,
        ]
        for field in all_fields:
            if field.name in _RESERVED_NAMES:
                errors.append(
                    format_actionable(
                        group=group.name,
                        field=field.name,
                        problem=f"field name '{field.name}' is reserved (used as a Hive partition column)",
                        next_step="rename the field to something other than 'year' or 'month'",
                    )
                )

    for group in groups:
        for jk in group.join_keys:
            if jk.referenced_group not in known_names:
                errors.append(
                    format_actionable(
                        group=group.name,
                        field=jk.name,
                        problem=(f"JoinKey referenced_group '{jk.referenced_group}' is not in the discovered set"),
                        next_step=(f"add a definition file that declares a FeatureGroup named '{jk.referenced_group}'"),
                    )
                )
            else:
                target = next(g for g in groups if g.name == jk.referenced_group)
                if jk.dtype != target.entity_key.dtype:
                    jk_label = jk.dtype.value if isinstance(jk.dtype, FeatureType) else repr(jk.dtype)
                    ek = target.entity_key.dtype
                    ek_label = ek.value if isinstance(ek, FeatureType) else repr(ek)
                    errors.append(
                        format_actionable(
                            group=group.name,
                            field=jk.name,
                            problem=(
                                f"JoinKey dtype {jk_label!r} does not match "
                                f"'{jk.referenced_group}' entity_key dtype "
                                f"{ek_label!r}"
                            ),
                            next_step=(f"set JoinKey dtype to {ek_label!r} to match '{jk.referenced_group}'"),
                        )
                    )

    if errors:
        raise DefinitionValidationError("\n".join(errors))


__all__ = ["validate_cross_definition"]
