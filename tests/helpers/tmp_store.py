"""Utilities for spinning up a local provider rooted at a tmp_path.

Provides a ready-to-use local KiteFS project directory for integration
and BDD tests.
"""

from __future__ import annotations

from pathlib import Path

from kitefs.cli.scaffold import init_producer


def make_initialized_project(tmp_path: Path) -> Path:
    """Scaffold a full local KiteFS project at tmp_path and return the path."""
    init_producer(tmp_path)
    return tmp_path
