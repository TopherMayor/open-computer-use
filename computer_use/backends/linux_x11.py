from __future__ import annotations

import os
import platform
import re
import subprocess
from typing import Any

from ..types import CachedElement, ELEMENT_CACHE, clear_cache, element_from_index, frame_center


SCREEN_SIZE = {"width": 1920, "height": 1080}


def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def _get_display() -> str | None:
    return os.environ.get("DISPLAY")


def require_pyautogui():
    try:
        import pyautogui  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "pyautogui is required for desktop input. Run `pip install -r requirements-linux.txt`."
        ) from exc

    pyautogui.FAILSAFE = True
    return pyautogui


def _screen_size() -> dict[str, int]:
    try:
        pyautogui = require_pyautogui()
        size = pyautogui.size()
        return {"width": int(size[0]), "height": int(size[1]}
    except Exception:
        return SCREEN_SIZE.copy()


def _capture_screenshot_png() -> tuple[str, int, int, str]:
    try:
        import pyautogui  # type: ignore
        import io
        import base64
        from PIL import Image

        image = pyautogui.screenshot()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii"), image.width, image.height, "pyautogui"
    except Exception:
        pass

    try:
        import mss  # type: ignore
        import mss.tools  # type: ignore
        import base64

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            sct_img = sct.grab(monitor)
            data = mss.tools.to_png(sct_img.rgb, sct_img.size)
            return base64.b64encode(data).decode("ascii"), sct_img.width, sct_img.height, "mss"
    except Exception as exc:
        raise RuntimeError(
            "Could not capture a screenshot. Install pyautogui or mss and ensure DISPLAY is set."
        ) from exc


def _list_apps() -> list[dict[str, Any]]:
    apps: dict[int, dict[str, Any]] = {}

    code, stdout, _ = _run(["wmctrl", "-l", "-p"])
    if code == 0:
        for line in stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                try:
                    wid = parts[0]
                    pid = int(parts[2])
                    name = " ".join(parts[3:])
                    if pid and name:
                        if pid not in apps:
                            apps[pid] = {
                                "name": name,
                                "pid": pid,
                                "windows": [wid],
                                "running": True,
                                "source": "wmctrl",
                            }
                        else:
                            apps[pid]["windows"].append(wid)
                except (ValueError, IndexError):
                    continue

    if not apps:
        code, stdout, _ = _run(["wmctrl", "-l"])
        if code == 0:
            for line in stdout.splitlines():
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    name = parts[3]
                    if name:
                        apps[len(apps)] = {
                            "name": name,
                            "running": True,
                            "source": "wmctrl",
                        }

    if not apps:
        code, stdout, _ = _run(["ps", "-eo", "pid,comm"])
        if code == 0:
            for line in stdout.splitlines()[1:]:
                parts = line.split(None, 1)
                if len(parts) >= 1:
                    name = parts[1] if len(parts) > 1 else parts[0]
                    if name and not name.startswith("-"):
                        apps[int(parts[0])] = {
                            "name": name,
                            "pid": int(parts[0]),
                            "running": True,
                            "source": "ps",
                        }

    result = list(apps.values())
    result.sort(key=lambda a: (not a.get("running", False), (a.get("name") or "").lower()))
    return result


def _find_running_app(app_name: str) -> dict[str, Any] | None:
    needle = app_name.lower().strip()
    if not needle:
        return None

    apps = _list_apps()
    for app in apps:
        name = str(app.get("name") or "").lower()
        if needle in name:
            return app

    for app in apps:
        name = str(app.get("name") or "").lower()
        if needle in name:
            return app

    return None


def _launch_or_activate_app(app_name: str) -> dict[str, Any]:
    app = _find_running_app(app_name)
    if app is not None:
        _activate_app(app.get("windows", [None])[0] if app.get("windows") else None
        code, _, _ = _run(["wmctrl", "-a", app_name])
        if code != 0:
            if app.get("windows"):
                _run(["xdotool", "windowactivate", app["windows"][0]])
        return app

    code, stdout, stderr = _run(["which", app_name])
    if code == 0 and stdout.strip():
        executable = stdout.strip()
    else:
        code, stdout, _ = _run(["which", app_name.lower()])
        executable = stdout.strip() if code == 0 else app_name

    if not executable:
        executable = app_name

    code, _, stderr = _run(["sh", "-c", f"{executable} &"])
    if code != 0 and stderr:
        raise RuntimeError(f"Could not launch app {app_name!r}: {stderr}")

    import time
    time.sleep(0.8)

    app = _find_running_app(app_name)
    if app is None:
        if code == 0:
            return {
                "name": app_name,
                "running": True,
                "active": False,
                "source": "launch-fallback",
            }
        raise RuntimeError(f"Could not find running app {app_name!r}")

    if app.get("windows"):
        _run(["xdotool", "windowactivate", "--sync", app["windows"][0]])

    return {
        "name": app.get("name", app_name),
        "pid": app.get("pid"),
        "running": True,
        "active": True,
        "source": "wmctrl",
    }


def _activate_app(windows: list[str | None]) -> str | None:
    if not windows:
        return None
    for wid in windows:
        if wid is None:
            continue
        code, _, _ = _run(["xdotool", "windowactivate", "--sync", wid])
        if code == 0:
            return wid
    return None


def normalize_button(button: str) -> str:
    button = (button or "left").lower()
    if button not in {"left", "right", "middle"}:
        raise RuntimeError("mouse_button must be one of: left, right, middle")
    return button


KEY_ALIASES = {
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


def normalize_key_token(token: str) -> str:
    token = token.strip().replace("-", "_")
    if len(token) == 4 and token.lower().startswith("kp_"):
        return token[-1]
    lowered = token.lower()

    if lowered in ("super", "cmd", "command", "meta"):
        return "ctrl"
    if lowered in ("ctrl", "control"):
        return "ctrl"
    if lowered in ("alt", "option"):
        return "alt"
    if lowered in ("shift",):
        return "shift"

    return KEY_ALIASES.get(lowered) or lowered


def _press_key_sequence(key: str) -> None:
    pyautogui = require_pyautogui()
    parts = [normalize_key_token(part) for part in re.split(r"\+", key) if part.strip()]
    if not parts:
        raise RuntimeError("key must not be empty")
    if len(parts) == 1:
        pyautogui.press(parts[0])
    else:
        pyautogui.hotkey(*parts)


def _type_literal_text(text: str) -> str:
    pyautogui = require_pyautogui()
    if all(char == "\n" or char == "\t" or 32 <= ord(char) <= 126 for char in text) and len(text) <= 500:
        pyautogui.write(text, interval=0.01)
        return "keyboard"

    try:
        import pyperclip  # type: ignore
        old_clipboard = pyperclip.paste()
        pyperclip.copy(text)
        _press_key_sequence("ctrl+v")
        import time
        time.sleep(0.1)
        pyperclip.copy(old_clipboard)
        return "clipboard-paste"
    except Exception:
        pyautogui.write(text, interval=0.01)
        return "keyboard"


def normalize_key_for_linux(key: str) -> str:
    key = key.lower()
    if key in ("super", "cmd", "command", "meta"):
        return "ctrl"
    if key in ("option", "alt"):
        return "alt"
    return key


def _get_accessibility_tree(app_name: str, pid: int, **kwargs) -> dict[str, Any] | None:
    max_elements = int(kwargs.get("max_elements", 10))

    try:
        from gi.repository import Atspi  # type: ignore
    except Exception:
        return _fallback_accessibility_tree(app_name, max_elements)

    try:
        Atspi.set_timeout(2000)
    except Exception:
        pass

    desktop = Atspi.get_desktop(0)
    if desktop is None:
        return _fallback_accessibility_tree(app_name, max_elements)

    tree = {
        "element_index": "0",
        "role": "window",
        "title": app_name,
        "children": [],
    }

    ELEMENT_CACHE.clear()
    element_index = 0

    def add_element(el: Any, parent_children: list, depth: int = 0) -> None:
        nonlocal element_index
        if depth > 7 or element_index >= max_elements:
            return

        try:
            role = el.get_role_name() if hasattr(el, "get_role_name") else None
            name = el.get_name() if hasattr(el, "get_name") else None
        except Exception:
            role = None
            name = None

        index_str = str(element_index)
        ELEMENT_CACHE[index_str] = CachedElement(
            element=el,
            frame=None,
            app=app_name,
            role=str(role) if role else None,
            title=str(name) if name else None,
        )

        node = {
            "element_index": index_str,
            "role": role,
            "title": name,
        }

        if role:
            node["role"] = role
        if name:
            node["title"] = name

        try:
            children = el.get_children() if hasattr(el, "get_children") else []
            if children and len(children) > 0:
                node["children"] = []
                for child in children:
                    add_element(child, node["children"], depth + 1)
        except Exception:
            pass

        parent_children.append(node)
        element_index += 1

    try:
        for app in desktop.get_applications():
            if not app:
                continue
            try:
                name = app.get_name() if hasattr(app, "get_name") else None
            except Exception:
                name = None

            if name and app_name.lower() in name.lower():
                for window in app.get_windows():
                    if window:
                        add_element(window, tree["children"], 0)
                        break
                break
    except Exception:
        pass

    return tree


def _fallback_accessibility_tree(app_name: str, max_elements: int) -> dict[str, Any]:
    code, stdout, _ = _run(["wmctrl", "-l"])
    if code != 0:
        return {"element_index": "0", "role": "window", "title": app_name, "children": []}

    children = []
    for i, line in enumerate(stdout.splitlines()):
        if i >= max_elements:
            break
        parts = line.split(None, 3)
        if len(parts) >= 4:
            children.append({
                "element_index": str(i + 1),
                "role": "window",
                "title": parts[3],
            })

    return {"element_index": "0", "role": "window", "title": app_name, "children": children}


class LinuxX11Backend:
    name = "linux-x11"

    def __init__(self):
        self._app = None

    def list_apps(self, **kwargs) -> list[dict[str, Any]]:
        return _list_apps()

    def activate_or_launch_app(self, app_name: str) -> dict[str, Any]:
        return _launch_or_activate_app(app_name)

    def capture_screenshot(self) -> tuple[str, int, int, str]:
        return _capture_screenshot_png()

    def get_accessibility_tree(self, app_name: str, pid: int, **kwargs) -> dict[str, Any] | None:
        return _get_accessibility_tree(app_name, pid, **kwargs)

    def click(self, element_index: str | None, x: int | None, y: int | None, **kwargs) -> dict[str, Any]:
        button = normalize_button(str(kwargs.get("mouse_button", "left")))
        click_count = int(kwargs.get("click_count", 1))

        pyautogui = require_pyautogui()

        if element_index is not None:
            cached = element_from_index(str(element_index))
            if cached.frame:
                cx, cy = frame_center(cached.frame)
            else:
                raise RuntimeError(f"No frame for element {element_index}")
        else:
            if x is None or y is None:
                raise RuntimeError("click requires either element_index or both x and y")
            cx, cy = x, y

        pyautogui.click(x=cx, y=cy, clicks=max(click_count, 1), button=button, interval=0.08)
        return {"success": True, "method": "mouse", "x": cx, "y": cy, "button": button, "click_count": click_count}

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, **kwargs) -> dict[str, Any]:
        duration = float(kwargs.get("duration", 0.35))
        pyautogui = require_pyautogui()
        pyautogui.moveTo(from_x, from_y)
        pyautogui.dragTo(to_x, to_y, duration=duration, button="left")
        return {"success": True, "from": [from_x, from_y], "to": [to_x, to_y], "duration": duration}

    def press_key(self, key: str, **kwargs) -> dict[str, Any]:
        key = normalize_key_for_linux(key)
        _press_key_sequence(key)
        return {"success": True, "key": key}

    def type_text(self, text: str, **kwargs) -> dict[str, Any]:
        method = _type_literal_text(text)
        return {"success": True, "chars": len(text), "method": method}

    def scroll(self, element_index: str, direction: str, pages: float, **kwargs) -> dict[str, Any]:
        direction = direction.lower()
        pages = float(pages)
        cached = element_from_index(element_index)
        x, y = frame_center(cached.frame)
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

        return {"success": True, "element_index": element_index, "direction": direction, "pages": pages}

    def set_value(self, element_index: str, value: str, **kwargs) -> dict[str, Any]:
        cached = element_from_index(element_index)
        method = _type_literal_text(value)
        return {"success": True, "method": method, "element_index": element_index}

    def perform_action(self, element_index: str, action: str, **kwargs) -> dict[str, Any]:
        return {"success": True, "element_index": element_index, "action": action, "note": "AT-SPI action not fully implemented"}

    def screen_size(self) -> dict[str, int]:
        return _screen_size()

    def is_accessibility_trusted(self) -> bool | None:
        code, _, _ = _run(["xdotool", "--version"])
        return code == 0

    def clear_cache(self) -> None:
        clear_cache()

    def flat_elements(self) -> list[dict[str, Any]]:
        from ..types import flat_elements as fe
        return fe()

    def element_from_index(self, index: str) -> Any:
        return element_from_index(index)


def create_backend() -> LinuxX11Backend:
    return LinuxX11Backend()