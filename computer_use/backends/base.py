from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ComputerBackend(ABC):
    @abstractmethod
    def list_apps(self, **kwargs) -> list[dict[str, Any]]: ...

    @abstractmethod
    def activate_or_launch_app(self, app_name: str) -> dict[str, Any]: ...

    @abstractmethod
    def capture_screenshot(self) -> tuple[str, int, int, str]: ...

    @abstractmethod
    def get_accessibility_tree(self, app_name: str, pid: int, **kwargs) -> dict[str, Any] | None: ...

    @abstractmethod
    def click(self, element_index: str | None, x: int | None, y: int | None, **kwargs) -> dict[str, Any]: ...

    @abstractmethod
    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, **kwargs) -> dict[str, Any]: ...

    @abstractmethod
    def press_key(self, key: str, **kwargs) -> dict[str, Any]: ...

    @abstractmethod
    def type_text(self, text: str, **kwargs) -> dict[str, Any]: ...

    @abstractmethod
    def scroll(self, element_index: str, direction: str, pages: float, **kwargs) -> dict[str, Any]: ...

    @abstractmethod
    def set_value(self, element_index: str, value: str, **kwargs) -> dict[str, Any]: ...

    @abstractmethod
    def perform_action(self, element_index: str, action: str, **kwargs) -> dict[str, Any]: ...

    @abstractmethod
    def screen_size(self) -> dict[str, int]: ...

    @abstractmethod
    def is_accessibility_trusted(self) -> bool | None: ...

    @abstractmethod
    def clear_cache(self) -> None: ...

    @abstractmethod
    def flat_elements(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def element_from_index(self, index: str) -> Any: ...

    def ocr_extract(self, image_bytes: bytes) -> list[dict[str, Any]]:
        return []

    def annotate_screenshot(self, image_bytes: bytes, elements: list[dict[str, Any]]) -> bytes:
        return image_bytes

    def diff_screenshots(self, before_bytes: bytes, after_bytes: bytes, threshold: float = 5.0) -> dict[str, Any]:
        return {"changed": False, "regions": [], "diff_image": b""}