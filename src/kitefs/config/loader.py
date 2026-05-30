"""Private config-loading helpers for kitefs.

Implements the loading sequence:
  1. Require ./kitefs.yaml in root
  2. Parse YAML
  3. Validate fixed-literal type fields (before interpolation)
  4. Interpolate ${VAR} and ${VAR:-default} expressions
  5. Apply KITEFS_RUNTIME_TARGET env override
  6. Validate required fields and runtime target
  7. Return RuntimeConfig
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from kitefs.errors import ConfigurationError, format_actionable

_INTERP_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?}")
_REGISTRY_TYPES: frozenset[str] = frozenset({"aws_s3"})
_OFFLINE_TYPES: frozenset[str] = frozenset({"aws_s3"})
_ONLINE_TYPES: frozenset[str] = frozenset({"aws_dynamodb"})


@dataclass(frozen=True)
class RuntimeConfig:
    """Resolved configuration consumed by the provider factory and SDK."""

    version: int
    project_name: str
    target: Literal["local", "remote"]
    # Raw resolved remote section; typed further in later features.
    remote: dict[str, Any] | None


def load_runtime_config(root: Path) -> RuntimeConfig:
    """Load, validate, interpolate, and return the resolved config from root/kitefs.yaml."""
    path = _require_config_file(root)
    raw = _parse_yaml(path)
    _validate_fixed_literals(raw)
    resolved = _interpolate(raw)
    _apply_runtime_override(resolved)
    return _validate_and_build(resolved)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _require_config_file(root: Path) -> Path:
    path = root / "kitefs.yaml"
    if not path.exists():
        raise ConfigurationError(
            format_actionable(
                problem="kitefs.yaml not found in current directory",
                next_step="run 'kitefs init' to create a project",
            )
        )
    return path


def _parse_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            format_actionable(
                setting=str(path),
                problem=f"YAML parse error: {exc}",
                next_step="fix the syntax in kitefs.yaml",
            )
        ) from exc
    if not isinstance(data, dict):
        raise ConfigurationError(
            format_actionable(
                setting=str(path),
                problem="YAML root must be a mapping",
                next_step="ensure kitefs.yaml contains a valid YAML mapping",
            )
        )
    return data  # type: ignore[return-value]


def _check_fixed_literal(value: Any, setting: str, allowed: frozenset[str]) -> None:
    """Raise ConfigurationError when value is not a bare literal from allowed."""
    if isinstance(value, str) and value.startswith("${"):
        raise ConfigurationError(
            format_actionable(
                setting=setting,
                problem=f"interpolation expressions are not allowed in fixed-type fields (got {value!r})",
                next_step=f"set it to one of: {', '.join(sorted(allowed))}",
            )
        )
    if value not in allowed:
        raise ConfigurationError(
            format_actionable(
                setting=setting,
                problem=f"unsupported value {value!r}; must be one of: {', '.join(sorted(allowed))}",
                next_step=f"set it to one of: {', '.join(sorted(allowed))}",
            )
        )


def _validate_fixed_literals(raw: dict[str, Any]) -> None:
    """Validate remote store type fields before interpolation."""
    remote = raw.get("remote")
    if not isinstance(remote, dict):
        return

    registry = remote.get("registry")
    if isinstance(registry, dict) and "type" in registry:
        _check_fixed_literal(registry["type"], "remote.registry.type", _REGISTRY_TYPES)

    offline = remote.get("offline_store")
    if isinstance(offline, dict) and "type" in offline:
        _check_fixed_literal(offline["type"], "remote.offline_store.type", _OFFLINE_TYPES)

    online = remote.get("online_store")
    if isinstance(online, dict) and "type" in online:
        _check_fixed_literal(online["type"], "remote.online_store.type", _ONLINE_TYPES)


def _interpolate_string(s: str) -> str:
    def _replace(m: re.Match[str]) -> str:
        var_name = m.group(1)
        default = m.group(2)  # None when no :- clause
        val = os.environ.get(var_name)
        if default is not None:
            # ${VAR:-default}: use default when var is unset or empty, per bash semantics.
            return val or default
        # ${VAR} without default: resolve to empty string when unset.
        return val if val is not None else ""

    return _INTERP_RE.sub(_replace, s)


def _interpolate(data: Any) -> Any:
    """Recursively replace ${VAR} and ${VAR:-default} in all string values."""
    if isinstance(data, str):
        return _interpolate_string(data)
    if isinstance(data, dict):
        return {k: _interpolate(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_interpolate(item) for item in data]
    return data


def _apply_runtime_override(resolved: dict[str, Any]) -> None:
    """If KITEFS_RUNTIME_TARGET is set, overwrite runtime.target after interpolation."""
    override = os.environ.get("KITEFS_RUNTIME_TARGET")
    if override is not None:
        if not isinstance(resolved.get("runtime"), dict):
            resolved["runtime"] = {}
        resolved["runtime"]["target"] = override


def _validate_and_build(resolved: dict[str, Any]) -> RuntimeConfig:
    """Validate required fields and return a RuntimeConfig."""
    if resolved.get("version") is None:
        raise ConfigurationError(
            format_actionable(
                setting="version",
                problem="required field is missing",
                next_step="add 'version: 1' to kitefs.yaml",
            )
        )

    project = resolved.get("project") or {}
    if not project.get("name"):
        raise ConfigurationError(
            format_actionable(
                setting="project.name",
                problem="required field is missing",
                next_step="add a 'project.name' value to kitefs.yaml",
            )
        )

    runtime = resolved.get("runtime") or {}
    target = runtime.get("target")
    if not target:
        raise ConfigurationError(
            format_actionable(
                setting="runtime.target",
                problem="required field is missing",
                next_step="set runtime.target to 'local' or 'remote'",
            )
        )

    if target not in ("local", "remote"):
        raise ConfigurationError(
            format_actionable(
                setting="runtime.target",
                problem=f"unsupported value {target!r}; must be one of: local, remote",
                next_step="set runtime.target to 'local' or 'remote'",
            )
        )

    if target == "remote" and not isinstance(resolved.get("remote"), dict):
        raise ConfigurationError(
            format_actionable(
                setting="remote",
                problem="required section is missing for runtime.target 'remote'",
                next_step="add a remote section to kitefs.yaml or set runtime.target to 'local'",
            )
        )

    return RuntimeConfig(
        version=int(resolved["version"]),
        project_name=str(project["name"]),
        target=target,  # type: ignore[arg-type]
        remote=resolved.get("remote") if isinstance(resolved.get("remote"), dict) else None,
    )
