"""Unit tests for LocalRegistryStore."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kitefs.errors import RegistryReadError, RegistryWriteError
from kitefs.providers.local.registry import LocalRegistryStore


def _make_store(root: Path) -> LocalRegistryStore:
    (root / "feature_store").mkdir(exist_ok=True)
    return LocalRegistryStore(root)


class TestRead:
    """LocalRegistryStore.read() loads and returns the registry document."""

    def test_returns_parsed_json(self, tmp_path) -> None:
        """read() returns the parsed content of registry.json."""
        store = _make_store(tmp_path)
        doc = {"feature_groups": {"fg1": {"name": "fg1"}}}
        (tmp_path / "feature_store" / "registry.json").write_text(json.dumps(doc), encoding="utf-8")
        assert store.read() == doc

    def test_empty_registry(self, tmp_path) -> None:
        """read() returns empty dict structure from a freshly initialized registry."""
        store = _make_store(tmp_path)
        (tmp_path / "feature_store" / "registry.json").write_text('{"feature_groups": {}}', encoding="utf-8")
        assert store.read() == {"feature_groups": {}}

    def test_missing_file_raises_registry_read_error(self, tmp_path) -> None:
        """read() raises RegistryReadError when registry.json is absent."""
        store = _make_store(tmp_path)
        with pytest.raises(RegistryReadError) as exc_info:
            store.read()
        assert "registry.json" in str(exc_info.value).lower() or "registry" in str(exc_info.value).lower()

    def test_corrupt_json_raises_registry_read_error(self, tmp_path) -> None:
        """read() raises RegistryReadError when registry.json is not valid JSON."""
        store = _make_store(tmp_path)
        (tmp_path / "feature_store" / "registry.json").write_text("{broken json", encoding="utf-8")
        with pytest.raises(RegistryReadError):
            store.read()

    def test_non_dict_json_raises_registry_read_error(self, tmp_path) -> None:
        """read() raises RegistryReadError when JSON root is not an object."""
        store = _make_store(tmp_path)
        (tmp_path / "feature_store" / "registry.json").write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(RegistryReadError):
            store.read()

    def test_missing_feature_groups_raises_registry_read_error(self, tmp_path) -> None:
        """read() raises RegistryReadError when feature_groups key is absent."""
        store = _make_store(tmp_path)
        (tmp_path / "feature_store" / "registry.json").write_text('{"version": 1}', encoding="utf-8")
        with pytest.raises(RegistryReadError):
            store.read()

    def test_non_dict_feature_groups_raises_registry_read_error(self, tmp_path) -> None:
        """read() raises RegistryReadError when feature_groups is not an object."""
        store = _make_store(tmp_path)
        (tmp_path / "feature_store" / "registry.json").write_text('{"feature_groups": []}', encoding="utf-8")
        with pytest.raises(RegistryReadError):
            store.read()

    def test_io_error_raises_registry_read_error(self, tmp_path) -> None:
        """read() raises RegistryReadError on unexpected OSError."""
        store = _make_store(tmp_path)
        store._path = MagicMock()
        store._path.open.side_effect = PermissionError("denied")
        store._path.resolve.return_value = tmp_path / "feature_store" / "registry.json"
        with pytest.raises(RegistryReadError):
            store.read()


class TestWrite:
    """LocalRegistryStore.write() serializes and atomically installs the document."""

    def test_write_produces_correct_json_format(self, tmp_path) -> None:
        """write() produces sorted, 2-space indented, ensure_ascii=False JSON."""
        store = _make_store(tmp_path)
        doc = {"z_key": "value", "a_key": [1, 2]}
        store.write(doc)
        raw = (tmp_path / "feature_store" / "registry.json").read_text(encoding="utf-8")
        expected = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        assert raw == expected

    def test_write_produces_trailing_newline(self, tmp_path) -> None:
        """write() output ends with a newline character."""
        store = _make_store(tmp_path)
        store.write({"feature_groups": {}})
        raw = (tmp_path / "feature_store" / "registry.json").read_bytes()
        assert raw.endswith(b"\n")

    def test_write_sorts_keys(self, tmp_path) -> None:
        """write() serializes keys in sorted order."""
        store = _make_store(tmp_path)
        store.write({"z": 1, "a": 2, "m": 3})
        raw = (tmp_path / "feature_store" / "registry.json").read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert list(parsed.keys()) == sorted(parsed.keys())

    def test_write_roundtrips_with_read(self, tmp_path) -> None:
        """write() followed by read() returns the same document."""
        store = _make_store(tmp_path)
        doc = {"feature_groups": {"mygroup": {"name": "mygroup"}}}
        store.write(doc)
        assert store.read() == doc

    def test_write_is_atomic_no_partial_on_failure(self, tmp_path) -> None:
        """write() leaves the original file untouched when the write fails mid-way."""
        store = _make_store(tmp_path)
        original = {"feature_groups": {}}
        store.write(original)

        # Simulate an I/O failure during the os.replace step.
        _patch = patch("kitefs.providers.local.registry.os.replace", side_effect=OSError("disk full"))
        with _patch, pytest.raises(RegistryWriteError):
            store.write({"feature_groups": {"new": {}}})

        # Original content must still be intact.
        assert store.read() == original

    def test_write_cleans_up_temp_file_on_failure(self, tmp_path) -> None:
        """write() removes the temp file when the atomic install fails."""
        store = _make_store(tmp_path)
        store.write({"feature_groups": {}})

        _patch = patch("kitefs.providers.local.registry.os.replace", side_effect=OSError("disk full"))
        with _patch, pytest.raises(RegistryWriteError):
            store.write({"new": "data"})

        tmp_files = list((tmp_path / "feature_store").glob(".tmp_registry_*"))
        assert tmp_files == [], f"Temp files not cleaned up: {tmp_files}"

    def test_mkstemp_failure_raises_registry_write_error(self, tmp_path) -> None:
        """write() raises RegistryWriteError when tempfile.mkstemp fails."""
        store = _make_store(tmp_path)
        _patch = patch("kitefs.providers.local.registry.tempfile.mkstemp", side_effect=OSError("no space left"))
        with _patch, pytest.raises(RegistryWriteError):
            store.write({"feature_groups": {}})
