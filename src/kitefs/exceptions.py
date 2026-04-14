"""Exception hierarchy for KiteFS — all user-facing errors raised by the SDK and CLI."""


class KiteFSError(Exception):
    """Base exception for all KiteFS errors.

    Catch this for a broad handler, or catch specific subclasses for targeted handling.
    All subclasses carry an actionable message: what went wrong, what caused it,
    and how to fix it (NFR-UX-001).
    """

    def __init__(self, message: str) -> None:
        """Initialise with an actionable error message."""
        super().__init__(message)


class ConfigurationError(KiteFSError):
    """Raised when kitefs.yaml is missing, malformed, or contains invalid values.

    Raised by BB-10 in FeatureStore.__init__() when the config file cannot be
    loaded or fails field validation (missing required fields, unsupported provider,
    missing AWS credentials, etc).
    """


class DefinitionError(KiteFSError):
    """Raised when feature group definitions are structurally invalid.

    Raised by BB-04 in apply(). Collects all errors before raising — never
    fails on the first error alone (KTD-9). The message includes every issue
    so users can fix them all in one pass.
    """


class RegistryError(KiteFSError):
    """Raised when the registry file is unavailable or its contents are corrupted.

    Raised by BB-04 when registry.json cannot be found or its JSON is malformed.
    Should not occur in a correctly initialised project (kitefs init seeds the file).
    """


class FeatureGroupNotFoundError(KiteFSError):
    """Raised when a referenced feature group does not exist in the registry.

    Raised by BB-02 (via BB-04) in ingest(), get_historical_features(),
    get_online_features(), materialize(), and describe_feature_group() when
    the named group is absent from registry.json.
    """


class ValidationError(KiteFSError):
    """Base class for validation failures.

    Not raised directly — raise SchemaValidationError or DataValidationError.
    Catch this to handle any validation failure regardless of phase.
    """


class SchemaValidationError(ValidationError):
    """Raised when a DataFrame's columns don't match the expected schema.

    Phase 1 validation — always raised regardless of ValidationMode. Raised by BB-05
    when required columns are missing, or the entity key / event timestamp column
    contains null values. The message lists all schema issues found.
    """


class DataValidationError(ValidationError):
    """Raised when data fails type checks or feature expectation checks in ERROR mode.

    Phase 2 validation — only raised when ValidationMode is ERROR. Raised by BB-05
    in ingest() (ingestion gate) and get_historical_features() (retrieval gate).
    The message includes the full validation report: passed count, failed count,
    and per-failure details (entity key, field, expected constraint, actual value).
    """


class IngestionError(KiteFSError):
    """Raised for ingestion failures not covered by validation errors.

    Raised by BB-02 in ingest() when the input type is unsupported (not a
    DataFrame, CSV path, or Parquet path), or when an input file cannot be
    found or read.
    """


class RetrievalError(KiteFSError):
    """Raised for retrieval parameter or state errors.

    Raised by BB-02 in get_historical_features() and get_online_features() when
    select references non-existent features, where uses an unsupported field or
    operator, or the feature group is OFFLINE-only and online retrieval was requested.
    """


class MaterializationError(KiteFSError):
    """Raised for materialization-specific failures.

    Raised by BB-02 in materialize() when a group's storage_target is OFFLINE-only,
    or by BB-07 in get_online_features() when the online store table doesn't exist
    (i.e. materialize() has never been run for that group).
    """


class JoinError(KiteFSError):
    """Raised when a point-in-time join cannot be executed.

    Raised by BB-02 in get_historical_features() when no valid join path exists
    between the base group and a joined group, or when the join spec contains
    more than one group (MVP limit — FR-OFF-009).
    """


class ProviderError(KiteFSError):
    """Raised when the underlying storage backend fails.

    Raised by BB-09 for any I/O failure — disk full, S3 permission denied,
    DynamoDB throttling, network errors, missing AWS credentials, etc.
    Wraps provider-specific exceptions with KiteFS context, preserving the
    original error as context (use `raise ProviderError(...) from original`).
    """
