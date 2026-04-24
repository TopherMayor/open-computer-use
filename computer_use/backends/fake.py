from __future__ import annotations

from typing import Any

from ..types import CachedElement, ELEMENT_CACHE, clear_cache, element_from_index as base_element_from_index, frame_center
from .base import ComputerBackend


SCREEN_SIZE = {"width": 1920, "height": 1080}


def _fake_element(index: int) -> CachedElement:
    return CachedElement(
        element=None,
        frame={
            "x": index * 10,
            "y": index * 10,
            "width": 100,
            "height": 50,
            "center_x": index * 10 + 50,
            "center_y": index * 10 + 25,
        },
        app="FakeApp",
        role="button",
        title=f"Element {index}",
    )


class FakeBackend(ComputerBackend):
    name = "fake"

    def __init__(self):
        self._app = None

    def list_apps(self, **kwargs) -> list[dict[str, Any]]:
        return [
            {"name": "FakeApp", "pid": 12345, "running": True, "active": True, "source": "fake"},
        ]

    def activate_or_launch_app(self, app_name: str) -> dict[str, Any]:
        self._app = app_name
        return {
            "name": app_name,
            "pid": 12345,
            "running": True,
            "active": True,
            "source": "fake",
        }

    def capture_screenshot(self) -> tuple[str, int, int, str]:
        import base64
        import io

        from PIL import Image

        width, height = 1920, 1080
        img = Image.new("RGB", (width, height), (64, 64, 64))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return b64, width, height, "fake"

    def get_accessibility_tree(self, app_name: str, pid: int, **kwargs) -> dict[str, Any] | None:
        max_elements = int(kwargs.get("max_elements", 10))
        clear_cache()
        for i in range(min(max_elements, 10)):
            index_str = str(i)
            ELEMENT_CACHE[index_str] = CachedElement(
                element=None,
                frame={
                    "x": i * 10,
                    "y": i * 10,
                    "width": 100,
                    "height": 50,
                    "center_x": i * 10 + 50,
                    "center_y": i * 10 + 25,
                },
                app=app_name,
                role="button" if i > 0 else "window",
                title=f"Element {i}" if i > 0 else app_name,
            )
        tree = {"element_index": "0", "role": "window", "title": app_name, "children": []}
        for i in range(1, min(max_elements, 10)):
            tree["children"].append({
                "element_index": str(i),
                "role": "button",
                "title": f"Button {i}",
            })
        return tree

    def click(self, element_index: str | None, x: int | None, y: int | None, **kwargs) -> dict[str, Any]:
        button = str(kwargs.get("mouse_button", "left"))
        click_count = int(kwargs.get("click_count", 1))
        if element_index is not None:
            base_element_from_index(element_index)
            return {"success": True, "method": "AXPress", "element_index": element_index}
        return {"success": True, "method": "mouse", "x": x, "y": y, "button": button, "click_count": click_count}

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, **kwargs) -> dict[str, Any]:
        duration = float(kwargs.get("duration", 0.35))
        return {"success": True, "from": [from_x, from_y], "to": [to_x, to_y], "duration": duration}

    def press_key(self, key: str, **kwargs) -> dict[str, Any]:
        return {"success": True, "key": key}

    def type_text(self, text: str, **kwargs) -> dict[str, Any]:
        return {"success": True, "chars": len(text), "method": "fake"}

    def scroll(self, element_index: str, direction: str, pages: float, **kwargs) -> dict[str, Any]:
        return {"success": True, "element_index": element_index, "direction": direction, "pages": pages}

    def set_value(self, element_index: str, value: str, **kwargs) -> dict[str, Any]:
        return {"success": True, "method": "AXValue", "element_index": element_index}

    def perform_action(self, element_index: str, action: str, **kwargs) -> dict[str, Any]:
        return {"success": True, "element_index": element_index, "action": action}

    def screen_size(self) -> dict[str, int]:
        return SCREEN_SIZE

    def is_accessibility_trusted(self) -> bool | None:
        return True

    def clear_cache(self) -> None:
        clear_cache()

    def flat_elements(self) -> list[dict[str, Any]]:
        return [{"element_index": "0", "role": "window"}]

    def element_from_index(self, index: str) -> Any:
        return _fake_element(int(index))

    def ocr_extract(self, image_bytes: bytes) -> list[dict[str, Any]]:
        return [{"text": "FakeApp", "x": 10, "y": 10, "width": 80, "height": 20, "confidence": 0.95}]

    def annotate_screenshot(self, image_bytes: bytes, elements: list[dict[str, Any]]) -> bytes:
        return image_bytes

    def diff_screenshots(self, before_bytes: bytes, after_bytes: bytes, threshold: float = 5.0) -> dict[str, Any]:
        return {"changed": False, "regions": [], "diff_image": b""}


def create_backend() -> FakeBackend:
    return FakeBackend()