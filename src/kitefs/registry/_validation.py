"""Definition validation — structural checks for FeatureGroup definitions."""

from collections import Counter

from kitefs.definitions import FeatureGroup, FeatureType


def _validate_definitions(groups: list[FeatureGroup]) -> list[str]:
    """Check a list of feature group definitions against all structural rules.

    Returns a list of error message strings. An empty list means all definitions
    are valid. Collects **all** errors before returning — never fails on the
    first error alone.

    Validation runs in two phases:
    1. Individual group validation (per-group structural checks).
    2. Cross-group validation (uniqueness and join key integrity).
    """
    errors: list[str] = []

    # --- Phase 1: Individual group validation ---
    for group in groups:
        _validate_group(group, errors)

    # --- Phase 2: Cross-group validation ---
    _validate_cross_group(groups, errors)

    return errors


def _validate_group(group: FeatureGroup, errors: list[str]) -> None:
    """Run per-group structural checks, appending any errors found."""
    # EventTimestamp dtype must be DATETIME.
    if group.event_timestamp.dtype != FeatureType.DATETIME:
        errors.append(
            f"Group '{group.name}': EventTimestamp field '{group.event_timestamp.name}' "
            f"must have dtype DATETIME, got {group.event_timestamp.dtype.value}."
        )

    # Feature dtype must be a FeatureType member.
    for feature in group.features:
        if not isinstance(feature.dtype, FeatureType):
            errors.append(
                f"Group '{group.name}': Feature '{feature.name}' has invalid dtype "
                f"'{feature.dtype}'. Supported: STRING, INTEGER, FLOAT, DATETIME."
            )

    # Field names must be unique across entity_key, event_timestamp, and features.
    all_names: list[str] = [
        group.entity_key.name,
        group.event_timestamp.name,
        *(f.name for f in group.features),
    ]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in all_names:
        if name in seen:
            duplicates.add(name)
        seen.add(name)
    for dup in sorted(duplicates):
        errors.append(
            f"Group '{group.name}': Duplicate field name '{dup}' found across "
            "entity_key, event_timestamp, and features."
        )


def _validate_cross_group(groups: list[FeatureGroup], errors: list[str]) -> None:
    """Run cross-group validation checks, appending any errors found."""
    # Duplicate feature group names.
    name_counts = Counter(g.name for g in groups)
    for name, count in sorted(name_counts.items()):
        if count > 1:
            errors.append(f"Duplicate feature group name '{name}' found {count} times.")

    # When names are duplicated, the last group wins — acceptable because
    # duplicate names are already caught above.
    group_map: dict[str, FeatureGroup] = {g.name: g for g in groups}

    for group in groups:
        for join_key in group.join_keys:
            ref_name = join_key.referenced_group

            # Referenced group must exist.
            if ref_name not in group_map:
                errors.append(f"Group '{group.name}': Join key references non-existent group '{ref_name}'.")
                continue

            ref_group = group_map[ref_name]

            # Join key field_name must match the referenced group's entity_key.name.
            if join_key.field_name != ref_group.entity_key.name:
                errors.append(
                    f"Group '{group.name}': Join key field '{join_key.field_name}' "
                    f"must match entity key name '{ref_group.entity_key.name}' of "
                    f"referenced group '{ref_name}'. Rename the field to "
                    f"'{ref_group.entity_key.name}'."
                )

            # Join key field must exist in the base group.
            base_field_dtype = _find_field_dtype(group, join_key.field_name)
            if base_field_dtype is None:
                errors.append(
                    f"Group '{group.name}': Join key field '{join_key.field_name}' "
                    f"does not exist as an entity_key or feature in this group."
                )
                continue

            # Join key type compatibility: the field in the base group must have
            # the same dtype as the referenced group's entity key.
            ref_ek_dtype = ref_group.entity_key.dtype
            if base_field_dtype != ref_ek_dtype:
                errors.append(
                    f"Group '{group.name}': Join key field '{join_key.field_name}' "
                    f"has dtype {base_field_dtype.value} but entity key "
                    f"'{ref_group.entity_key.name}' of referenced group "
                    f"'{ref_name}' has dtype {ref_ek_dtype.value}."
                )


def _find_field_dtype(group: FeatureGroup, field_name: str) -> FeatureType | None:
    """Look up a field's dtype in a group by checking entity_key then features."""
    if group.entity_key.name == field_name:
        return group.entity_key.dtype
    for feature in group.features:
        if feature.name == field_name:
            return feature.dtype
    return None
