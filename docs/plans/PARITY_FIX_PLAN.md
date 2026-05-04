# Linux X11 Backend Parity Fix Plan

## Goal
Bring the Linux X11 backend (`open_computer_use/backends/linux_x11.py`) to functional parity with the macOS backend (`open_computer_use/backends/macos.py`). All 14 abstract methods from `ComputerBackend` are structurally implemented but many have functional gaps.

## Context
- The macOS backend is 968 lines. The Linux backend is 532 lines.
- The Linux backend has the same abstract interface but lacks: element frame data, rich metadata, action execution, and proper set_value.
- ATSPI (Accessibility Toolkit Service Provider Interface) via `gi.repository.Atspi` is the Linux equivalent of macOS AXUIElement.
- Reference the macOS backend for behavior patterns but adapt for Linux APIs.

## Phase 1: Rich Accessibility Tree Metadata

The Linux `_get_accessibility_tree()` function (line 308) currently only collects `role` and `title` per element. It needs to collect the same rich metadata as macOS `_build_accessibility_tree()` (line 668).

**Changes to `_get_accessibility_tree()` in `linux_x11.py`:**

For each ATSPI element, collect these fields (mapping macOS AX attributes to ATSPI equivalents):

| macOS AX | Linux ATSPI | Method |
|----------|-------------|--------|
| AXRole | Atspi.RoleType | `el.get_role_name()` (already done) |
| AXTitle/AXName | Atspi name | `el.get_name()` (already done) |
| AXDescription | Atspi description | `el.get_description()` |
| AXValue | Atspi value | `el.get_value()` — returns `AccessibleValue` or use `Atspi.Value.get_value(el)` |
| AXEnabled | StateSet | `Atspi.StateSet.contains(Atspi.StateType.ENABLED)` |
| AXFocused | StateSet | `Atspi.StateSet.contains(Atspi.StateType.FOCUSED)` |
| AXPosition+AXSize (frame) | Atspi component | `Atspi.Component.get_position(el, Atspi.CoordType.SCREEN)` and `Atspi.Component.get_size(el)` |
| Actions | Atspi Action | `Atspi.Action.get_n_actions(el)` + `Atspi.Action.get_action_name(el, i)` |

**Element frame data (CRITICAL):**
The `CachedElement.frame` must be populated with `{x, y, width, height, center_x, center_y}` for every element that exposes position/size. This is required for `click`, `scroll`, and `set_value` to work by element_index.

Use the ATSPI Component interface:
```python
try:
    ext = el.get_extents(Atspi.CoordType.SCREEN)
    # ext is an AtspiRect with x, y, width, height
    frame = {
        "x": ext.x, "y": ext.y,
        "width": ext.width, "height": ext.height,
        "center_x": ext.x + ext.width / 2,
        "center_y": ext.y + ext.height / 2,
    }
except Exception:
    frame = None
```

**Tree node output format** — match macOS output:
```python
node = {"element_index": index_str}
for key, value in {"role": role, "title": name, "description": desc, "value": val, "enabled": enabled, "focused": focused, "frame": frame}.items():
    if value not in (None, "", []):
        node[key] = value
if actions:
    node["actions"] = actions
```

## Phase 2: Fix `click` by element_index

Currently in `LinuxX11Backend.click()` (line 438), when `element_index` is provided, it tries `frame_center(cached.frame)` but frame is always None. After Phase 1 fixes the tree to populate frames, this should work. But also add the macOS pattern:

**macOS pattern** (line 868-872): If button=="left" and click_count==1 and the element supports AXPress, use AXPress instead of mouse click.

**Linux equivalent:** Check if the ATSPI element has an "activate" or "press" action, and if so, use `Atspi.Action.do_action(el, action_index)` instead of mouse click.

