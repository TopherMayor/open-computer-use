from __future__ import annotations

import os
import re
import subprocess
import time
from typing import Any

from ..types import CachedElement, ELEMENT_CACHE, clear_cache, element_from_index, frame_center
from .base import ComputerBackend
from .input_utils import KEY_ALIASES, normalize_button, require_pyautogui, capture_screenshot_png, perform_scroll, perform_drag


def import_appkit() -> Any:
    try:
        import AppKit  # type: ignore

        return AppKit
    except Exception:
        return None


def import_quartz() -> Any:
    try:
        import Quartz  # type: ignore

        return Quartz
    except Exception:
        return None


def ax_const(name: str, fallback: str) -> str:
    quartz = import_quartz()
    return getattr(quartz, name, fallback) if quartz is not None else fallback


AX_CHILDREN = ax_const("kAXChildrenAttribute", "AXChildren")
AX_VISIBLE_CHILDREN = ax_const("kAXVisibleChildrenAttribute", "AXVisibleChildren")
AX_WINDOWS = ax_const("kAXWindowsAttribute", "AXWindows")
AX_FOCUSED_WINDOW = ax_const("kAXFocusedWindowAttribute", "AXFocusedWindow")
AX_ROLE = ax_const("kAXRoleAttribute", "AXRole")
AX_SUBROLE = ax_const("kAXSubroleAttribute", "AXSubrole")
AX_TITLE = ax_const("kAXTitleAttribute", "AXTitle")
AX_DESCRIPTION = ax_const("kAXDescriptionAttribute", "AXDescription")
AX_HELP = ax_const("kAXHelpAttribute", "AXHelp")
AX_VALUE = ax_const("kAXValueAttribute", "AXValue")
AX_PLACEHOLDER = ax_const("kAXPlaceholderValueAttribute", "AXPlaceholderValue")
AX_ENABLED = ax_const("kAXEnabledAttribute", "AXEnabled")
AX_FOCUSED = ax_const("kAXFocusedAttribute", "AXFocused")
AX_POSITION = ax_const("kAXPositionAttribute", "AXPosition")
AX_SIZE = ax_const("kAXSizeAttribute", "AXSize")
AX_PRESS = ax_const("kAXPressAction", "AXPress")


def scalarize(value: Any, max_len: int = 240) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, (str, os.PathLike)):
        text = str(value)
        return text if len(text) <= max_len else text[: max_len - 3] + "..."
    if isinstance(value, (list, tuple)):
        out = [scalarize(item, max_len=80) for item in value[:8]]
        if len(value) > 8:
            out.append(f"... {len(value) - 8} more")
        return out
    text = str(value)
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def ax_copy(element: Any, attribute: str) -> Any | None:
    quartz = import_quartz()
    if quartz is None or element is None:
        return None

    try:
        result = quartz.AXUIElementCopyAttributeValue(element, attribute, None)
    except TypeError:
        try:
            result = quartz.AXUIElementCopyAttributeValue(element, attribute)
        except Exception:
            return None
    except Exception:
        return None

    if isinstance(result, tuple):
        if len(result) >= 2:
            err, value = result[0], result[1]
            return value if err == 0 else None
        return None
    return result


def ax_actions(element: Any) -> list[str]:
    quartz = import_quartz()
    if quartz is None or element is None:
        return []

    try:
        result = quartz.AXUIElementCopyActionNames(element, None)
    except TypeError:
        try:
            result = quartz.AXUIElementCopyActionNames(element)
        except Exception:
            return []
    except Exception:
        return []

    if isinstance(result, tuple):
        if len(result) >= 2 and result[0] == 0 and result[1] is not None:
            return [str(action) for action in result[1]]
        return []
    return [str(action) for action in result or []]


def ax_perform(element: Any, action: str) -> bool:
    quartz = import_quartz()
    if quartz is None or element is None:
        return False

    try:
        result = quartz.AXUIElementPerformAction(element, action)
    except Exception:
        return False

    if isinstance(result, tuple):
        return bool(result and result[0] == 0)
    return result == 0 or result is None


def ax_set(element: Any, attribute: str, value: Any) -> bool:
    quartz = import_quartz()
    if quartz is None or element is None:
        return False

    try:
        result = quartz.AXUIElementSetAttributeValue(element, attribute, value)
    except Exception:
        return False

    if isinstance(result, tuple):
        return bool(result and result[0] == 0)
    return result == 0 or result is None


