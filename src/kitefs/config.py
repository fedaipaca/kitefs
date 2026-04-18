"""Configuration manager — loads, validates, and exposes kitefs.yaml settings."""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from kitefs.exceptions import ConfigurationError

_SUPPORTED_PROVIDERS = ("local", "aws")

_ENV_OVERRIDES: dict[str, str] = {
    "KITEFS_PROVIDER": "provider",
    "KITEFS_STORAGE_ROOT": "storage_root",
}

_ENV_AWS_OVERRIDES: dict[str, str] = {
    "KITEFS_AWS_S3_BUCKET": "s3_bucket",
    "KITEFS_AWS_S3_PREFIX": "s3_prefix",
    "KITEFS_AWS_DYNAMODB_TABLE_PREFIX": "dynamodb_table_prefix",
}

_REQUIRED_AWS_FIELDS = ("s3_bucket", "s3_prefix", "dynamodb_table_prefix")


@dataclass(frozen=True)
class AWSConfig:
    """AWS-specific configuration for S3 and DynamoDB access."""

    s3_bucket: str
    s3_prefix: str
    dynamodb_table_prefix: str


@dataclass(frozen=True)
class Config:
    """Validated, immutable configuration loaded from kitefs.yaml."""

    provider: str
    project_root: Path
    storage_root: Path
    definitions_path: Path
    aws: AWSConfig | None


def load_config(project_root: Path) -> Config:
    """Load and validate kitefs.yaml from the given project root.

    Environment variables take precedence over file values.
    All validation errors are collected before raising.
    """
    project_root = project_root.resolve()
    config_path = project_root / "kitefs.yaml"

    raw = _read_yaml(config_path)
    env_origins = _apply_env_overrides(raw)
    _validate(raw, config_path, env_origins)

    storage_root = (project_root / raw["storage_root"]).resolve()

    aws_config: AWSConfig | None = None
    if raw["provider"] == "aws":
        aws_section = raw.get("aws", {}) or {}
        aws_config = AWSConfig(
            s3_bucket=aws_section["s3_bucket"],
            s3_prefix=aws_section["s3_prefix"],
            dynamodb_table_prefix=aws_section["dynamodb_table_prefix"],
        )

    return Config(
        provider=raw["provider"],
        project_root=project_root,
        storage_root=storage_root,
        definitions_path=storage_root / "definitions",
        aws=aws_config,
    )


def _read_yaml(config_path: Path) -> dict:
    """Read and parse kitefs.yaml, raising ConfigurationError on failure."""
    if not config_path.exists():
        raise ConfigurationError(
            f"No configuration file found at '{config_path}'. Run `kitefs init` to create a project."
        )
    try:
        text = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Malformed YAML in '{config_path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigurationError(
            f"Expected a YAML mapping in '{config_path}', got {type(data).__name__}. "
            "The file must contain key-value pairs (e.g., 'provider: local')."
        )
    return data


def _apply_env_overrides(raw: dict) -> dict[str, str]:
    """Apply environment variable overrides to the raw config dict.

    Returns a mapping of config field path (e.g. 'provider', 'aws.s3_bucket') to
    the env var name that provided the value, for use in actionable error messages.
    """
    origins: dict[str, str] = {}

    for env_var, field in _ENV_OVERRIDES.items():
        value = os.environ.get(env_var)
        if value is not None:
            raw[field] = value
            origins[field] = env_var

    for env_var, field in _ENV_AWS_OVERRIDES.items():
        value = os.environ.get(env_var)
        if value is not None:
            raw.setdefault("aws", {})
            if raw["aws"] is None:
                raw["aws"] = {}
            raw["aws"][field] = value
            origins[f"aws.{field}"] = env_var

    return origins


def _validate(raw: dict, config_path: Path, env_origins: dict[str, str]) -> None:
    """Validate all config fields, collecting all errors before raising."""
    errors: list[str] = []

    # --- provider ---
    provider = raw.get("provider")
    if provider is None:
        errors.append(f"Missing required field: 'provider' in {config_path}")
    elif provider not in _SUPPORTED_PROVIDERS:
        source = f" (set by environment variable {env_origins['provider']})" if "provider" in env_origins else ""
        errors.append(f"Unsupported provider: '{provider}'{source}. Supported: {', '.join(_SUPPORTED_PROVIDERS)}")

    # --- storage_root ---
    storage_root = raw.get("storage_root")
    if storage_root is None:
        errors.append(f"Missing required field: 'storage_root' in {config_path}")
    elif not isinstance(storage_root, str):
        env_var = env_origins.get("storage_root")
        source = f" (set by environment variable {env_var})" if env_var else ""
        errors.append(
            f"Invalid 'storage_root' value{source}: expected a string path, got {type(storage_root).__name__}"
        )
    elif not storage_root.strip():
        env_var = env_origins.get("storage_root")
        source = f" (set by environment variable {env_var})" if env_var else ""
        errors.append(
            f"Invalid 'storage_root' value{source}: path must not be empty. "
            "Set a relative path such as './feature_store/'."
        )

    # --- AWS fields (only when provider is aws) ---
    if provider == "aws":
        aws_section = raw.get("aws", {}) or {}
        missing_aws = [f for f in _REQUIRED_AWS_FIELDS if not aws_section.get(f)]
        if missing_aws:
            formatted = ", ".join(f"'aws.{f}'" for f in missing_aws)
            errors.append(f"Missing required AWS fields when provider is 'aws': {formatted}")

    if errors:
        joined = "; ".join(errors)
        raise ConfigurationError(f"Invalid configuration in '{config_path}': {joined}")
