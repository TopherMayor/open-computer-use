#!/usr/bin/env python3
"""
Self-hosted Computer Use MCP server.

This intentionally avoids a runtime dependency on the Python MCP SDK so the
plugin can run anywhere Python plus the desktop automation dependencies are
available. It implements the small JSON-RPC surface Codex needs:
initialize, tools/list, and tools/call over stdio.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


SERVER_NAME = "gsd-computer-use"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"
DEFAULT_MAX_DEPTH = 7
DEFAULT_MAX_ELEMENTS = 220


@dataclass
class CachedElement:
    element: Any
    frame: dict[str, float] | None
    app: str | None
    role: str | None = None
    title: str | None = None


ELEMENT_CACHE: dict[str, CachedElement] = {}
LAST_APP: str | None = None


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def ok_text(data: Any) -> dict[str, Any]:
    text = data if isinstance(data, str) else pretty_json(data)
    return {"content": [{"type": "text", "text": text}]}


def ok_content(content: list[dict[str, Any]]) -> dict[str, Any]:
    return {"content": content}


def error_result(message: str, details: Any | None = None) -> dict[str, Any]:
    payload = {"error": message}
    if details is not None:
        payload["details"] = details
    return {"isError": True, "content": [{"type": "text", "text": pretty_json(payload)}]}


def require_pyautogui():
    try:
        import pyautogui  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on host setup
        raise RuntimeError(
            "pyautogui is required for desktop input. Run `pip install -r requirements.txt`."
        ) from exc

    pyautogui.FAILSAFE = True
    return pyautogui


def import_appkit():
    try:
        import AppKit  # type: ignore

        return AppKit
    except Exception:
        return None


def import_quartz():
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
    if isinstance(value, (str, Path)):
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


def capture_screenshot_png() -> tuple[str, int, int, str]:
    try:
        pyautogui = require_pyautogui()
        image = pyautogui.screenshot()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii"), image.width, image.height, "pyautogui"
    except Exception:
        pass

    try:
        import mss  # type: ignore
        import mss.tools  # type: ignore

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            sct_img = sct.grab(monitor)
            data = mss.tools.to_png(sct_img.rgb, sct_img.size)
            return base64.b64encode(data).decode("ascii"), sct_img.width, sct_img.height, "mss"
    except Exception as exc:
        raise RuntimeError(
            "Could not capture a screenshot. Install pyautogui or mss and grant Screen Recording permission."
        ) from exc


def running_apps() -> list[dict[str, Any]]:
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
        apps = running_apps_from_cgwindows()
    if not apps:
        apps = running_apps_from_osascript()
    if not apps:
        apps = running_apps_from_ps()

    apps.sort(key=lambda item: (not item.get("active", False), (item.get("name") or "").lower()))
    return apps


def running_apps_from_cgwindows() -> list[dict[str, Any]]:
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


def running_apps_from_osascript() -> list[dict[str, Any]]:
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


def running_apps_from_ps() -> list[dict[str, Any]]:
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


def installed_apps(limit: int = 80) -> list[dict[str, Any]]:
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


def recent_apps(days: int = 14, limit: int = 60) -> list[dict[str, Any]]:
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


def merge_app_lists(running: list[dict[str, Any]], recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def find_running_app(app_name: str) -> dict[str, Any] | None:
    needle = app_name.lower().strip()
    if not needle:
        return None

    apps = running_apps()
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


def pid_from_osascript(app_name: str) -> int | None:
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


def pid_from_pgrep(app_name: str) -> int | None:
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


def launch_or_activate_app(app_name: str) -> dict[str, Any]:
    app = find_running_app(app_name)
    if app is None:
        command = ["open", "-b", app_name] if "." in app_name and "/" not in app_name else ["open", "-a", app_name]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"Could not launch app {app_name!r}")
        time.sleep(0.8)
        app = find_running_app(app_name)

    if app is None:
        pid = pid_from_osascript(app_name) or pid_from_pgrep(app_name)
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


def app_ax_element(pid: int) -> Any | None:
    quartz = import_quartz()
    if quartz is None:
        return None
    try:
        return quartz.AXUIElementCreateApplication(pid)
    except Exception:
        return None


def focused_or_first_window(app_element: Any) -> Any | None:
    window = ax_copy(app_element, AX_FOCUSED_WINDOW)
    if window is not None:
        return window
    windows = ax_copy(app_element, AX_WINDOWS)
    if isinstance(windows, (list, tuple)) and windows:
        return windows[0]
    return None


def child_elements(element: Any) -> list[Any]:
    children: list[Any] = []
    for attribute in (AX_CHILDREN, AX_VISIBLE_CHILDREN):
        value = ax_copy(element, attribute)
        if isinstance(value, (list, tuple)):
            for child in value:
                if child not in children:
                    children.append(child)
    return children


def build_accessibility_tree(
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
        for child in child_elements(element):
            child_node = build_accessibility_tree(
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


def press_key_sequence(key: str) -> None:
    pyautogui = require_pyautogui()
    parts = [normalize_key_token(part) for part in re.split(r"\+", key) if part.strip()]
    if not parts:
        raise RuntimeError("key must not be empty")
    if len(parts) == 1:
        pyautogui.press(parts[0])
    else:
        pyautogui.hotkey(*parts)


def type_literal_text(text: str) -> str:
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
        press_key_sequence("super+v")
        time.sleep(0.1)
        return "clipboard-paste"
    finally:
        if clipboard_loaded:
            try:
                subprocess.run(["pbcopy"], input=old_clipboard, text=True, timeout=2, check=False)
            except Exception:
                pass


def tool_get_app_state(args: dict[str, Any]) -> dict[str, Any]:
    global LAST_APP

    app_name = str(args.get("app") or "").strip()
    if not app_name:
        raise RuntimeError("app is required")

    max_depth = int(args.get("max_depth", DEFAULT_MAX_DEPTH))
    max_elements = int(args.get("max_elements", DEFAULT_MAX_ELEMENTS))
    include_screenshot = bool(args.get("include_screenshot", True))

    app = launch_or_activate_app(app_name)
    LAST_APP = app_name
    ELEMENT_CACHE.clear()

    screenshot_content: dict[str, Any] | None = None
    screenshot_meta: dict[str, Any] | None = None
    if include_screenshot:
        image_b64, width, height, capture_backend = capture_screenshot_png()
        screenshot_content = {"type": "image", "data": image_b64, "mimeType": "image/png"}
        screenshot_meta = {
            "width": width,
            "height": height,
            "backend": capture_backend,
            "coordinateSystem": "pyautogui screen coordinates",
        }

    tree = None
    if app.get("pid") is not None:
        ax_app = app_ax_element(int(app["pid"]))
        window = focused_or_first_window(ax_app)
        tree = build_accessibility_tree(
            window or ax_app,
            app_name,
            max_depth=max_depth,
            max_elements=max_elements,
        )

    payload = {
        "app": app,
        "screen": screen_size(),
        "screenshot": screenshot_meta,
        "accessibilityTrusted": is_ax_trusted(),
        "accessibilityTree": tree,
        "flatElements": flat_elements(),
        "elementCount": len(ELEMENT_CACHE),
        "notes": [
            "Use element_index values from this response for click, scroll, set_value, and perform_secondary_action.",
            "If accessibilityTrusted is false, grant Accessibility permission to the process launching this MCP server.",
        ],
    }

    content = []
    if screenshot_content is not None:
        content.append(screenshot_content)
    content.append({"type": "text", "text": pretty_json(payload)})
    return ok_content(content)


def tool_list_apps(args: dict[str, Any]) -> dict[str, Any]:
    days = int(args.get("recent_days", 14))
    include_recent = bool(args.get("include_recent", True))
    include_installed = bool(args.get("include_installed", False))
    running = running_apps()
    recent = recent_apps(days=days) if include_recent else []
    installed = installed_apps() if include_installed or (not running and not recent) else []
    return ok_text(
        {
            "runningCount": len(running),
            "recentCount": len(recent),
            "installedCount": len(installed),
            "apps": merge_app_lists(running, recent + installed),
        }
    )


def tool_click(args: dict[str, Any]) -> dict[str, Any]:
    app_name = str(args.get("app") or LAST_APP or "").strip()
    if app_name:
        launch_or_activate_app(app_name)

    pyautogui = require_pyautogui()
    button = normalize_button(str(args.get("mouse_button", "left")))
    click_count = int(args.get("click_count", 1))
    element_index = args.get("element_index")

    if element_index is not None:
        cached = element_from_index(str(element_index))
        if button == "left" and click_count == 1 and AX_PRESS in ax_actions(cached.element):
            if ax_perform(cached.element, AX_PRESS):
                return ok_text({"success": True, "method": "AXPress", "element_index": str(element_index)})
        x, y = frame_center(cached.frame)
    else:
        if args.get("x") is None or args.get("y") is None:
            raise RuntimeError("click requires either element_index or both x and y")
        x, y = int(args["x"]), int(args["y"])

    pyautogui.click(x=x, y=y, clicks=max(click_count, 1), button=button, interval=0.08)
    return ok_text({"success": True, "method": "mouse", "x": x, "y": y, "button": button, "click_count": click_count})


def tool_drag(args: dict[str, Any]) -> dict[str, Any]:
    app_name = str(args.get("app") or LAST_APP or "").strip()
    if app_name:
        launch_or_activate_app(app_name)

    pyautogui = require_pyautogui()
    from_x = int(args["from_x"])
    from_y = int(args["from_y"])
    to_x = int(args["to_x"])
    to_y = int(args["to_y"])
    duration = float(args.get("duration", 0.35))
    pyautogui.moveTo(from_x, from_y)
    pyautogui.dragTo(to_x, to_y, duration=duration, button="left")
    return ok_text({"success": True, "from": [from_x, from_y], "to": [to_x, to_y], "duration": duration})


def tool_press_key(args: dict[str, Any]) -> dict[str, Any]:
    app_name = str(args.get("app") or LAST_APP or "").strip()
    if app_name:
        launch_or_activate_app(app_name)

    key = str(args.get("key") or "")
    press_key_sequence(key)
    return ok_text({"success": True, "key": key})


def tool_type_text(args: dict[str, Any]) -> dict[str, Any]:
    app_name = str(args.get("app") or LAST_APP or "").strip()
    if app_name:
        launch_or_activate_app(app_name)

    text = str(args.get("text") or "")
    method = type_literal_text(text)
    return ok_text({"success": True, "chars": len(text), "method": method})


def tool_scroll(args: dict[str, Any]) -> dict[str, Any]:
    app_name = str(args.get("app") or LAST_APP or "").strip()
    if app_name:
        launch_or_activate_app(app_name)

    pyautogui = require_pyautogui()
    direction = str(args.get("direction", "down")).lower()
    pages = float(args.get("pages", 1))
    element_index = str(args.get("element_index"))
    cached = element_from_index(element_index)
    x, y = frame_center(cached.frame)
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

    return ok_text({"success": True, "element_index": element_index, "direction": direction, "pages": pages})


def tool_set_value(args: dict[str, Any]) -> dict[str, Any]:
    app_name = str(args.get("app") or LAST_APP or "").strip()
    if app_name:
        launch_or_activate_app(app_name)

    element_index = str(args.get("element_index"))
    value = str(args.get("value") or "")
    cached = element_from_index(element_index)

    if ax_set(cached.element, AX_VALUE, value):
        return ok_text({"success": True, "method": "AXValue", "element_index": element_index})

    x, y = frame_center(cached.frame)
    pyautogui = require_pyautogui()
    pyautogui.click(x=x, y=y)
    press_key_sequence("super+a")
    method = type_literal_text(value)
    return ok_text({"success": True, "method": f"click-select-{method}", "element_index": element_index})


def normalize_ax_action(action: str, available: list[str]) -> str:
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


def tool_perform_secondary_action(args: dict[str, Any]) -> dict[str, Any]:
    app_name = str(args.get("app") or LAST_APP or "").strip()
    if app_name:
        launch_or_activate_app(app_name)

    element_index = str(args.get("element_index"))
    action = str(args.get("action") or "")
    cached = element_from_index(element_index)
    available = ax_actions(cached.element)
    ax_action = normalize_ax_action(action, available)
    if not ax_perform(cached.element, ax_action):
        raise RuntimeError(f"Could not perform {ax_action!r}. Available actions: {available}")
    return ok_text({"success": True, "element_index": element_index, "action": ax_action})


TOOL_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "get_app_state": tool_get_app_state,
    "list_apps": tool_list_apps,
    "click": tool_click,
    "drag": tool_drag,
    "press_key": tool_press_key,
    "type_text": tool_type_text,
    "scroll": tool_scroll,
    "set_value": tool_set_value,
    "perform_secondary_action": tool_perform_secondary_action,
}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_app_state",
        "description": "Start an app use session if needed, then get the state of the app's key window and return a screenshot plus indexed accessibility tree.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "max_depth": {"type": "integer", "minimum": 1, "maximum": 12, "default": DEFAULT_MAX_DEPTH},
                "max_elements": {"type": "integer", "minimum": 10, "maximum": 1000, "default": DEFAULT_MAX_ELEMENTS},
                "include_screenshot": {"type": "boolean", "default": True},
            },
            "required": ["app"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_apps",
        "description": "List running macOS apps and optionally Spotlight-discovered apps used recently.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_recent": {"type": "boolean", "default": True},
                "recent_days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 14},
                "include_installed": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "click",
        "description": "Click an element by index from get_app_state or by screenshot pixel coordinates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "x": {"type": "number", "description": "Screenshot x coordinate."},
                "y": {"type": "number", "description": "Screenshot y coordinate."},
                "click_count": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1},
                "mouse_button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
            },
            "required": ["app"],
            "additionalProperties": False,
        },
    },
    {
        "name": "drag",
        "description": "Drag from one screenshot coordinate to another.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "from_x": {"type": "number"},
                "from_y": {"type": "number"},
                "to_x": {"type": "number"},
                "to_y": {"type": "number"},
                "duration": {"type": "number", "minimum": 0, "default": 0.35},
            },
            "required": ["app", "from_x", "from_y", "to_x", "to_y"],
            "additionalProperties": False,
        },
    },
    {
        "name": "press_key",
        "description": "Press a key or key combination using xdotool-like syntax, such as super+c, Return, Tab, Up, or KP_0.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "key": {"type": "string", "description": "Key or key combination."},
            },
            "required": ["app", "key"],
            "additionalProperties": False,
        },
    },
    {
        "name": "type_text",
        "description": "Type literal text into the active app.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "text": {"type": "string", "description": "Text to type."},
            },
            "required": ["app", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "scroll",
        "description": "Scroll an element from the latest get_app_state response.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                "pages": {"type": "number", "minimum": 0, "default": 1},
            },
            "required": ["app", "element_index", "direction"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_value",
        "description": "Set the value of an accessibility element from the latest get_app_state response.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "value": {"type": "string", "description": "Value to assign."},
            },
            "required": ["app", "element_index", "value"],
            "additionalProperties": False,
        },
    },
    {
        "name": "perform_secondary_action",
        "description": "Invoke an accessibility action exposed by an element, such as AXPress, AXShowMenu, AXIncrement, or AXDecrement.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "action": {"type": "string", "description": "Accessibility action name."},
            },
            "required": ["app", "element_index", "action"],
            "additionalProperties": False,
        },
    },
]


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    if "id" not in message:
        return None

    request_id = message["id"]
    method = message.get("method")
    params = message.get("params") or {}

    try:
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name not in TOOL_HANDLERS:
                raise RuntimeError(f"Unknown tool: {name}")
            result = TOOL_HANDLERS[name](arguments)
        elif method == "resources/list":
            result = {"resources": []}
        elif method == "prompts/list":
            result = {"prompts": []}
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": error_result(str(exc)),
        }


def serve_stdio() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = handle_request(message)
            if response is not None:
                sys.stdout.write(json_dumps(response) + "\n")
                sys.stdout.flush()
        except Exception:
            sys.stderr.write(traceback.format_exc() + "\n")
            sys.stderr.flush()


def self_test() -> int:
    names = [tool["name"] for tool in TOOLS]
    missing_handlers = [name for name in names if name not in TOOL_HANDLERS]
    schemas = [tool.get("inputSchema", {}).get("type") == "object" for tool in TOOLS]
    result = {
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "toolCount": len(TOOLS),
        "tools": names,
        "missingHandlers": missing_handlers,
        "schemasValid": all(schemas),
    }
    print(pretty_json(result))
    return 1 if missing_handlers or not all(schemas) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Self-hosted Computer Use MCP server")
    parser.add_argument("--self-test", action="store_true", help="Validate server metadata without touching the GUI")
    parser.add_argument("--list-tools", action="store_true", help="Print tool schemas and exit")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.list_tools:
        print(pretty_json({"tools": TOOLS}))
        return 0

    serve_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