def ax_unpack_value(value: Any, kind_name: str) -> Any | None:
    quartz = import_quartz()
    if quartz is None or value is None:
        return None

    kind = getattr(quartz, kind_name, None)
    if kind is None:
        return None

    try:
        result = quartz.AXValueGetValue(value, kind, None)
    except TypeError:
        try:
            result = quartz.AXValueGetValue(value, kind)
        except Exception:
            return None
    except Exception:
        return None

    if isinstance(result, tuple):
        if len(result) >= 2 and result[0]:
            return result[1]
        if len(result) == 1:
            return result[0]
        return None
    return result


def point_to_xy(point: Any) -> tuple[float, float] | None:
    if point is None:
        return None
    if hasattr(point, "x") and hasattr(point, "y"):
        return float(point.x), float(point.y)
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        return float(point[0]), float(point[1])
    return None


def size_to_wh(size: Any) -> tuple[float, float] | None:
    if size is None:
        return None
    if hasattr(size, "width") and hasattr(size, "height"):
        return float(size.width), float(size.height)
    if isinstance(size, (list, tuple)) and len(size) >= 2:
        return float(size[0]), float(size[1])
    return None


def ax_frame(element: Any) -> dict[str, float] | None:
    pos = point_to_xy(ax_unpack_value(ax_copy(element, AX_POSITION), "kAXValueCGPointType"))
    size = size_to_wh(ax_unpack_value(ax_copy(element, AX_SIZE), "kAXValueCGSizeType"))
    if pos is None or size is None:
        return None

    x, y = pos
    width, height = size
    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "width": round(width, 2),
        "height": round(height, 2),
        "center_x": round(x + width / 2, 2),
        "center_y": round(y + height / 2, 2),
    }


def is_ax_trusted() -> bool | None:
    quartz = import_quartz()
    if quartz is None:
        return None
    try:
        return bool(quartz.AXIsProcessTrusted())
    except Exception:
        return None


def screen_size() -> dict[str, int]:
    try:
        size = require_pyautogui().size()
        return {"width": int(size[0]), "height": int(size[1])}
    except Exception:
        return {"width": 0, "height": 0}


def _running_apps() -> list[dict[str, Any]]:
    appkit = import_appkit()
    apps = []
    if appkit is not None:
        for app in appkit.NSWorkspace.sharedWorkspace().runningApplications():
            name = app.localizedName()
            bundle_id = app.bundleIdentifier()
            pid = int(app.processIdentifier())
            if not name and not bundle_id:
                continue
            launch_date = app.launchDate()
            apps.append(
                {
                    "name": str(name) if name else str(bundle_id),
                    "bundleIdentifier": str(bundle_id) if bundle_id else None,
                    "pid": pid,
                    "running": True,
                    "active": bool(app.isActive()),
                    "hidden": bool(app.isHidden()),
                    "launchDate": str(launch_date) if launch_date is not None else None,
                    "source": "NSWorkspace",
                }
            )

    if not apps:
        apps = _running_apps_from_cgwindows()
    if not apps:
        apps = _running_apps_from_osascript()
    if not apps:
        apps = _running_apps_from_ps()

    apps.sort(key=lambda item: (not item.get("active", False), (item.get("name") or "").lower()))
    return apps


def _running_apps_from_cgwindows() -> list[dict[str, Any]]:
    quartz = import_quartz()
    if quartz is None:
        return []

    try:
        infos = quartz.CGWindowListCopyWindowInfo(
            getattr(quartz, "kCGWindowListOptionOnScreenOnly", 1),
            getattr(quartz, "kCGNullWindowID", 0),
        )
    except Exception:
        return []

    if not infos:
        return []

    by_pid: dict[int, dict[str, Any]] = {}
    for info in infos:
        name = info.get("kCGWindowOwnerName")
        pid = info.get("kCGWindowOwnerPID")
        if not name or pid is None:
            continue
        pid_int = int(pid)
        item = by_pid.setdefault(
            pid_int,
            {
                "name": str(name),
                "bundleIdentifier": None,
                "pid": pid_int,
                "running": True,
                "active": False,
                "windowCount": 0,
                "source": "CGWindowList",
            },
        )
        item["windowCount"] += 1
    return list(by_pid.values())


