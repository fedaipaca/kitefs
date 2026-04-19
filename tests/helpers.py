"""Shared test helpers for the KiteFS test suite."""

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

from kitefs.config import Config
from kitefs.definitions import (
    EntityKey,
    EventTimestamp,
    Feature,
    FeatureGroup,
    FeatureType,
    StorageTarget,
)
from kitefs.providers.local import LocalProvider
from kitefs.registry import RegistryManager


def make_feature_group(**overrides: Any) -> FeatureGroup:
    """Build a minimal FeatureGroup with sensible defaults.

    Any FeatureGroup field can be overridden via keyword arguments.
    """
    defaults: dict[str, Any] = {
        "name": "test_group",
        "storage_target": StorageTarget.OFFLINE,
        "entity_key": EntityKey(name="id", dtype=FeatureType.INTEGER),
        "event_timestamp": EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
        "features": [Feature(name="value", dtype=FeatureType.FLOAT)],
    }
    defaults.update(overrides)
    return FeatureGroup(**defaults)


def make_local_config(tmp_path: Path) -> Config:
    """Build a minimal local Config pointing at tmp_path."""
    storage_root = tmp_path / "feature_store"
    return Config(
        provider="local",
        project_root=tmp_path,
        storage_root=storage_root,
        definitions_path=storage_root / "definitions",
        aws=None,
    )


def write_definition(directory: Path, filename: str, content: str) -> Path:
    """Write a Python definition file into *directory* and return the path."""
    path = directory / filename
    path.write_text(content)
    return path


def setup_manager(tmp_path: Path, seed_registry: bool = True) -> RegistryManager:
    """Create a RegistryManager backed by a LocalProvider in tmp_path.

    Optionally seeds an empty registry.json (mirrors what kitefs init does).
    """
    config = make_local_config(tmp_path)
    config.storage_root.mkdir(parents=True, exist_ok=True)
    config.definitions_path.mkdir(parents=True, exist_ok=True)

    if seed_registry:
        registry_path = config.storage_root / "registry.json"
        registry_path.write_text('{"version": "1.0", "feature_groups": {}}', encoding="utf-8")

    provider = LocalProvider(config)
    return RegistryManager(provider, config.definitions_path)


MINIMAL_GROUP = dedent("""\
    from kitefs import (
        EntityKey, EventTimestamp, Feature, FeatureGroup,
        FeatureType, StorageTarget,
    )

    group = FeatureGroup(
        name="{name}",
        storage_target=StorageTarget.OFFLINE,
        entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
        event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
        features=[Feature(name="value", dtype=FeatureType.FLOAT)],
    )
""")

MINIMAL_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup,
    FeatureType, StorageTarget,
)

{varname} = FeatureGroup(
    name="{name}",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[Feature(name="value", dtype=FeatureType.FLOAT)],
)
"""

LISTING_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
    FeatureType, JoinKey, Metadata, StorageTarget, ValidationMode,
)

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER,
                         description="Unique identifier for each listing"),
    event_timestamp=EventTimestamp(name="event_timestamp", dtype=FeatureType.DATETIME,
                                   description="When the listing was sold"),
    features=[
        Feature(name="net_area", dtype=FeatureType.INTEGER,
                description="Usable area in sqm",
                expect=Expect().not_null().gt(0)),
        Feature(name="number_of_rooms", dtype=FeatureType.INTEGER,
                description="Number of rooms",
                expect=Expect().not_null().gt(0)),
        Feature(name="build_year", dtype=FeatureType.INTEGER,
                description="Year the building was constructed",
                expect=Expect().not_null().gte(1900).lte(2030)),
        Feature(name="sold_price", dtype=FeatureType.FLOAT,
                description="Sold price in TL (training label)",
                expect=Expect().not_null().gt(0)),
        Feature(name="town_id", dtype=FeatureType.INTEGER,
                description="Join key to town_market_features"),
    ],
    join_keys=[JoinKey(field_name="town_id", referenced_group="town_market_features")],
    ingestion_validation=ValidationMode.ERROR,
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(
        description="Historical sold listing attributes and prices",
        owner="data-science-team",
        tags={"domain": "real-estate", "cadence": "monthly"},
    ),
)
"""

TOWN_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
    FeatureType, Metadata, StorageTarget, ValidationMode,
)

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER,
                         description="Unique town identifier"),
    event_timestamp=EventTimestamp(name="event_timestamp", dtype=FeatureType.DATETIME,
                                   description="When this value became available"),
    features=[
        Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT,
                description="Average sold price per sqm in this town last month",
                expect=Expect().not_null().gt(0)),
    ],
    ingestion_validation=ValidationMode.ERROR,
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(
        description="Monthly town-level market aggregate",
        owner="data-science-team",
        tags={"domain": "real-estate", "cadence": "monthly"},
    ),
)
"""


def setup_project(project_root: Path, definitions: dict[str, str] | None = None) -> Path:
    """Create a minimal KiteFS project scaffold on disk for SDK tests.

    Writes kitefs.yaml, creates the definitions directory, and seeds
    an empty registry.json. Optionally writes definition files from a
    {filename: content} dict.

    Returns the project_root for convenience.
    """
    storage_root = project_root / "feature_store"
    definitions_dir = storage_root / "definitions"
    definitions_dir.mkdir(parents=True, exist_ok=True)
    (definitions_dir / "__init__.py").write_text("", encoding="utf-8")

    # Mirror the data directories that `kitefs init` creates.
    (storage_root / "data" / "offline_store").mkdir(parents=True, exist_ok=True)
    (storage_root / "data" / "online_store").mkdir(parents=True, exist_ok=True)

    (project_root / "kitefs.yaml").write_text(
        "provider: local\nstorage_root: ./feature_store/\n",
        encoding="utf-8",
    )
    (storage_root / "registry.json").write_text(
        json.dumps({"version": "1.0", "feature_groups": {}}, sort_keys=True, indent=2),
        encoding="utf-8",
    )

    if definitions:
        for filename, content in definitions.items():
            (definitions_dir / filename).write_text(content, encoding="utf-8")

    return project_root