```python
if element_index is not None:
    cached = element_from_index(str(element_index))
    # Try ATSPI action first (like macOS AXPress)
    if button == "left" and click_count == 1:
        try:
            from gi.repository import Atspi
            action_iface = Atspi.Action
            if action_iface and cached.element is not None:
                n_actions = action_iface.get_n_actions(cached.element)
                for i in range(n_actions):
                    name = action_iface.get_action_name(cached.element, i)
                    if name and name.lower() in ("press", "activate", "click"):
                        action_iface.do_action(cached.element, i)
                        return {"success": True, "method": "ATSPI-press", "element_index": str(element_index)}
        except Exception:
            pass
    # Fallback to mouse click at frame center
    cx, cy = frame_center(cached.frame)
else:
    if x is None or y is None:
        raise RuntimeError("click requires either element_index or both x and y")
    cx, cy = x, y
```

## Phase 3: Fix `perform_action`

Currently (line 511) returns a stub response. Implement proper ATSPI action execution:

```python
def perform_action(self, element_index: str, action: str, **kwargs) -> dict[str, Any]:
    cached = element_from_index(element_index)
    if cached.element is None:
        raise RuntimeError(f"No ATSPI element for index {element_index}")
    
    try:
        from gi.repository import Atspi
    except Exception:
        raise RuntimeError("ATSPI not available for action execution")
    
    action_iface = Atspi.Action
    n_actions = action_iface.get_n_actions(cached.element)
    available = []
    for i in range(n_actions):
        name = action_iface.get_action_name(cached.element, i)
        available.append(name)
    
    # Normalize action name (similar to macOS _normalize_ax_action)
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
        # Try prefix match
        for i, name in enumerate(available):
            if name.lower().startswith(normalized[:4]):
                matched_action = name
                matched_index = i
                break
    
    if matched_index is None:
        raise RuntimeError(f"Action {action!r} not found. Available: {available}")
    
    success = action_iface.do_action(cached.element, matched_index)
    return {"success": bool(success), "element_index": element_index, "action": matched_action}
```

## Phase 4: Fix `set_value`

Currently (line 506) just types the value without focusing/selecting. Implement like macOS:

```python
def set_value(self, element_index: str, value: str, **kwargs) -> dict[str, Any]:
    cached = element_from_index(element_index)
    
    # Try ATSPI Value interface first (like macOS AXValue)
    if cached.element is not None:
        try:
            from gi.repository import Atspi
            value_iface = Atspi.Value
            # Try setting via ATSPI Value interface
            # Atspi.Value.set_value may not exist in all versions
            if hasattr(value_iface, 'set_value'):
                current = value_iface.get_value(cached.element)
                # set_value expects the new value
                result = value_iface.set_value(cached.element, float(value) if value.replace('.','').isdigit() else value)
                if result:
                    return {"success": True, "method": "ATSPI-Value", "element_index": element_index}
        except Exception:
            pass
    
    # Fallback: click to focus, select all, type new value (same as macOS)
    x, y = frame_center(cached.frame)
    pyautogui = require_pyautogui()
    pyautogui.click(x=x, y=y)
    _press_key_sequence("ctrl+a")  # Linux uses ctrl+a, not super+a
    method = _type_literal_text(value)
    return {"success": True, "method": f"click-select-{method}", "element_index": element_index}
```

## Phase 5: Enhance `list_apps`

Add more metadata matching macOS output:

```python
def list_apps(self, **kwargs) -> list[dict[str, Any]]:
    include_recent = bool(kwargs.get("include_recent", True))
    include_installed = bool(kwargs.get("include_installed", False))
    
    apps = _list_apps()  # existing wmctrl/ps logic
    
    # Add installed apps from .desktop files (Linux equivalent of /Applications)
    if include_installed:
        installed = _installed_linux_apps()
        # Merge with running apps
        apps = _merge_app_lists(apps, installed)
    
    return apps
```

Add helper functions:

