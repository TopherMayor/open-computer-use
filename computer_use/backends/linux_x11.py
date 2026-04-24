from __future__ import annotations

import contextlib
import os
import re
import subprocess
from typing import Any

from ..types import ELEMENT_CACHE, CachedElement, clear_cache, element_from_index, frame_center, generate_role_summary, is_visible
from .base import ComputerBackend
from .input_utils import (
    KEY_ALIASES,
    capture_screenshot_png,
    normalize_button,
    perform_drag,
    perform_scroll,
    require_pyautogui,
)

SCREEN_SIZE = {"width": 1920, "height": 1080}


def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def _get_display() -> str | None:
    return os.environ.get("DISPLAY")


def _screen_size() -> dict[str, int]:
    try:
        pyautogui = require_pyautogui()
        size = pyautogui.size()
        return {"width": int(size[0]), "height": int(size[1])}
    except Exception:
        return SCREEN_SIZE.copy()


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
                    if pid is not None and name:
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
        if needle == name:
            return app

    for app in apps:
        name = str(app.get("name") or "").lower()
        if needle in name or name in needle:
            return app

    return None


def _launch_or_activate_app(app_name: str) -> dict[str, Any]:
    app = _find_running_app(app_name)
    if app is not None:
        windows = app.get("windows") or [None]
        _activate_app(windows)
        code, _, _ = _run(["wmctrl", "-a", app_name])
        if code != 0 and app.get("windows"):
            _run(["xdotool", "windowactivate", app["windows"][0]])
        return app

    which_code, stdout, stderr = _run(["which", app_name])
    if which_code == 0 and stdout.strip():
        executable = stdout.strip()
    else:
        which_code, stdout, _ = _run(["which", app_name.lower()])
        executable = stdout.strip() if which_code == 0 else app_name

    if not executable:
        executable = app_name

    try:
        subprocess.Popen(
            [executable],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise RuntimeError(f"Could not launch app {app_name!r}: executable {executable!r} not found") from None
    except Exception as exc:
        raise RuntimeError(f"Could not launch app {app_name!r}: {exc}") from exc

    import time
    time.sleep(0.8)

    app = _find_running_app(app_name)
    if app is None:
        if which_code == 0:
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

    screen = _screen_size()
    screen_w, screen_h = screen["width"], screen["height"]

    tree = {
        "element_index": "0",
        "role": "window",
        "title": app_name,
        "path": "window",
        "role_summary": "window",
        "visible": True,
        "children": [],
    }

    ELEMENT_CACHE.clear()
    element_index = 0
    was_truncated = False

    def add_element(el: Any, parent_children: list, depth: int = 0, parent_path: str = "") -> None:
        nonlocal element_index, was_truncated
        if depth > 7 or element_index >= max_elements:
            if element_index >= max_elements:
                was_truncated = True
            return

        try:
            role = el.get_role_name() if hasattr(el, "get_role_name") else None
        except Exception:
            role = None
        try:
            name = el.get_name() if hasattr(el, "get_name") else None
        except Exception:
            name = None

        desc = None
        try:
            desc = el.get_description() if hasattr(el, "get_description") else None
        except Exception:
            pass

        val = None
        try:
            val = Atspi.Value.get_value(el) if hasattr(el, "get_value") else None
        except Exception:
            pass

        states = None
        try:
            states = el.get_state_set() if hasattr(el, "get_state_set") else None
        except Exception:
            pass

        enabled = None
        try:
            if states is not None:
                enabled = states.contains(Atspi.StateType.ENABLED)
        except Exception:
            pass

        focused = None
        try:
            if states is not None:
                focused = states.contains(Atspi.StateType.FOCUSED)
        except Exception:
            pass

        checked = None
        try:
            if states is not None:
                checked = states.contains(Atspi.StateType.CHECKED)
        except Exception:
            pass

        frame = None
        try:
            ext = el.get_extents(Atspi.CoordType.SCREEN)
            if ext and (ext.width > 0 or ext.height > 0):
                frame = {
                    "x": ext.x, "y": ext.y,
                    "width": ext.width, "height": ext.height,
                    "center_x": ext.x + ext.width / 2,
                    "center_y": ext.y + ext.height / 2,
                }
        except Exception:
            pass

        actions = []
        try:
            action_iface = Atspi.Action
            n_actions = action_iface.get_n_actions(el)
            for i in range(n_actions):
                try:
                    aname = action_iface.get_action_name(el, i)
                    if aname:
                        actions.append(str(aname))
                except Exception:
                    pass
        except Exception:
            pass

        index_str = str(element_index)
        ELEMENT_CACHE[index_str] = CachedElement(
            element=el,
            frame=frame,
            app=app_name,
            role=str(role) if role else None,
            title=str(name) if name else None,
        )

        role_str = str(role) if role else "unknown"
        current_path = f"{parent_path}/{role_str}" if parent_path else role_str

        node: dict[str, Any] = {
            "element_index": index_str,
            "path": current_path,
            "role_summary": generate_role_summary(role_str, name, value=val, checked=checked),
            "visible": is_visible(frame, screen_w, screen_h),
        }
        fields = {
            "role": role,
            "title": name,
            "description": desc,
            "value": val,
            "enabled": enabled,
            "focused": focused,
            "checked": checked,
            "frame": frame,
        }
        for key, value in fields.items():
            if value not in (None, "", []):
                node[key] = value
        if actions:
            node["actions"] = actions

        try:
            children = el.get_children() if hasattr(el, "get_children") else []
            if children:
                node["children"] = []
                for child in children:
                    add_element(child, node["children"], depth + 1, current_path)
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
                        add_element(window, tree["children"], 0, "window")
                        break
                break
    except Exception:
        pass

    if was_truncated:
        tree["_truncated"] = True
        tree["_total_elements"] = element_index

    return tree


def _installed_linux_apps(limit: int = 80) -> list[dict[str, Any]]:
    from pathlib import Path

    dirs = [
        "/usr/share/applications",
        os.path.expanduser("~/.local/share/applications"),
        "/var/lib/flatpak/exports/share/applications",
        os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
    ]

    apps = []
    seen: set[str] = set()
    for dir_path in dirs:
        dir_obj = Path(dir_path)
        if not dir_obj.exists():
            continue
        for desktop_file in sorted(dir_obj.glob("*.desktop"))[:limit]:
            if desktop_file.name in seen:
                continue
            seen.add(desktop_file.name)
            try:
                name = None
                no_display = False
                with open(desktop_file) as f:
                    for line in f:
                        if line.startswith("Name="):
                            name = line.strip().split("=", 1)[1]
                        elif line.startswith("NoDisplay="):
                            no_display = line.strip().split("=", 1)[1].lower() == "true"
                        elif line.startswith("[") and line.strip() != "[Desktop Entry]":
                            break
                if name and not no_display:
                    apps.append({
                        "name": name,
                        "running": False,
                        "source": "desktop-file",
                        "desktop_file": str(desktop_file),
                    })
            except Exception:
                continue
            if len(apps) >= limit:
                return apps
    return apps


def _merge_app_lists(running: list[dict[str, Any]], installed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in installed:
        key = (item.get("name") or "").lower()
        merged[key] = item
    for item in running:
        key = (item.get("name") or "").lower()
        existing = merged.get(key, {})
        existing.update({k: v for k, v in item.items() if v is not None})
        existing["running"] = True
        merged[key] = existing
    return sorted(merged.values(), key=lambda a: (not a.get("running", False), (a.get("name") or "").lower()))


def _fallback_accessibility_tree(app_name: str, max_elements: int) -> dict[str, Any]:
    code, stdout, _ = _run(["wmctrl", "-l"])
    if code != 0:
        return {
            "element_index": "0", "role": "window", "title": app_name,
            "path": "window", "role_summary": "window", "visible": True, "children": [],
        }

    screen = _screen_size()
    screen_w, screen_h = screen["width"], screen["height"]

    ELEMENT_CACHE.clear()
    root_frame = {"x": 0, "y": 0, "width": 1920, "height": 1080, "center_x": 960, "center_y": 540}
    ELEMENT_CACHE["0"] = CachedElement(
        element=None,
        frame=root_frame,
        app=app_name, role="window", title=app_name,
    )

    children = []
    was_truncated = False
    for i, line in enumerate(stdout.splitlines()):
        if i + 1 >= max_elements:
            was_truncated = True
            break
        parts = line.split(None, 3)
        if len(parts) >= 4:
            wid = parts[0]
            title = parts[3]
            index_str = str(i + 1)

            frame = None
            geo_code, geo_stdout, _ = _run(["xdotool", "getwindowgeometry", "--shell", wid])
            if geo_code == 0:
                geo: dict[str, str] = {}
                for geo_line in geo_stdout.splitlines():
                    if "=" in geo_line:
                        k, v = geo_line.split("=", 1)
                        geo[k.strip()] = v.strip()
                if all(k in geo for k in ("X", "Y", "WIDTH", "HEIGHT")):
                    gx, gy, gw, gh = int(geo["X"]), int(geo["Y"]), int(geo["WIDTH"]), int(geo["HEIGHT"])
                    frame = {"x": gx, "y": gy, "width": gw, "height": gh, "center_x": gx + gw / 2, "center_y": gy + gh / 2}

            ELEMENT_CACHE[index_str] = CachedElement(
                element=None, frame=frame, app=app_name, role="window", title=title,
            )
            children.append({
                "element_index": index_str,
                "role": "window",
                "title": title,
                "path": "window/window",
                "role_summary": generate_role_summary("window", title),
                "visible": is_visible(frame, screen_w, screen_h),
            })

    tree: dict[str, Any] = {
        "element_index": "0",
        "role": "window",
        "title": app_name,
        "path": "window",
        "role_summary": "window",
        "visible": is_visible(root_frame, screen_w, screen_h),
        "children": children,
    }
    if was_truncated:
        tree["_truncated"] = True
        tree["_total_elements"] = 1 + len(children)
    return tree


class LinuxX11Backend(ComputerBackend):
    name = "linux-x11"

    def __init__(self) -> None:
        self._app = None

    def list_apps(self, **kwargs) -> list[dict[str, Any]]:
        include_installed = bool(kwargs.get("include_installed", False))

        apps = _list_apps()

        if include_installed:
            installed = _installed_linux_apps()
            apps = _merge_app_lists(apps, installed)

        return apps

    def activate_or_launch_app(self, app_name: str) -> dict[str, Any]:
        return _launch_or_activate_app(app_name)

    def capture_screenshot(self) -> tuple[str, int, int, str]:
        return capture_screenshot_png()

    def get_accessibility_tree(self, app_name: str, pid: int, **kwargs) -> dict[str, Any] | None:
        return _get_accessibility_tree(app_name, pid, **kwargs)

    def click(self, element_index: str | None, x: int | None, y: int | None, **kwargs) -> dict[str, Any]:
        button = normalize_button(str(kwargs.get("mouse_button", "left")))
        click_count = int(kwargs.get("click_count", 1))

        if element_index is not None:
            cached = element_from_index(str(element_index))
            if button == "left" and click_count == 1:
                try:
                    from gi.repository import Atspi  # type: ignore
                    if cached.element is not None:
                        action_iface = Atspi.Action
                        n_actions = action_iface.get_n_actions(cached.element)
                        for i in range(n_actions):
                            aname = action_iface.get_action_name(cached.element, i)
                            if aname and aname.lower() in ("press", "activate", "click"):
                                action_iface.do_action(cached.element, i)
                                return {"success": True, "method": "ATSPI-press", "element_index": str(element_index)}
                except Exception:
                    pass
            cx, cy = frame_center(cached.frame)
        else:
            if x is None or y is None:
                raise RuntimeError("click requires either element_index or both x and y")
            cx, cy = x, y

        pyautogui = require_pyautogui()
        pyautogui.click(x=cx, y=cy, clicks=max(click_count, 1), button=button, interval=0.08)
        return {"success": True, "method": "mouse", "x": cx, "y": cy, "button": button, "click_count": click_count}

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, **kwargs) -> dict[str, Any]:
        duration = float(kwargs.get("duration", 0.35))
        perform_drag(from_x, from_y, to_x, to_y, duration=duration)
        return {"success": True, "from": [from_x, from_y], "to": [to_x, to_y], "duration": duration}

    def press_key(self, key: str, **kwargs) -> dict[str, Any]:
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
        perform_scroll(x, y, direction, pages)
        return {"success": True, "element_index": element_index, "direction": direction, "pages": pages}

    def set_value(self, element_index: str, value: str, **kwargs) -> dict[str, Any]:
        cached = element_from_index(element_index)

        if cached.element is not None:
            try:
                from gi.repository import Atspi  # type: ignore
                value_iface = Atspi.Value
                if hasattr(value_iface, "set_value"):
                    try:
                        numeric = float(value)
                        result = value_iface.set_value(cached.element, numeric)
                        if result:
                            return {"success": True, "method": "ATSPI-Value", "element_index": element_index}
                    except (ValueError, TypeError):
                        pass
            except Exception:
                pass

        x, y = frame_center(cached.frame)
        pyautogui = require_pyautogui()
        pyautogui.click(x=x, y=y)
        _press_key_sequence("ctrl+a")
        method = _type_literal_text(value)
        return {"success": True, "method": f"click-select-{method}", "element_index": element_index}

    def perform_action(self, element_index: str, action: str, **kwargs) -> dict[str, Any]:
        cached = element_from_index(element_index)
        if cached.element is None:
            raise RuntimeError(f"No ATSPI element for index {element_index}")

        try:
            from gi.repository import Atspi  # type: ignore
        except Exception:
            raise RuntimeError("ATSPI not available for action execution") from None

        action_iface = Atspi.Action
        try:
            n_actions = action_iface.get_n_actions(cached.element)
        except Exception:
            n_actions = 0
        available = []
        for i in range(n_actions):
            try:
                aname = action_iface.get_action_name(cached.element, i)
                available.append(str(aname))
            except Exception:
                pass

        normalized = action.lower().replace("_", "").replace("-", "")
        matched_action = None
        matched_index = None
        for i, name in enumerate(available):
            stripped = name.lower().replace("_", "").replace("-", "")
            if normalized == stripped or normalized == name.lower():
                matched_action = name
                matched_index = i
                break

        if matched_index is None:
            for i, name in enumerate(available):
                if name.lower().startswith(normalized[:4]):
                    matched_action = name
                    matched_index = i
                    break

        if matched_index is None:
            raise RuntimeError(f"Action {action!r} not found. Available: {available}")

        success = action_iface.do_action(cached.element, matched_index)
        return {"success": bool(success), "element_index": element_index, "action": matched_action}

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
