from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CachedElement:
    element: Any
    frame: dict[str, float] | None
    app: str | None
    role: str | None = None
    title: str | None = None


ELEMENT_CACHE: dict[str, CachedElement] = {}
LAST_APP: str | None = None


def clear_cache() -> None:
    ELEMENT_CACHE.clear()


def flat_elements() -> list[dict[str, Any]]:
    return [
        {
            "element_index": index,
            "role": cached.role,
            "title": cached.title,
            "frame": cached.frame,
            "app": cached.app,
        }
        for index, cached in ELEMENT_CACHE.items()
    ]


def element_from_index(element_index: str) -> CachedElement:
    if element_index not in ELEMENT_CACHE:
        raise RuntimeError(
            f"Unknown element_index {element_index!r}. Call get_app_state first and use an index from the latest tree."
        )
    return ELEMENT_CACHE[element_index]


def frame_center(frame: dict[str, float] | None) -> tuple[int, int]:
    if not frame:
        raise RuntimeError("The selected accessibility element does not expose a screen frame.")
    return int(round(frame["center_x"])), int(round(frame["center_y"]))