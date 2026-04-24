# Maturity Roadmap

## Completed

- [x] Architecture split: backend interface, macOS/Linux/fake backends, tool registry
- [x] Container test lab: Docker Xvfb, fixture app, Linux X11 backend
- [x] Structured JSONL audit log (`computer_use/audit.py`)
- [x] Rate limiting and action budgets (`computer_use/safety.py`)
- [x] Emergency stop signal (`GSD_CU_EMERGENCY_STOP_FILE`)
- [x] Clipboard preservation (`backends/input_utils.py`)
- [x] Lint + typecheck (ruff, mypy via `pyproject.toml`)
- [x] Visual element targeting (`visual_click`, `visual_locate` tools)
- [x] Video recording of Docker tests (ffmpeg + `run-and-record.sh`)
- [x] OCR text extraction and screenshot annotation (`computer_use/vision.py`)
- [x] Screenshot diff comparison (`screenshot_diff` tool)

## Goal

Close the practical maturity gap between this independent local implementation and OpenAI's bundled native Computer Use plugin while keeping the project inspectable, self-hosted, and hackable.

This roadmap is based on observable differences:

- OpenAI ships a native macOS app with a proprietary MCP client.
- This project currently ships a Python stdio MCP server.
- OpenAI likely has stronger app lifecycle handling, permissions UX, coordinate mapping, safety controls, and production testing.
- This project has transparency and extensibility, but needs engineering hardening.

## Milestone 1: Architecture Split

Separate MCP protocol handling from platform-specific desktop control.

Deliverables:

- `computer_use/server.py`: MCP JSON-RPC transport and tool registration.
- `computer_use/backends/base.py`: backend interface.
- `computer_use/backends/macos.py`: current AppKit/Quartz/pyautogui implementation.
- `computer_use/backends/fake.py`: deterministic test backend.
- Move tool schemas into a single registry with tests.

Acceptance:

- Existing 9 tools still list and execute.
- Fake backend can run all tools without a GUI.
- Server has no platform imports at module import time except in selected backend.

## Milestone 2: Container Test Lab

Implement the Docker desktop test plan in `docs/docker-desktop-test-plan.md`.

Deliverables:

- Docker desktop image with Xvfb and noVNC.
- Fixture desktop app.
- Linux X11 backend.
- Contract, smoke, and failure-mode tests.

Acceptance:

- One command runs contract tests.
- One command runs GUI smoke tests.
- Screenshot and JSONL traces are saved on failures.

## Milestone 3: macOS Permission And Session UX

Make failures understandable and recoverable.

Deliverables:

- Explicit permission probes for Accessibility and Screen Recording.
- Clear diagnostic output for missing permissions.
- `doctor` command for local setup validation.
- Permission setup guide with screenshots or exact System Settings path.
- Graceful behavior when app discovery APIs are unavailable.

Acceptance:

- A new user can run `doctor` and know exactly what to fix.
- `get_app_state` returns structured permission diagnostics instead of silent empty trees.
- Screenshot failures distinguish dependency, display, and permission causes.

## Milestone 4: Robust App Lifecycle

Improve launch, activation, focus, and window selection.

Deliverables:

- App identity model: display name, bundle id, path, pid, window id.
- Deterministic app matching and disambiguation.
- Foreground activation verification.
- Focused window selection with fallback to largest visible window.
- App session cache with stale-process detection.
- Safe timeouts for launch and activation.

Acceptance:

- `list_apps` reliably reports running and installed apps.
- `get_app_state` selects the intended window in common multi-window apps.
- Stale pid/window references are detected and refreshed.

## Milestone 5: Accessibility Tree Quality

Make element trees more useful to agents.

Deliverables:

- Stable element paths in addition to ephemeral numeric indexes.
- Element filtering to keep trees compact but complete.
- Role-specific summaries for buttons, fields, lists, menus, tabs, tables, and web views.
- Parent/child path metadata.
- Element visibility and hit-testability scoring.
- Better value extraction for text fields, selected rows, checkboxes, and menus.

Acceptance:

- Agents can identify common controls without relying on raw coordinates.
- Tree output stays below configurable size limits.
- Element indexes survive minor UI refreshes when possible through path remapping.

## Milestone 6: Coordinate And Screenshot Accuracy

Harden visual grounding.

Deliverables:

- Unified coordinate model for screenshot pixels, logical points, and display coordinates.
- Retina scaling detection.
- Multi-monitor support.
- Per-window screenshots where possible.
- Cursor position metadata.
- Screenshot redaction hooks for sensitive regions.
- Nonblank and bounds checks.

