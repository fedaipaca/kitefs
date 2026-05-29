"""Cross-definition validation: checks the full discovered set as a single unit."""

from __future__ import annotations

from collections import Counter

from kitefs.definitions import FeatureGroup
from kitefs.errors import DefinitionValidationError, format_actionable

_RESERVED_NAMES = frozenset({"year", "month"})


def validate_cross_definition(groups: list[FeatureGroup]) -> None:
    """Validate the discovered set of FeatureGroups as a whole. Aggregates all failures.

    Raises DefinitionValidationError with every violation if any are found.
    """
    errors: list[str] = []
    known_names = {g.name for g in groups}

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
                    errors.append(
                        format_actionable(
                            group=group.name,
                            field=jk.name,
                            problem=(
                                f"JoinKey dtype {jk.dtype.value!r} does not match "
                                f"'{jk.referenced_group}' entity_key dtype "
                                f"{target.entity_key.dtype.value!r}"
                            ),
                            next_step=(
                                f"set JoinKey dtype to {target.entity_key.dtype.value!r} "
                                f"to match '{jk.referenced_group}'"
                            ),
                        )
                    )

    if errors:
        raise DefinitionValidationError("\n".join(errors))


__all__ = ["validate_cross_definition"]
