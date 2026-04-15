"""Definition types for KiteFS feature groups — the foundational data model (BB-03)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum


class FeatureType(Enum):
    """Supported data types for entity keys, event timestamps, and features."""

    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    DATETIME = "DATETIME"


class StorageTarget(Enum):
    """Where a feature group's data is stored and served from."""

    OFFLINE = "OFFLINE"
    OFFLINE_AND_ONLINE = "OFFLINE_AND_ONLINE"


class ValidationMode(Enum):
    """How validation failures are handled at each gate (ingestion, retrieval)."""

    ERROR = "ERROR"
    FILTER = "FILTER"
    NONE = "NONE"


@dataclass(frozen=True)
class Expect:
    """Fluent builder for feature-level data expectations.

    Each method returns a new Expect instance with the constraint appended,
    preserving immutability. Constraints are stored as a tuple of dicts,
    serializable via dataclasses.asdict().

    Example::

        Expect().not_null().gt(0)
        Expect().gte(1900).lte(2030)
        Expect().one_of(["apartment", "house", "land"])
    """

    _constraints: tuple[dict, ...] = ()

    def not_null(self) -> "Expect":
        """Require non-null values."""
        return Expect(_constraints=(*self._constraints, {"type": "not_null"}))

    def gt(self, value: int | float) -> "Expect":
        """Require values strictly greater than *value*."""
        return Expect(_constraints=(*self._constraints, {"type": "gt", "value": value}))

    def gte(self, value: int | float) -> "Expect":
        """Require values greater than or equal to *value*."""
        return Expect(_constraints=(*self._constraints, {"type": "gte", "value": value}))

    def lt(self, value: int | float) -> "Expect":
        """Require values strictly less than *value*."""
        return Expect(_constraints=(*self._constraints, {"type": "lt", "value": value}))

    def lte(self, value: int | float) -> "Expect":
        """Require values less than or equal to *value*."""
        return Expect(_constraints=(*self._constraints, {"type": "lte", "value": value}))

    def one_of(self, values: Sequence[str | int | float]) -> "Expect":
        """Require values to be one of the given *values*. Stores a defensive copy as a tuple."""
        return Expect(_constraints=(*self._constraints, {"type": "one_of", "values": tuple(values)}))


@dataclass(frozen=True)
class EntityKey:
    """The single entity identifier for a feature group.

    Structural column — always included in query results, implicitly non-null.
    Does not support expectations (Expect is not available on this type).
    """

    name: str
    dtype: FeatureType
    description: str | None = None


@dataclass(frozen=True)
class EventTimestamp:
    """The single event timestamp for a feature group.

    Structural column — always included in query results, implicitly non-null.
    dtype must be FeatureType.DATETIME (enforced by BB-04 at apply() time).
    """

    name: str
    dtype: FeatureType
    description: str | None = None


@dataclass(frozen=True)
class Feature:
    """A single feature (data column) within a feature group.

    Supports optional expectations via the Expect fluent builder for
    data-level validation at ingestion and retrieval gates.
    """

    name: str
    dtype: FeatureType
    description: str | None = None
    expect: Expect | None = None


@dataclass(frozen=True)
class JoinKey:
    """Declares a join relationship to another feature group's entity key.

    field_name must match a feature name in this group AND the entity key name
    of referenced_group. Type matching is validated by BB-04 at apply() time.
    """

    field_name: str
    referenced_group: str


@dataclass(frozen=True)
class Metadata:
    """Optional metadata attached to a feature group.

    All fields are optional and default to None.
    """

    description: str | None = None
    owner: str | None = None
    tags: dict[str, str] | None = None


@dataclass(frozen=True)
class FeatureGroup:
    """Top-level definition for a feature group.

    The foundational type that users create in their definitions/ directory.
    BB-04 discovers FeatureGroup instances at apply() time via importlib.

    features is normalised to a tuple sorted alphabetically by Feature.name
    during construction (KTD-16), ensuring deterministic equality and
    serialisation regardless of user-provided order.
    """

    name: str
    storage_target: StorageTarget
    entity_key: EntityKey
    event_timestamp: EventTimestamp
    features: list[Feature]
    join_keys: list[JoinKey] = field(default_factory=list)
    ingestion_validation: ValidationMode = ValidationMode.ERROR
    offline_retrieval_validation: ValidationMode = ValidationMode.NONE
    metadata: Metadata = field(default_factory=Metadata)

    def __post_init__(self) -> None:
        """Normalise features to a sorted tuple and join_keys to a tuple."""
        object.__setattr__(
            self,
            "features",
            tuple(sorted(self.features, key=lambda f: f.name)),
        )
        object.__setattr__(self, "join_keys", tuple(self.join_keys))
