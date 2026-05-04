# Docker Desktop Test Plan

## Purpose

Build a repeatable containerized desktop lab for validating the local `open-computer-use` MCP server without touching the user's real desktop.

The current plugin is macOS-oriented. Docker containers on macOS run Linux and cannot access macOS Accessibility, Screen Recording, AppKit, Quartz, or real Mac app windows. This means container testing must use a Linux desktop backend and fixture apps. The goal is not to prove macOS permission behavior inside Docker; the goal is to make protocol behavior, screenshot capture, input execution, app state modeling, and regression tests deterministic.

## Test Strategy

Use three layers:

1. MCP contract tests: run anywhere, no GUI required.
2. Container desktop smoke tests: Linux GUI with Xvfb, window manager, and fixture apps.
3. Backend parity tests: the same scenario suite runs against both the Linux container backend and the real macOS backend where possible.

## Target Docker Environment

Base image:

- Ubuntu 24.04 or Debian stable
- Python 3.12+
- `xvfb` for virtual display
- `openbox` or `fluxbox` as window manager
- `x11vnc` and noVNC for visual debugging
- `xdotool`, `wmctrl`, `scrot`, `xclip`, `xsel`
- `dbus-x11`, `at-spi2-core`, and Python AT-SPI bindings for accessibility-style inspection
- A small deterministic fixture app, preferably built in Python with GTK or Qt

Suggested display:

- `DISPLAY=:99`
- resolution `1280x800x24`
- one virtual monitor for baseline tests
- optional second profile at `1920x1080x24`

## Required Test Harness Changes

Before full desktop tests can pass in Docker, split the current server into backend-neutral tool handling plus platform backends:

- `ComputerBackend` interface:
  - `list_apps()`
  - `activate_or_launch_app(app)`
  - `capture_screenshot()`
  - `get_accessibility_tree(app)`
  - `click(...)`
  - `drag(...)`
  - `press_key(...)`
  - `type_text(...)`
  - `scroll(...)`
  - `set_value(...)`
  - `perform_action(...)`
- `MacOSBackend`: current AppKit/Quartz/pyautogui implementation.
- `LinuxX11Backend`: container implementation using X11 tools and AT-SPI where available.
- Backend selection by environment:
  - `OPEN_CU_BACKEND=macos`
  - `OPEN_CU_BACKEND=linux-x11`
  - `OPEN_CU_BACKEND=fake`

The immediate contract tests can run before this split. The GUI tests should wait until the backend split exists.

## Fixture App

Create a deterministic app for end-to-end testing. It should expose:

- A button labeled `Increment`
- A label/counter that changes from `0` to `1`
- A text field labeled `Name`
- A scrollable list with at least 50 rows
- A menu or secondary action target
- A drag target area

GTK is preferred because it works well with Linux accessibility tooling. Tkinter is acceptable for screenshot/input smoke tests, but may be weaker for accessibility tree coverage.

## Test Cases

### Contract Tests

- Server starts over stdio.
- `initialize` returns server name/version and tool capabilities.
- `tools/list` returns all expected tools.
- Every tool has an object `inputSchema`.
- Invalid tool names return MCP tool errors instead of crashing.
- Missing required arguments return structured errors.

### Desktop Smoke Tests

- Start Xvfb and window manager.
- Launch fixture app.
- `list_apps` includes the fixture app or process.
- `get_app_state` returns:
  - screenshot image content
  - nonzero screenshot width and height
  - nonempty accessibility or fallback element tree
  - stable element indexes
- `click` on `Increment` changes counter text.
- `type_text` enters text into the `Name` field.
- `press_key` handles `Tab`, `Return`, and a shortcut such as `ctrl+a`.
- `scroll` changes visible list rows.
- `set_value` sets the text field through accessibility or fallback input.
- `drag` moves a draggable object or produces a detectable state change.
- `perform_secondary_action` invokes a supported accessibility action when available.

### Visual Regression Checks

- Screenshot is not blank.
- Fixture app window is visible and framed inside the screenshot.
- Coordinate clicks land within expected target bounds.
- Retina/scaling assumptions are not baked into the Linux path.

### Failure Mode Tests

- Backend unavailable.
- Display unavailable.
- App cannot launch.
- Screenshot permission/backend failure.
- Unknown element index.
- Stale element index after app state changes.
- App exits between `get_app_state` and action call.

## Proposed Files