Acceptance:

- Click coordinates align with screenshots on Retina and non-Retina displays.
- Multi-monitor screenshots include correct origin metadata.
- Out-of-bounds clicks are rejected with useful errors.

## Milestone 7: Input Reliability

Make actions predictable and reversible where possible.

Deliverables:

- Action preflight checks.
- Post-action verification hooks.
- Configurable click strategy: AX action first, coordinate fallback, or coordinate only.
- Robust text input strategy: AX set value, paste fallback, typing fallback.
- Clipboard preservation guarantees and failure cleanup.
- Key mapping tests for macOS and Linux.
- Drag calibration and scroll calibration.

Acceptance:

- Every action returns method used, target metadata, and verification status.
- Clipboard is restored after paste fallback in normal and error paths.
- Key combinations are covered by unit tests.

## Milestone 8: Safety And Control Plane

Add guardrails comparable to a production desktop-control tool.

Deliverables:

- App allowlist/denylist.
- Optional per-action confirmation policies.
- Sensitive-app mode for Passwords, banking, medical, mail, messages, and settings.
- Configurable screenshot redaction.
- Rate limits and max action budgets.
- Dry-run mode.
- Emergency stop file/signal.
- Audit log with tool call, target app, action, and result.

Acceptance:

- Risky apps can be blocked or require explicit approval.
- A running task can be stopped externally.
- Audit logs are enough to reconstruct what happened without storing full screenshots by default.

## Milestone 9: Observability And Replay

Make debugging boring.

Deliverables:

- Structured JSONL logging.
- Optional screenshot capture before and after actions.
- Tool latency metrics.
- Accessibility tree snapshots.
- Scenario replay runner.
- Failure bundles with logs, screenshots, environment, and MCP transcript.

Acceptance:

- Every failed test creates a self-contained artifact bundle.
- A developer can replay an MCP transcript against fake or live backend.

## Milestone 10: Packaging And Distribution

Make installation feel intentional.

Deliverables:

- Python package layout.
- Console entrypoint, for example `gsd-computer-use-mcp`.
- Versioned releases.
- Lockfile or reproducible install path.
- Plugin marketplace metadata for local install.
- Optional signed macOS app wrapper if needed for smoother permissions.

Acceptance:

- Clean install works from a fresh clone.
- Plugin launch does not depend on ad hoc shell assumptions.
- Version is reported consistently by package, MCP server, and manifest.

## Milestone 11: Browser And WebView Support

Close a major real-world desktop automation gap.

Deliverables:

- Better handling for browser windows and web views.
- URL/title extraction when available.
- DOM bridge only when explicitly enabled and safe.
- Browser profile isolation for tests.
- Container browser scenario tests.

Acceptance:

- Browser tasks can be inspected through accessibility and screenshot state.
- Optional DOM support is clearly separated from OS-level control.

## Milestone 12: Production Compatibility Matrix

Track where the plugin works and where it does not.

Deliverables:

- Supported OS matrix.
- Supported Python matrix.
- App compatibility notes.
- Known limitations.
- Regression suite by app category:
  - Finder/files
  - browser
  - text editor
  - settings
  - menu-heavy app
  - canvas-heavy app

Acceptance:

- New regressions can be tied to OS, Python, dependency, or app category.
- Users can tell whether their target workflow is expected to work.

## Priority Order

P0:

- Architecture split
- Fake backend
- Docker contract tests
- Permission diagnostics

P1:

- Docker GUI harness
- Linux X11 backend
- App lifecycle hardening
- Accessibility tree quality
- Coordinate accuracy

P2:

- Safety control plane
- Observability and replay
- Input reliability
- Packaging

P3:

- Browser/WebView support
- Compatibility matrix
- Optional signed macOS wrapper

## Near-Term Implementation Plan

1. Create package structure and backend interface.
2. Move current macOS code behind `MacOSBackend`.
3. Add fake backend and unit tests for all tools.
4. Add Docker contract test image.
5. Add fixture GUI app and Linux X11 backend.
6. Add permission `doctor`.
7. Add action logging and failure artifacts.

## Success Criteria

The project reaches practical maturity when:

- It can be tested deterministically in Docker.
- It gives clear diagnostics for macOS permission and app-state failures.
- It has repeatable scenario tests for every MCP tool.
- It handles common desktop edge cases without crashing.
- It exposes enough safety controls for real workflows.
- It remains fully local and inspectable.
