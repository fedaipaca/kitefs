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
                document = json.load(f)
        except FileNotFoundError as exc:
            raise RegistryReadError(
                f"Registry file not found at {self._path.resolve()}. Run 'kitefs init' to scaffold a registry."
            ) from exc
        except json.JSONDecodeError as exc:
            raise RegistryReadError(f"Registry file at {self._path.resolve()} could not be parsed: {exc}") from exc
        except OSError as exc:
            raise RegistryReadError(f"Failed to read registry at {self._path.resolve()}: {exc}") from exc

        if not isinstance(document, dict):
            raise RegistryReadError(
                f"Registry file at {self._path.resolve()} has an unexpected format: expected a JSON object"
            )
        if not isinstance(document.get("feature_groups"), dict):
            raise RegistryReadError(
                f"Registry file at {self._path.resolve()} is corrupt: missing or invalid 'feature_groups' field"
            )
        return document  # type: ignore[return-value]

    def write(self, document: dict[str, Any]) -> None:
        content = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        tmp: Path | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(dir=self._path.parent, prefix=".tmp_registry_", suffix="")
            tmp = Path(tmp_name)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            os.replace(tmp, self._path)
        except OSError as exc:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
            raise RegistryWriteError(f"Failed to write registry at {self._path.resolve()}: {exc}") from exc
        except BaseException:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
            raise


__all__ = ["LocalRegistryStore"]
