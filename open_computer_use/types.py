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
LAST_APP: str | None = None  # TODO: expose via flat_elements or a status endpoint
LAST_SCREENSHOT: bytes = b""

INTERACTIVE_ROLES: frozenset[str] = frozenset({
    "button",
    "push button",
    "toggle button",
    "textfield",
    "text field",
    "text",
    "entry",
    "menuitem",
    "menu item",
    "checkbox",
    "check box",
    "radio",
    "radio button",
    "slider",
    "tab",
    "page tab",
    "link",
    "grid",
    "table",
    "listitem",
    "list item",
})


def clear_cache() -> None:
    """Remove all entries from the element cache."""
    ELEMENT_CACHE.clear()


def flat_elements() -> list[dict[str, Any]]:
    """Return a flattened list of cached element metadata dicts."""
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
    """Look up a cached element by its index string."""
    if element_index not in ELEMENT_CACHE:
        raise RuntimeError(
            f"Unknown element_index {element_index!r}. Call get_app_state first and use an index from the latest tree."
        )
    return ELEMENT_CACHE[element_index]


def frame_center(frame: dict[str, float] | None) -> tuple[int, int]:
    """Extract the rounded pixel center coordinates from a frame dict."""
    if not frame:
        raise RuntimeError("The selected accessibility element does not expose a screen frame.")
    return int(round(frame["center_x"])), int(round(frame["center_y"]))


def generate_role_summary(
    role: str | None,
    title: str | None,
    value: Any = None,
    checked: bool | None = None,
) -> str:
    if not role:
        return ""
    r = role.lower()
    if r in ("button", "push button", "toggle button"):
        return f"Button: {title or ''}"
    if r in ("textfield", "text field", "text", "entry"):
        return f"Text Field [{value or ''}]"
    if r in ("checkbox", "check box"):
        return f"Checkbox [{'checked' if checked else 'unchecked'}]"
    if r in ("menuitem", "menu item"):
        return f"Menu Item: {title or ''}"
    return role


def is_visible(frame: dict[str, float] | None, screen_w: int, screen_h: int) -> bool:
    if frame is None:
        return False
    w = frame.get("width", 0)
    h = frame.get("height", 0)
    if w <= 0 or h <= 0:
        return False
    x = frame.get("x", 0)
    y = frame.get("y", 0)
    if x + w <= 0 or y + h <= 0:
        return False
    if x >= screen_w or y >= screen_h:
        return False
    return True


def count_tree_nodes(tree: dict[str, Any]) -> int:
    count = 1
    for child in tree.get("children", []):
        count += count_tree_nodes(child)
    return count


def filter_tree(tree: dict[str, Any], filter_type: str) -> dict[str, Any]:
    if not filter_type:
        return tree

    def _matches(n: dict[str, Any]) -> bool:
        if filter_type == "interactive":
            return (n.get("role") or "").lower() in INTERACTIVE_ROLES
        if filter_type == "text":
            return bool(n.get("title") or n.get("value") or n.get("text"))
        return True

    def _prune(node: dict[str, Any]) -> dict[str, Any] | None:
        filtered_children = []
        for child in node.get("children", []):
            result = _prune(child)
            if result is not None:
                filtered_children.append(result)
        if _matches(node) or filtered_children:
            out = dict(node)
            if filtered_children:
                out["children"] = filtered_children
            elif "children" in out:
                del out["children"]
            return out
        return None

    result = _prune(tree)
    return result if result is not None else tree
