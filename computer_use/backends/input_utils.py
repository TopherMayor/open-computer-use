from __future__ import annotations


KEY_ALIASES: dict[str, str] = {
    "return": "enter",
    "enter": "enter",
    "escape": "esc",
    "esc": "esc",
    "space": "space",
    "tab": "tab",
    "backspace": "backspace",
    "delete": "delete",
    "del": "delete",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "home": "home",
    "end": "end",
    "page_up": "pageup",
    "pageup": "pageup",
    "page_down": "pagedown",
    "pagedown": "pagedown",
}


def normalize_button(button: str) -> str:
    button = (button or "left").lower()
    if button not in {"left", "right", "middle"}:
        raise RuntimeError("mouse_button must be one of: left, right, middle")
    return button
