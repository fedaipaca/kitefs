"""Local RegistryStore — reads and writes feature_store/registry.json atomically."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from kitefs.errors import RegistryReadError, RegistryWriteError
from kitefs.providers.base import RegistryStore


class LocalRegistryStore(RegistryStore):
    """JSON-backed registry stored at <root>/feature_store/registry.json."""

    def __init__(self, root: Path) -> None:
        self._path = root / "feature_store" / "registry.json"

    def read(self) -> dict[str, Any]:
        try:
            with self._path.open(encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except FileNotFoundError as exc:
            raise RegistryReadError(
                f"Registry file not found at {self._path.resolve()}. Run 'kitefs init' to scaffold a registry."
            ) from exc
        except json.JSONDecodeError as exc:
            raise RegistryReadError(f"Registry file at {self._path.resolve()} could not be parsed: {exc}") from exc

    def write(self, document: dict[str, Any]) -> None:
        content = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        fd, tmp_name = tempfile.mkstemp(dir=self._path.parent, prefix=".tmp_registry_", suffix="")
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            os.replace(tmp, self._path)
        except BaseException as exc:
            tmp.unlink(missing_ok=True)
            raise RegistryWriteError(f"Failed to write registry at {self._path.resolve()}: {exc}") from exc


__all__ = ["LocalRegistryStore"]
