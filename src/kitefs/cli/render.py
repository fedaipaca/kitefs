"""Presentation helpers for the list and describe CLI commands.

All functions are pure: they receive typed result objects and return strings.
No I/O, no SDK calls, no Click references.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kitefs.sdk.results import FeatureGroupDescription, FeatureGroupSummary

# Re-use the single datetime format string from the serializer.
_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def render_list(summaries: list[FeatureGroupSummary], *, as_json: bool) -> str:
    """Render a list of FeatureGroupSummary values as a human table or JSON array."""
    if as_json:
        return _render_list_json(summaries)
    return _render_list_text(summaries)


def _render_list_text(summaries: list[FeatureGroupSummary]) -> str:
    if not summaries:
        return "No feature groups registered."

    rows = [(s.name, s.owner or "", s.entity_key, s.storage_target.value, str(s.feature_count)) for s in summaries]
    headers = ("NAME", "OWNER", "ENTITY KEY", "STORAGE TARGET", "FEATURES")
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]

    def fmt_row(cells: tuple[str, ...]) -> str:
        return "  ".join(c.ljust(widths[i]) for i, c in enumerate(cells)).rstrip()

    lines = [fmt_row(headers), fmt_row(tuple("-" * w for w in widths))]
    lines.extend(fmt_row(row) for row in rows)
    return "\n".join(lines)


def _render_list_json(summaries: list[FeatureGroupSummary]) -> str:
    if not summaries:
        return "[]"
    items = [
        {
            "name": s.name,
            "owner": s.owner,
            "description": s.description,
            "entity_key": s.entity_key,
            "storage_target": s.storage_target.value,
            "feature_count": s.feature_count,
        }
        for s in summaries
    ]
    return json.dumps(items, indent=2)


# ---------------------------------------------------------------------------
# describe
# ---------------------------------------------------------------------------


def render_describe(description: FeatureGroupDescription, *, as_json: bool) -> str:
    """Render a FeatureGroupDescription as human-readable text or a JSON registry entry."""
    if as_json:
        return json.dumps(_description_to_entry(description), indent=2, sort_keys=True)
    return _render_describe_text(description)


def _fmt_dt(dt: Any) -> str:
    """Format a datetime or return 'none'."""
    if dt is None:
        return "none"
    return dt.strftime(_DATETIME_FMT)


def _render_describe_text(desc: FeatureGroupDescription) -> str:
    lines: list[str] = []

    lines.append(f"Name:             {desc.name}")
    lines.append(f"Storage target:   {desc.storage_target.value}")
    lines.append(f"Applied at:       {_fmt_dt(desc.applied_at)}")
    lines.append(f"Materialized at:  {_fmt_dt(desc.last_materialized_at)}")
    lines.append("")

    ek = desc.entity_key
    lines.append(f"Entity key:       {ek.name} ({ek.dtype.value})")

    et = desc.event_timestamp
    lines.append(f"Event timestamp:  {et.name} ({et.dtype.value})")
    lines.append("")

    lines.append(f"Features ({len(desc.features)}):")
    for f in desc.features:
        expect_str = _fmt_expect(f.expect)
        suffix = f"  [{expect_str}]" if expect_str else ""
        lines.append(f"  {f.name}  {f.dtype.value}{suffix}")

    if desc.join_keys:
        lines.append("")
        lines.append(f"Join keys ({len(desc.join_keys)}):")
        for jk in desc.join_keys:
            lines.append(f"  {jk.name} ({jk.dtype.value}) → {jk.referenced_group}")
    else:
        lines.append("")
        lines.append("Join keys:        none")

    lines.append("")
    lines.append("Validation:")
    lines.append(f"  ingestion:           {desc.ingestion_validation.value}")
    lines.append(f"  offline_retrieval:   {desc.offline_retrieval_validation.value}")

    meta = desc.metadata
    lines.append("")
    lines.append("Metadata:")
    if meta.owner:
        lines.append(f"  owner:   {meta.owner}")
    if meta.description:
        lines.append(f"  description:   {meta.description}")
    if meta.tags:
        lines.append(f"  tags:    {meta.tags}")

    return "\n".join(lines)


def _fmt_expect(expect: list[dict[str, Any]] | None) -> str:
    """Format an expect constraint list into a short readable string."""
    if not expect:
        return ""
    parts = []
    for c in expect:
        t = c["type"]
        if t == "not_null":
            parts.append("not_null")
        elif t == "is_in":
            parts.append(f"is_in({c['value']!r})")
        else:
            parts.append(f"{t}({c['value']})")
    return ", ".join(parts)


def _description_to_entry(desc: FeatureGroupDescription) -> dict[str, Any]:
    """Reconstruct the on-disk registry entry shape from a FeatureGroupDescription.

    Mirrors _serialize_feature_group in serializer.py so the JSON output of
    'kitefs describe --format json' matches the persisted registry.json entry.
    """

    def fmt_dt(dt: Any) -> str | None:
        return dt.strftime(_DATETIME_FMT) if dt is not None else None

    return {
        "applied_at": fmt_dt(desc.applied_at),
        "entity_key": {
            "description": desc.entity_key.description,
            "dtype": desc.entity_key.dtype.value,
            "name": desc.entity_key.name,
        },
        "event_timestamp": {
            "description": desc.event_timestamp.description,
            "dtype": desc.event_timestamp.dtype.value,
            "name": desc.event_timestamp.name,
        },
        "features": [
            {
                "description": f.description,
                "dtype": f.dtype.value,
                "expect": f.expect,
                "name": f.name,
            }
            for f in desc.features
        ],
        "ingestion_validation": desc.ingestion_validation.value,
        "join_keys": [
            {
                "dtype": jk.dtype.value,
                "name": jk.name,
                "referenced_group": jk.referenced_group,
            }
            for jk in desc.join_keys
        ],
        "last_materialized_at": fmt_dt(desc.last_materialized_at),
        "metadata": {
            "description": desc.metadata.description,
            "owner": desc.metadata.owner,
            "tags": desc.metadata.tags,
        },
        "name": desc.name,
        "offline_retrieval_validation": desc.offline_retrieval_validation.value,
        "storage_target": desc.storage_target.value,
    }


__all__ = ["render_describe", "render_list"]
