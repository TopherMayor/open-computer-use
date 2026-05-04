# Linux/X11 Backend Implementation Plan

Reference docs: `docs/docker-desktop-test-plan.md` and `docs/maturity-roadmap.md`.

## Phase 1: Architecture Split

Refactor the monolithic `scripts/open_computer_use_mcp_server.py` into a backend-agnostic package.

### File Structure
```
open_computer_use/
  __init__.py
  server.py              # MCP JSON-RPC transport + tool dispatch
  tools.py               # Tool schema registry (the TOOLS list)
  types.py               # CachedElement, ELEMENT_CACHE, LAST_APP, helper functions
  backends/
    __init__.py
    base.py              # ComputerBackend ABC
    macos.py             # Current AppKit/Quartz/pyautogui implementation
    fake.py              # Deterministic test backend
scripts/
  open_computer_use_mcp_server.py  # Thin entrypoint importing from open_computer_use
```

### ComputerBackend Interface (base.py)
```python
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
```

### Backend Selection
- Env var `OPEN_CU_BACKEND`: `macos` (default on darwin), `linux-x11` (default on linux), `fake`
- Auto-detect if env var not set: `platform.system() == "Darwin"` → macos, else → linux-x11

### Verification
```bash
python3 scripts/open_computer_use_mcp_server.py --self-test
python3 scripts/open_computer_use_mcp_server.py --list-tools
```

Both must pass with identical output to the original.

### Fake Backend
Implement `fake.py` that returns deterministic canned responses for all methods. Used for contract tests.

## Phase 2: Linux X11 Backend

Create `open_computer_use/backends/linux_x11.py`.

### Dependencies
- `pyautogui` — mouse/keyboard (works on Linux with X11)
- `mss` — screenshots (works on Linux)
- `wmctrl` — window management and app listing
- `xdotool` — app activation, window focus
- `xclip` or `xsel` — clipboard (replaces pbcopy/pbpaste)
- `/proc/<pid>/cmdline` and `ps` — process discovery
- AT-SPI2 (`python3-gi`, `gi.repository.Atspi`) — accessibility tree where available

### Key Mappings
- `super` modifier → `ctrl` on Linux
- `command` modifier → `ctrl` on Linux
- `option` modifier → `alt` on Linux

### App Discovery (list_apps)
1. `wmctrl -l -p` for window list with PIDs
2. `/proc/<pid>/cmdline` for process names
3. `ps -eo pid,comm,args` as fallback
4. `xdotool search --name` for window titles

### App Activation (activate_or_launch_app)
1. `wmctrl -a <window_title>` to activate by title
2. `xdotool windowactivate <wid>` as fallback
3. Launch via subprocess if not running
4. Verify activation with `xdotool getactivewindow`

### Screenshots
- `mss` primary (works on Linux with X11)
- `pyautogui.screenshot()` fallback
- Save to `/tmp` for debugging

### Accessibility Tree
- Try AT-SPI2 first: `gi.repository.Atspi`
- Fallback to window geometry from `wmctrl -l -G` + `xdotool`
- Build element tree with window frames as root elements
- Use coordinate-based element selection when AT-SPI2 unavailable

### Clipboard
- `xclip -selection clipboard` replaces pbcopy/pbpaste
- `xsel --clipboard` as fallback

### Requirements
Create `requirements-linux.txt`:
```
mss>=9.0.0
pyautogui>=0.9.54
pynput>=1.7.0
pillow>=10.0.0
numpy>=1.24.0
pyperclip>=1.8.0
```

System packages: `sudo apt-get install -y xvfb xdotool wmctrl xclip x11-utils scrot python3-gi gir1.2-atspi-2.0 gir1.2-gtk-3.0 dbus-x11 at-spi2-core openbox`

## Phase 3: Contract Tests

### files
```
tests/
  __init__.py
  mcp_client.py          # Stdio MCP client helper
  test_mcp_contract.py   # Contract tests using fake backend
requirements-test.txt    # pytest
```

### mcp_client.py
```python
import subprocess, json
class MCPClient:
    def __init__(self, backend="fake"):
        env = {"OPEN_CU_BACKEND": backend}
        self.proc = subprocess.Popen(
            ["python3", "scripts/open_computer_use_mcp_server.py"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env={**os.environ, **env}
        )
    def send(self, msg): ...
    def initialize(self): ...
    def tools_list(self): ...
    def tool_call(self, name, args): ...
    def close(self): ...
```

### Test Cases
1. Server starts over stdio
2. `initialize` returns server name/version and tool capabilities
3. `tools/list` returns all 9 expected tools
4. Every tool has object `inputSchema`
5. Invalid tool names return MCP tool errors (not crashes)
6. Missing required arguments return structured errors
7. `resources/list` returns empty list
8. `prompts/list` returns empty list

## Phase 4: Docker Desktop Environment

### File Structure
```
docker/
  desktop-test/
    Dockerfile
    docker-compose.yml
    entrypoint.sh
tests/
  fixtures/
    desktop_app.py    # GTK fixture app
```

### Dockerfile
- Base: ubuntu:24.04
- Install: python3.12, xvfb, openbox, x11vnc, novnc, xdotool, wmctrl, scrot, xclip, xsel, dbus-x11, at-spi2-core, python3-gi, gir1.2-atspi-2.0, gir1.2-gtk-3.0
- Copy repo, install requirements
- EXPOSE 6080 (noVNC)
- ENTRYPOINT entrypoint.sh

### docker-compose.yml
```yaml
services:
  contract-tests:
    build: .
    command: python3 -m pytest tests/test_mcp_contract.py -v
    environment:
      - OPEN_CU_BACKEND=fake

  desktop-tests:
    build: .
    command: >
      bash -c "
        Xvfb :99 -screen 0 1280x800x24 &
        openbox &
        dbus-launch --exit-with-session python3 tests/fixtures/desktop_app.py &
        sleep 2
        DISPLAY=:99 OPEN_CU_BACKEND=linux-x11 python3 -m pytest tests/test_desktop_smoke.py -v
      "
    environment:
      - DISPLAY=:99
      - OPEN_CU_BACKEND=linux-x11

  novnc-debug:
    build: .
    ports:
      - "6080:6080"
    command: >
      bash -c "
        Xvfb :99 -screen 0 1280x800x24 &
        openbox &
        x11vnc -display :99 -forever -nopw &
        novnc --listen 6080 &
        dbus-launch --exit-with-session python3 tests/fixtures/desktop_app.py &
        sleep infinity
      "
    environment:
      - DISPLAY=:99
```

### Fixture App (desktop_app.py)
GTK3 app with:
- Button labeled "Increment"
- Label showing counter (starts at "0")
- Text field labeled "Name"
- Scrollable list with 50 rows
- Menu bar with "File" menu containing "Quit"
- Drag target area

## Phase 5: Smoke Tests

### test_desktop_smoke.py
Tests from docs/docker-desktop-test-plan.md:
- list_apps includes fixture app
- get_app_state returns screenshot + accessibility tree + element indexes
- click on Increment changes counter
- type_text enters text into Name field
- press_key handles Tab, Return, ctrl+a
- scroll changes visible list rows
- set_value sets text field
- drag moves object or changes state
- perform_secondary_action invokes accessibility action

### test_failure_modes.py
- Backend unavailable
- Display unavailable
- App cannot launch
- Unknown element index
- Stale element index

## Execution Notes

- After each phase, commit with: `git commit -m "phase N: <description>"`
- Do NOT push to remote
- Install system deps as needed: `sudo apt-get install -y ...`
- Use project venv: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- The macOS backend must remain functional — don't break it
- Test each phase before moving to the next