- `docker/desktop-test/Dockerfile`
- `docker/desktop-test/entrypoint.sh`
- `docker/desktop-test/docker-compose.yml`
- `tests/fixtures/desktop_app.py`
- `tests/mcp_client.py`
- `tests/test_mcp_contract.py`
- `tests/test_desktop_smoke.py`
- `tests/test_failure_modes.py`
- `requirements-test.txt`

## Execution Plan

### Phase 1: Contract-Only Container

Deliver a Docker image that installs repo dependencies and runs MCP contract tests without a GUI.

Acceptance:

- `docker compose run --rm contract-tests` passes.
- Contract tests run on local macOS and in Docker.
- CI can run these tests without privileged desktop access.

### Phase 2: Linux Desktop Harness

Add Xvfb, window manager, noVNC, and fixture app.

Acceptance:

- Container starts a visible desktop.
- noVNC can be opened for debugging.
- The fixture app launches and remains foregrounded.
- Screenshots from the MCP server show the fixture app.

### Phase 3: Linux Backend

Refactor the MCP server around a backend interface and implement `LinuxX11Backend`.

Acceptance:

- The same MCP tool names work in Docker.
- `get_app_state`, `click`, `type_text`, `press_key`, and `drag` pass fixture tests.
- Accessibility support is used when available and screenshot-coordinate fallback is explicit.

### Phase 4: End-to-End Scenario Suite

Implement deterministic scenarios for all tools.

Acceptance:

- Every MCP tool has at least one positive test and one failure-mode test.
- Screenshots are archived on failure.
- Tool call logs are captured as JSONL.

### Phase 5: Parity Gate

Run the same scenario definitions against:

- Docker Linux backend
- macOS backend on a developer machine

Acceptance:

- Scenario results are comparable by tool outcome and final fixture state.
- Platform-specific differences are documented in expected-result files.

## CI Shape

Default CI:

- Contract tests
- Unit tests for backend-neutral code
- Fake backend tests

Optional/manual CI:

- Docker desktop smoke tests
- noVNC artifact capture
- screenshot archive on failure

Mac-only manual gate:

- Real macOS app tests
- Accessibility permission checks
- Screen Recording permission checks
- multi-monitor and scaling tests

## Risks

- Docker cannot validate macOS-specific permission prompts.
- Linux AT-SPI accessibility differs from macOS AX APIs.
- `pyautogui` behavior varies between Xvfb, VNC, and real desktops.
- Clipboard behavior can be flaky without a full desktop session.
- Browser apps inside containers add heavy dependencies; start with fixture apps first.

## Definition Of Done

The Docker test environment is considered useful when a contributor can run one command that:

1. Builds a containerized desktop.
2. Starts a fixture GUI app.
3. Starts the MCP server.
4. Executes all tool scenarios.
5. Saves screenshots and JSONL traces for failures.
6. Exits nonzero on regression.

## Video Recording

The Docker image includes `ffmpeg` for recording the Xvfb display during test execution. This produces MP4 video artifacts that serve as visual verification of test runs.

### How It Works

1. `ffmpeg` records the `:99` X11 display using `x11grab` at 10 fps
2. The video is encoded as H.264 (`libx264`, preset `fast`, CRF 28)
3. Output is saved to `/home/testuser/repo/test-recordings/desktop-test.mp4`
4. This directory is mounted as a Docker volume to `./test-recordings/` on the host

### Usage

```bash
# Run tests with video recording
./docker/desktop-test/run-and-record.sh
```

The script builds the `desktop-tests-recorded` Docker service, runs the desktop smoke tests with ffmpeg recording, and reports artifact locations.

### Docker Compose Service

The `desktop-tests-recorded` service in `docker/desktop-test/docker-compose.yml` extends the standard `desktop-tests` service with:

- ffmpeg background process recording the display
- Volume mount for the `test-recordings/` directory
- Test process followed by ffmpeg cleanup (`kill` + `wait`)

### Artifacts

| Artifact | Location | Description |
|----------|----------|-------------|
| `desktop-test.mp4` | `test-recordings/` | Full video of the test run |
| `*_failure.png` | `test-recordings/` | Screenshots captured on test failure (via `conftest.py`) |

Video files are excluded from git via `.gitignore` (`test-recordings/*.mp4`).

### Infrastructure Tests

`tests/test_recording.py` validates the recording infrastructure without Docker:

- Docker compose config is valid and contains ffmpeg command
- `run-and-record.sh` exists and is executable
- `test-recordings/` directory can be created
