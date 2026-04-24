from __future__ import annotations

import base64
import io
from typing import Any

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
    """Validate and normalize a mouse button name to left, right, or middle."""
    button = (button or "left").lower()
    if button not in {"left", "right", "middle"}:
        raise RuntimeError("mouse_button must be one of: left, right, middle")
    return button


def require_pyautogui() -> Any:
    """Import pyautogui with failsafe enabled or raise a helpful error."""
    try:
        import pyautogui
    except Exception as exc:
        raise RuntimeError(
            "pyautogui is required for desktop input. Run `pip install -r requirements.txt`."
        ) from exc

    pyautogui.FAILSAFE = True
    return pyautogui


def capture_screenshot_png() -> tuple[str, int, int, str]:
    """Capture the screen and return base64 PNG, width, height, and method used."""
    try:
        from PIL import Image

        pyautogui = require_pyautogui()
        image = pyautogui.screenshot()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii"), image.width, image.height, "pyautogui"
    except Exception:
        pass

    try:
        import mss
        import mss.tools

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            sct_img = sct.grab(monitor)
            data = mss.tools.to_png(sct_img.rgb, sct_img.size)
            return base64.b64encode(data).decode("ascii"), sct_img.width, sct_img.height, "mss"
    except Exception as exc:
        raise RuntimeError(
            "Could not capture a screenshot. Install pyautogui or mss."
        ) from exc


def perform_scroll(
    x: int, y: int, direction: str, pages: float,
) -> None:
    """Move to (x, y) and scroll the given direction by a fractional page count."""
    pyautogui = require_pyautogui()
    pyautogui.moveTo(x, y)

    units = max(1, int(round(7 * pages)))
    if direction == "up":
        pyautogui.scroll(units, x=x, y=y)
    elif direction == "down":
        pyautogui.scroll(-units, x=x, y=y)
    elif direction == "left":
        if hasattr(pyautogui, "hscroll"):
            pyautogui.hscroll(-units, x=x, y=y)
        else:
            pyautogui.keyDown("shift")
            pyautogui.scroll(units, x=x, y=y)
            pyautogui.keyUp("shift")
    elif direction == "right":
        if hasattr(pyautogui, "hscroll"):
            pyautogui.hscroll(units, x=x, y=y)
        else:
            pyautogui.keyDown("shift")
            pyautogui.scroll(-units, x=x, y=y)
            pyautogui.keyUp("shift")
    else:
        raise RuntimeError("direction must be one of: up, down, left, right")


def perform_drag(
    from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.35,
) -> None:
    """Drag the mouse from one coordinate to another."""
    pyautogui = require_pyautogui()
    pyautogui.moveTo(from_x, from_y)
    pyautogui.dragTo(to_x, to_y, duration=duration, button="left")


def preserve_clipboard() -> str | None:
    """Save current clipboard content. Returns saved text or None."""
    try:
        import pyperclip
        return pyperclip.paste()
    except Exception:
        return None


def restore_clipboard(saved: str | None) -> None:
    """Restore clipboard to saved content."""
    if saved is None:
        return
    try:
        import pyperclip
        pyperclip.copy(saved)
    except Exception:
        pass
