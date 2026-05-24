import importlib

import pytest

from kitefs.errors import KiteFSError

# (class_name, direct_base_name) — both reachable from kitefs.errors
HIERARCHY = [
    ("ConfigurationError", "KiteFSError"),
    ("DefinitionError", "KiteFSError"),
    ("DefinitionDiscoveryError", "KiteFSError"),
    ("DefinitionValidationError", "KiteFSError"),
    ("RegistryError", "KiteFSError"),
    ("RegistryReadError", "RegistryError"),
    ("RegistryWriteError", "RegistryError"),
    ("FeatureGroupNotFoundError", "KiteFSError"),
    ("FeatureGroupNotMaterializableError", "KiteFSError"),
    ("ValidationError", "KiteFSError"),
    ("IngestionShapeError", "KiteFSError"),
    ("RetrievalParameterError", "KiteFSError"),
    ("JoinError", "KiteFSError"),
    ("OfflineStoreError", "KiteFSError"),
    ("OfflineStoreReadError", "OfflineStoreError"),
    ("OfflineStoreWriteError", "OfflineStoreError"),
    ("OnlineStoreError", "KiteFSError"),
    ("OnlineStoreReadError", "OnlineStoreError"),
    ("OnlineStoreWriteError", "OnlineStoreError"),
    ("ProviderError", "KiteFSError"),
]


@pytest.mark.parametrize("class_name,direct_base_name", HIERARCHY)
def test_is_subclass_of_kitefsError(class_name: str, direct_base_name: str) -> None:
    errors_mod = importlib.import_module("kitefs.errors")
    cls = getattr(errors_mod, class_name)
    assert issubclass(cls, KiteFSError)


@pytest.mark.parametrize("class_name,direct_base_name", HIERARCHY)
def test_direct_base(class_name: str, direct_base_name: str) -> None:
    errors_mod = importlib.import_module("kitefs.errors")
    cls = getattr(errors_mod, class_name)
    base = getattr(errors_mod, direct_base_name)
    assert issubclass(cls, base)


@pytest.mark.parametrize("class_name,direct_base_name", HIERARCHY)
def test_importable_from_kitefs_errors(class_name: str, direct_base_name: str) -> None:
    errors_mod = importlib.import_module("kitefs.errors")
    assert hasattr(errors_mod, class_name)


@pytest.mark.parametrize("class_name,direct_base_name", HIERARCHY)
def test_importable_from_kitefs(class_name: str, direct_base_name: str) -> None:
    kitefs_mod = importlib.import_module("kitefs")
    assert hasattr(kitefs_mod, class_name)


def test_kitefsError_is_exception() -> None:
    assert issubclass(KiteFSError, Exception)