```python
def _installed_linux_apps(limit: int = 80) -> list[dict[str, Any]]:
    """Find installed applications from .desktop files."""
    import glob
    from pathlib import Path
    
    dirs = [
        "/usr/share/applications",
        os.path.expanduser("~/.local/share/applications"),
        "/var/lib/flatpak/exports/share/applications",
        os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
    ]
    
    apps = []
    seen = set()
    for dir_path in dirs:
        for desktop_file in sorted(Path(dir_path).glob("*.desktop"))[:limit]:
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
    merged = {}
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
```

## Phase 6: Update `_fallback_accessibility_tree` to populate frames

The fallback tree (when ATSPI is not available) uses wmctrl window list. Populate synthetic frame data using wmctrl window geometry:

```python
def _fallback_accessibility_tree(app_name: str, max_elements: int) -> dict[str, Any]:
    code, stdout, _ = _run(["wmctrl", "-l"])
    if code != 0:
        return {"element_index": "0", "role": "window", "title": app_name, "children": []}
    
    ELEMENT_CACHE.clear()
    # Root element
    ELEMENT_CACHE["0"] = CachedElement(
        element=None, frame={"x": 0, "y": 0, "width": 1920, "height": 1080, "center_x": 960, "center_y": 540},
        app=app_name, role="window", title=app_name,
    )
    
    children = []
    for i, line in enumerate(stdout.splitlines()):
        if i + 1 >= max_elements:
            break
        parts = line.split(None, 3)
        if len(parts) >= 4:
            wid = parts[0]
            title = parts[3]
            index_str = str(i + 1)
            
            # Get window geometry
            frame = None
            geo_code, geo_stdout, _ = _run(["xdotool", "getwindowgeometry", "--shell", wid])
            if geo_code == 0:
                geo = {}
                for geo_line in geo_stdout.splitlines():
                    if "=" in geo_line:
                        k, v = geo_line.split("=", 1)
                        geo[k.strip()] = v.strip()
                if all(k in geo for k in ("X", "Y", "WIDTH", "HEIGHT")):
                    x, y, w, h = int(geo["X"]), int(geo["Y"]), int(geo["WIDTH"]), int(geo["HEIGHT"])
                    frame = {"x": x, "y": y, "width": w, "height": h, "center_x": x + w/2, "center_y": y + h/2}
            
            ELEMENT_CACHE[index_str] = CachedElement(
                element=None, frame=frame, app=app_name, role="window", title=title,
            )
            children.append({"element_index": index_str, "role": "window", "title": title})
    
    return {"element_index": "0", "role": "window", "title": app_name, "children": children}
```

## Phase 7: Update tests

Update the existing tests to verify:
1. Accessibility tree includes frame data when using ATSPI
2. Fallback tree includes frame data from xdotool geometry
3. `perform_action` actually attempts ATSPI action (not just stub)
4. `set_value` tries ATSPI Value interface, falls back to click-select-type
5. `list_apps` returns merged data when `include_installed=True`

Add a new test file `tests/test_linux_parity.py` that compares the Linux backend output shape against the macOS backend output shape for each method.

## Acceptance Criteria

1. Every element in the accessibility tree has a `frame` dict when ATSPI or xdotool can provide geometry
2. `click(element_index="1")` works without RuntimeError (frame is populated)
3. `scroll(element_index="1", direction="down")` works without RuntimeError
4. `set_value("1", "hello")` focuses the element, selects all, and types
5. `perform_action("1", "press")` executes ATSPI action or raises with available actions listed
6. `list_apps(include_installed=True)` includes .desktop file entries merged with running apps
7. All existing tests still pass
8. `--self-test` still passes
9. Code is committed (DO NOT push to remote)

## Constraints
- DO NOT modify `base.py`, `macos.py`, `server.py`, `tools.py`, or `types.py`
- Only modify `linux_x11.py` and add new test files
- Keep the same function signatures
- Gracefully degrade when ATSPI is not available (fallback paths must work)
- DO NOT push to remote
