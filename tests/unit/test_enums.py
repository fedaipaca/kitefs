import kitefs
from kitefs.enums import FeatureType, StorageTarget, ValidationMode


def test_feature_type_members() -> None:
    assert {m.name for m in FeatureType} == {"STRING", "INTEGER", "FLOAT", "DATETIME"}


def test_storage_target_members() -> None:
    assert {m.name for m in StorageTarget} == {"OFFLINE", "OFFLINE_AND_ONLINE"}


def test_validation_mode_members() -> None:
    assert {m.name for m in ValidationMode} == {"ERROR", "FILTER", "NONE"}


def test_feature_type_string_values() -> None:
    assert FeatureType.STRING.value == "STRING"
    assert FeatureType.INTEGER.value == "INTEGER"
    assert FeatureType.FLOAT.value == "FLOAT"
    assert FeatureType.DATETIME.value == "DATETIME"


def test_storage_target_string_values() -> None:
    assert StorageTarget.OFFLINE.value == "OFFLINE"
    assert StorageTarget.OFFLINE_AND_ONLINE.value == "OFFLINE_AND_ONLINE"


def test_validation_mode_string_values() -> None:
    assert ValidationMode.ERROR.value == "ERROR"
    assert ValidationMode.FILTER.value == "FILTER"
    assert ValidationMode.NONE.value == "NONE"


def test_enums_reachable_from_kitefs() -> None:
    assert kitefs.FeatureType is FeatureType
    assert kitefs.StorageTarget is StorageTarget
    assert kitefs.ValidationMode is ValidationMode
