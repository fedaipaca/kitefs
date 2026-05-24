from enum import Enum


class FeatureType(Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    DATETIME = "DATETIME"


class StorageTarget(Enum):
    OFFLINE = "OFFLINE"
    OFFLINE_AND_ONLINE = "OFFLINE_AND_ONLINE"


class ValidationMode(Enum):
    ERROR = "ERROR"
    FILTER = "FILTER"
    NONE = "NONE"


__all__ = ["FeatureType", "StorageTarget", "ValidationMode"]