def _running_apps_from_osascript() -> list[dict[str, Any]]:
    script = (
        'tell application "System Events" to get name of every process whose background only is false'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except Exception:
        return []

    names = []
    for part in re.split(r",|\n", result.stdout):
        name = part.strip()
        if name:
            names.append(name)

    return [{"name": name, "bundleIdentifier": None, "running": True, "source": "osascript"} for name in names]


def _running_apps_from_ps() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,comm="],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except Exception:
        return []

    apps = []
    seen: set[tuple[int, str]] = set()
    for line in result.stdout.splitlines():
        match = re.match(r"\s*(\d+)\s+(.+?\.app)/Contents/MacOS/(.+)$", line)
        if not match:
            continue
        pid = int(match.group(1))
        app_path = match.group(2)
        executable = match.group(3)
        from pathlib import Path
        name = Path(app_path).stem or executable
        key = (pid, name)
        if key in seen:
            continue
        seen.add(key)
        apps.append(
            {
                "name": name,
                "bundleIdentifier": None,
                "pid": pid,
                "path": app_path,
                "running": True,
                "active": False,
                "source": "ps",
            }
        )
    return apps


def _installed_apps(limit: int = 80) -> list[dict[str, Any]]:
    from pathlib import Path

    roots = [Path("/Applications"), Path("/System/Applications"), Path.home() / "Applications"]
    apps = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.app"))[:limit]:
            apps.append(
                {
                    "name": path.stem,
                    "bundleIdentifier": None,
                    "path": str(path),
                    "running": False,
                    "source": "filesystem",
                }
            )
            if len(apps) >= limit:
                return apps
    return apps


def _recent_apps(days: int = 14, limit: int = 60) -> list[dict[str, Any]]:
    query = (
        'kMDItemContentType == "com.apple.application-bundle" '
        f'&& kMDItemLastUsedDate >= $time.now(-{max(days, 1) * 24 * 60 * 60})'
    )
    try:
        result = subprocess.run(
            ["mdfind", query],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return []

    apps = []
    from pathlib import Path
    for path in [line.strip() for line in result.stdout.splitlines() if line.strip()][:limit]:
        try:
            meta = subprocess.run(
                [
                    "mdls",
                    "-raw",
                    "-name",
                    "kMDItemDisplayName",
                    "-name",
                    "kMDItemCFBundleIdentifier",
                    "-name",
                    "kMDItemLastUsedDate",
                    "-name",
                    "kMDItemUseCount",
                    path,
                ],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            lines = [line.strip() for line in meta.stdout.splitlines()]
        except Exception:
            lines = []

        name = Path(path).stem
        bundle_id = None
        last_used = None
        use_count = None
        if len(lines) >= 1 and lines[0] and lines[0] != "(null)":
            name = lines[0]
        if len(lines) >= 2 and lines[1] and lines[1] != "(null)":
            bundle_id = lines[1]
        if len(lines) >= 3 and lines[2] and lines[2] != "(null)":
            last_used = lines[2]
        if len(lines) >= 4 and lines[3] and lines[3] != "(null)":
            use_count = lines[3]

        apps.append(
            {
                "name": name,
                "bundleIdentifier": bundle_id,
                "path": path,
                "running": False,
                "lastUsed": last_used,
                "usageFrequency": use_count,
                "source": "Spotlight",
            }
        )
    return apps


def _merge_app_lists(running: list[dict[str, Any]], recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    def key(item: dict[str, Any]) -> str:
        return (item.get("bundleIdentifier") or item.get("name") or item.get("path") or "").lower()

    for item in recent:
        merged[key(item)] = item
    for item in running:
        existing = merged.get(key(item), {})
        existing.update({field: value for field, value in item.items() if value is not None})
        existing["running"] = True
        merged[key(item)] = existing

    return sorted(merged.values(), key=lambda item: (not item.get("running", False), (item.get("name") or "").lower()))


def _find_running_app(app_name: str) -> dict[str, Any] | None:
    needle = app_name.lower().strip()
    if not needle:
        return None

    apps = _running_apps()
    for app in apps:
        if needle in {
            str(app.get("name") or "").lower(),
            str(app.get("bundleIdentifier") or "").lower(),
        }:
            return app
    for app in apps:
        name = str(app.get("name") or "").lower()
        bundle_id = str(app.get("bundleIdentifier") or "").lower()
        if needle in name or needle in bundle_id:
            return app
    return None


def _pid_from_osascript(app_name: str) -> int | None:
    escaped = app_name.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
    tell application "System Events"
      set candidateProcesses to application processes whose bundle identifier is "{escaped}"
      if (count of candidateProcesses) is 0 then
        set candidateProcesses to application processes whose name is "{escaped}"
      end if
      if (count of candidateProcesses) is greater than 0 then
        return unix id of item 1 of candidateProcesses
      end if
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except Exception:
        return None

    text = result.stdout.strip()
    return int(text) if text.isdigit() else None


def _pid_from_pgrep(app_name: str) -> int | None:
    try:
        result = subprocess.run(
            ["pgrep", "-if", app_name],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except Exception:
        return None

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def _launch_or_activate_app(app_name: str) -> dict[str, Any]:
    app = _find_running_app(app_name)
    if app is None:
        command = ["open", "-b", app_name] if "." in app_name and "/" not in app_name else ["open", "-a", app_name]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"Could not launch app {app_name!r}")
        time.sleep(0.8)
        app = _find_running_app(app_name)

    if app is None:
        pid = _pid_from_osascript(app_name) or _pid_from_pgrep(app_name)
        if pid is None:
            raise RuntimeError(f"Could not find running app {app_name!r}")
        app = {
            "name": app_name,
            "bundleIdentifier": app_name if "." in app_name else None,
            "pid": pid,
            "running": True,
            "active": False,
            "source": "pid-fallback",
        }

    appkit = import_appkit()
    if appkit is not None and app.get("pid") is not None:
        try:
            running_app = appkit.NSRunningApplication.runningApplicationWithProcessIdentifier_(int(app["pid"]))
            if running_app is not None:
                options = getattr(appkit, "NSApplicationActivateIgnoringOtherApps", 1)
                running_app.activateWithOptions_(options)
                time.sleep(0.25)
        except Exception:
            pass
    else:
        try:
            subprocess.run(
                ["osascript", "-e", f'tell application "{app_name}" to activate'],
                capture_output=True,
                timeout=5,
                check=False,
            )
            time.sleep(0.25)
        except Exception:
            pass

    return app


def _app_ax_element(pid: int) -> Any | None:
    quartz = import_quartz()
    if quartz is None:
        return None
    try:
        return quartz.AXUIElementCreateApplication(pid)
    except Exception:
        return None


def _focused_or_first_window(app_element: Any) -> Any | None:
    window = ax_copy(app_element, AX_FOCUSED_WINDOW)
    if window is not None:
        return window
    windows = ax_copy(app_element, AX_WINDOWS)
    if isinstance(windows, (list, tuple)) and windows:
        return windows[0]
    return None


def _child_elements(element: Any) -> list[Any]:
    children: list[Any] = []
    for attribute in (AX_CHILDREN, AX_VISIBLE_CHILDREN):
        value = ax_copy(element, attribute)
        if isinstance(value, (list, tuple)):
            for child in value:
                if child not in children:
                    children.append(child)
    return children


def _build_accessibility_tree(
    element: Any,
    app_name: str,
    *,
    max_depth: int,
    max_elements: int,
    depth: int = 0,
) -> dict[str, Any] | None:
    if element is None or len(ELEMENT_CACHE) >= max_elements:
        return None

    element_index = str(len(ELEMENT_CACHE))
    role = scalarize(ax_copy(element, AX_ROLE))
    title = scalarize(ax_copy(element, AX_TITLE))
    frame = ax_frame(element)
    ELEMENT_CACHE[element_index] = CachedElement(
        element=element,
        frame=frame,
        app=app_name,
        role=str(role) if role is not None else None,
        title=str(title) if title is not None else None,
    )

    node: dict[str, Any] = {"element_index": element_index}

    fields = {
        "role": role,
        "subrole": scalarize(ax_copy(element, AX_SUBROLE)),
        "title": title,
        "description": scalarize(ax_copy(element, AX_DESCRIPTION)),
        "help": scalarize(ax_copy(element, AX_HELP)),
        "value": scalarize(ax_copy(element, AX_VALUE)),
        "placeholder": scalarize(ax_copy(element, AX_PLACEHOLDER)),
        "enabled": scalarize(ax_copy(element, AX_ENABLED)),
        "focused": scalarize(ax_copy(element, AX_FOCUSED)),
        "frame": frame,
    }
    for key, value in fields.items():
        if value not in (None, "", []):
            node[key] = value

    actions = ax_actions(element)
    if actions:
        node["actions"] = actions

    if depth < max_depth and len(ELEMENT_CACHE) < max_elements:
        children = []
        for child in _child_elements(element):
            child_node = _build_accessibility_tree(
                child,
                app_name,
                max_depth=max_depth,
                max_elements=max_elements,
                depth=depth + 1,
            )
            if child_node is not None:
                children.append(child_node)
            if len(ELEMENT_CACHE) >= max_elements:
                break
        if children:
            node["children"] = children

    return node


MODIFIER_ALIASES = {
    "super": "command",
    "cmd": "command",
    "command": "command",
    "meta": "command",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "option",
    "option": "option",
    "shift": "shift",
}


def normalize_key_token(token: str) -> str:
    token = token.strip().replace("-", "_")
    if len(token) == 4 and token.lower().startswith("kp_"):
        return token[-1]
    lowered = token.lower()
    return MODIFIER_ALIASES.get(lowered) or KEY_ALIASES.get(lowered) or lowered


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

    old_clipboard = ""
    clipboard_loaded = False
    try:
        old_clipboard = subprocess.run(
            ["pbpaste"], capture_output=True, text=True, timeout=2, check=False
        ).stdout
        clipboard_loaded = True
        subprocess.run(["pbcopy"], input=text, text=True, timeout=2, check=True)
        _press_key_sequence("super+v")
        time.sleep(0.1)
        return "clipboard-paste"
    finally:
        if clipboard_loaded:
            try:
                subprocess.run(["pbcopy"], input=old_clipboard, text=True, timeout=2, check=False)
            except Exception:
                pass


def _normalize_ax_action(action: str, available: list[str]) -> str:
    if not action:
        raise RuntimeError("action is required")
    if action in available:
        return action
    normalized = action.lower().replace("_", "").replace("-", "")
    for candidate in available:
        stripped = candidate.lower().removeprefix("ax").replace("_", "").replace("-", "")
        if normalized == stripped or normalized == candidate.lower():
            return candidate
    if action.startswith("AX"):
        return action
    return "AX" + action[:1].upper() + action[1:]


class MacOSBackend(ComputerBackend):
    name = "macos"

    def list_apps(self, **kwargs) -> list[dict[str, Any]]:
        days = int(kwargs.get("recent_days", 14))
        include_recent = bool(kwargs.get("include_recent", True))
        include_installed = bool(kwargs.get("include_installed", False))
        running = _running_apps()
        recent = _recent_apps(days=days) if include_recent else []
        installed = _installed_apps() if include_installed or (not running and not recent) else []
        return _merge_app_lists(running, recent + installed)

    def activate_or_launch_app(self, app_name: str) -> dict[str, Any]:
        return _launch_or_activate_app(app_name)

    def capture_screenshot(self) -> tuple[str, int, int, str]:
        return capture_screenshot_png()

    def get_accessibility_tree(self, app_name: str, pid: int, **kwargs) -> dict[str, Any] | None:
        max_depth = int(kwargs.get("max_depth", 7))
        max_elements = int(kwargs.get("max_elements", 220))
        ax_app = _app_ax_element(pid)
        window = _focused_or_first_window(ax_app)
        return _build_accessibility_tree(
            window or ax_app,
            app_name,
            max_depth=max_depth,
            max_elements=max_elements,
        )

    def click(self, element_index: str | None, x: int | None, y: int | None, **kwargs) -> dict[str, Any]:
        button = normalize_button(str(kwargs.get("mouse_button", "left")))
        click_count = int(kwargs.get("click_count", 1))

        if element_index is not None:
            cached = element_from_index(str(element_index))
            if button == "left" and click_count == 1 and AX_PRESS in ax_actions(cached.element):
                if ax_perform(cached.element, AX_PRESS):
                    return {"success": True, "method": "AXPress", "element_index": str(element_index)}
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

        if ax_set(cached.element, AX_VALUE, value):
            return {"success": True, "method": "AXValue", "element_index": element_index}

        x, y = frame_center(cached.frame)
        pyautogui = require_pyautogui()
        pyautogui.click(x=x, y=y)
        _press_key_sequence("super+a")
        method = _type_literal_text(value)
        return {"success": True, "method": f"click-select-{method}", "element_index": element_index}

    def perform_action(self, element_index: str, action: str, **kwargs) -> dict[str, Any]:
        cached = element_from_index(element_index)
        available = ax_actions(cached.element)
        ax_action = _normalize_ax_action(action, available)
        if not ax_perform(cached.element, ax_action):
            raise RuntimeError(f"Could not perform {ax_action!r}. Available actions: {available}")
        return {"success": True, "element_index": element_index, "action": ax_action}

    def screen_size(self) -> dict[str, int]:
        return screen_size()

    def is_accessibility_trusted(self) -> bool | None:
        return is_ax_trusted()

    def clear_cache(self) -> None:
        clear_cache()

    def flat_elements(self) -> list[dict[str, Any]]:
        from ..types import flat_elements as fe
        return fe()

    def element_from_index(self, index: str) -> Any:
        return element_from_index(index)


def create_backend() -> MacOSBackend:
    return MacOSBackend()