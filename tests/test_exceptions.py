"""Tests for the KiteFS exception hierarchy (src/kitefs/exceptions.py)."""

import pytest

from kitefs.exceptions import (
    ConfigurationError,
    DataValidationError,
    DefinitionError,
    FeatureGroupNotFoundError,
    IngestionError,
    JoinError,
    KiteFSError,
    MaterializationError,
    ProviderError,
    RegistryError,
    RetrievalError,
    SchemaValidationError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Importability
# ---------------------------------------------------------------------------


class TestImportability:
    """All exception classes are importable from kitefs.exceptions."""

    def test_all_exception_classes_importable(self) -> None:
        # If any import above fails this module won't even load — this test
        # just asserts they're all proper Exception subclasses as a smoke check.
        classes = [
            KiteFSError,
            ConfigurationError,
            DefinitionError,
            RegistryError,
            FeatureGroupNotFoundError,
            ValidationError,
            SchemaValidationError,
            DataValidationError,
            IngestionError,
            RetrievalError,
            MaterializationError,
            JoinError,
            ProviderError,
        ]
        for cls in classes:
            assert issubclass(cls, Exception), f"{cls.__name__} is not an Exception subclass"


# ---------------------------------------------------------------------------
# Inheritance tree
# ---------------------------------------------------------------------------


class TestInheritanceTree:
    """Verify every class sits at the correct position in the hierarchy."""

    def test_kitesfserror_is_exception(self) -> None:
        assert issubclass(KiteFSError, Exception)

    def test_configuration_error_is_kitesfserror(self) -> None:
        assert issubclass(ConfigurationError, KiteFSError)

    def test_definition_error_is_kitesfserror(self) -> None:
        assert issubclass(DefinitionError, KiteFSError)

    def test_registry_error_is_kitesfserror(self) -> None:
        assert issubclass(RegistryError, KiteFSError)

    def test_feature_group_not_found_error_is_kitesfserror(self) -> None:
        assert issubclass(FeatureGroupNotFoundError, KiteFSError)

    def test_validation_error_is_kitesfserror(self) -> None:
        assert issubclass(ValidationError, KiteFSError)

    def test_schema_validation_error_is_validation_error(self) -> None:
        assert issubclass(SchemaValidationError, ValidationError)

    def test_schema_validation_error_is_kitesfserror(self) -> None:
        assert issubclass(SchemaValidationError, KiteFSError)

    def test_data_validation_error_is_validation_error(self) -> None:
        assert issubclass(DataValidationError, ValidationError)

    def test_data_validation_error_is_kitesfserror(self) -> None:
        assert issubclass(DataValidationError, KiteFSError)

    def test_ingestion_error_is_kitesfserror(self) -> None:
        assert issubclass(IngestionError, KiteFSError)

    def test_retrieval_error_is_kitesfserror(self) -> None:
        assert issubclass(RetrievalError, KiteFSError)

    def test_materialization_error_is_kitesfserror(self) -> None:
        assert issubclass(MaterializationError, KiteFSError)

    def test_join_error_is_kitesfserror(self) -> None:
        assert issubclass(JoinError, KiteFSError)

    def test_provider_error_is_kitesfserror(self) -> None:
        assert issubclass(ProviderError, KiteFSError)


# ---------------------------------------------------------------------------
# Sibling isolation — no accidental cross-inheritance
# ---------------------------------------------------------------------------


class TestSiblingIsolation:
    """Sibling exceptions must not inherit from one another."""

    def test_configuration_error_is_not_validation_error(self) -> None:
        assert not issubclass(ConfigurationError, ValidationError)

    def test_ingestion_error_is_not_validation_error(self) -> None:
        assert not issubclass(IngestionError, ValidationError)

    def test_definition_error_is_not_registry_error(self) -> None:
        assert not issubclass(DefinitionError, RegistryError)

    def test_schema_validation_error_is_not_data_validation_error(self) -> None:
        assert not issubclass(SchemaValidationError, DataValidationError)

    def test_data_validation_error_is_not_schema_validation_error(self) -> None:
        assert not issubclass(DataValidationError, SchemaValidationError)

    def test_provider_error_is_not_ingestion_error(self) -> None:
        assert not issubclass(ProviderError, IngestionError)


# ---------------------------------------------------------------------------
# Catchability via base KiteFSError
# ---------------------------------------------------------------------------


class TestCatchabilityViaBase:
    """Every exception is catchable via the KiteFSError base."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            ConfigurationError,
            DefinitionError,
            RegistryError,
            FeatureGroupNotFoundError,
            ValidationError,
            SchemaValidationError,
            DataValidationError,
            IngestionError,
            RetrievalError,
            MaterializationError,
            JoinError,
            ProviderError,
        ],
    )
    def test_catchable_via_kitesfserror(self, exc_class: type[KiteFSError]) -> None:
        with pytest.raises(KiteFSError):
            raise exc_class("test message")

    def test_kitesfserror_is_subclass_of_exception(self) -> None:
        assert issubclass(KiteFSError, Exception)


# ---------------------------------------------------------------------------
# ValidationError as intermediate catch
# ---------------------------------------------------------------------------


class TestValidationErrorIntermediateCatch:
    """SchemaValidationError and DataValidationError are catchable via ValidationError."""

    def test_schema_validation_error_catchable_as_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            raise SchemaValidationError("missing column: event_timestamp")

    def test_data_validation_error_catchable_as_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            raise DataValidationError("3 rows failed 'not_null' on 'price'")

    def test_configuration_error_not_catchable_as_validation_error(self) -> None:
        with pytest.raises(ConfigurationError):
            try:
                raise ConfigurationError("bad config")
            except ValidationError:
                pytest.fail("ConfigurationError should not be caught as ValidationError")


# ---------------------------------------------------------------------------
# Message preservation
# ---------------------------------------------------------------------------


class TestMessagePreservation:
    """The message string passed to the constructor is preserved and accessible."""

    @pytest.mark.parametrize(
        "exc_class, message",
        [
            (KiteFSError, "base error message"),
            (
                ConfigurationError,
                "Field 'provider' is missing in kitefs.yaml. Add 'provider: local' to fix it.",
            ),
            (
                DefinitionError,
                "2 errors found in definitions:\n"
                "  - Duplicate feature group name 'listing_features'\n"
                "  - 'event_timestamp' dtype must be DATETIME, got STRING",
            ),
            (
                RegistryError,
                "registry.json not found at feature_store/registry.json. Run `kitefs init` first.",
            ),
            (
                FeatureGroupNotFoundError,
                "Feature group 'listing_features' not found. Run `kitefs apply` to register it.",
            ),
            (
                SchemaValidationError,
                "Schema validation failed: missing columns ['price', 'net_area'].",
            ),
            (
                DataValidationError,
                "Data validation failed: 2 rows failed 'gt(0)' on 'price'.",
            ),
            (
                IngestionError,
                "Unsupported input type <class 'int'>. Pass a DataFrame, CSV path, or Parquet path.",
            ),
            (
                RetrievalError,
                "Feature 'unknown_feature' not found in 'listing_features'. Check `kitefs describe`.",
            ),
            (
                MaterializationError,
                "No online data for 'listing_features'. Run `kitefs materialize` first.",
            ),
            (
                JoinError,
                "No join key declared between 'listing_features' and 'town_market_features'.",
            ),
            (
                ProviderError,
                "Write to feature_store/registry.json failed: [Errno 28] No space left on device.",
            ),
        ],
    )
    def test_message_preserved(self, exc_class: type[KiteFSError], message: str) -> None:
        exc = exc_class(message)
        assert str(exc) == message
