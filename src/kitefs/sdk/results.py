from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApplyResult:
    registered_groups: list[str]
    published: bool


__all__ = ["ApplyResult"]
