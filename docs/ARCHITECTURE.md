# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────┐
│                   MCP Client                        │
│          (Claude Desktop, Cursor, Codex)            │
└──────────────────────┬──────────────────────────────┘
                       │ stdio JSON-RPC
                       ▼
┌─────────────────────────────────────────────────────┐
│                  server.py                          │
│                                                     │
│  ┌─────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │ handle_      │  │ TOOL_      │  │ get_backend()│  │
│  │ request()    │─▶│ HANDLERS   │  │             │  │
│  └─────────────┘  └─────┬──────┘  └──────┬──────┘  │
│                         │                 │         │
│  ┌──────────────────────▼─────────────────▼──────┐  │
│  │              safety.py                        │  │
│  │   budget check → rate limit → emergency stop  │  │
│  └──────────────────────┬────────────────────────┘  │
│                         │                           │
│  ┌──────────────────────▼────────────────────────┐  │
│  │              audit.py                         │  │
│  │         JSONL action logging                  │  │
│  └───────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │   ComputerBackend ABC   │
          └───┬─────────┬──────────┘
              │         │
    ┌─────────▼──┐  ┌───▼───────────┐  ┌──────────┐
    │ macos.py   │  │ linux_x11.py  │  │ fake.py  │
    │ (AppKit,   │  │ (Xvfb,        │  │ (determ- │
    │  Quartz,   │  │  xdotool,     │  │  inistic │
    │  pyautogui)│  │  AT-SPI)      │  │  test)   │
    └────────────┘  └───────────────┘  └──────────┘
```

## Module Descriptions

### `open_computer_use/server.py`
MCP JSON-RPC transport layer. Receives newline-delimited JSON over stdio, dispatches to tool handlers, and returns responses. Handles `initialize`, `tools/list`, `tools/call`, `ping`, `resources/list`, and `prompts/list` methods.

### `open_computer_use/tools.py`
Tool schema registry. Defines all 13 tool names, descriptions, and `inputSchema` objects. Each tool has a corresponding handler function in `server.py`.

### `open_computer_use/backends/base.py`
Abstract base class `ComputerBackend` defining the interface all backends must implement: `list_apps`, `activate_or_launch_app`, `capture_screenshot`, `get_accessibility_tree`, `click`, `drag`, `press_key`, `type_text`, `scroll`, `set_value`, `perform_action`, `screen_size`, `is_accessibility_trusted`, `clear_cache`, `flat_elements`, `element_from_index`.

### `open_computer_use/backends/macos.py`
macOS backend using AppKit (`NSWorkspace`), Quartz CoreGraphics, and `pyautogui`. Handles app discovery, window management, screenshots, accessibility trees, and input.

### `open_computer_use/backends/linux_x11.py`
Linux X11 backend for Docker container testing. Uses `xdotool` for input, `scrot` for screenshots, `wmctrl` for window management, and AT-SPI for accessibility trees.

### `open_computer_use/backends/fake.py`
Deterministic test backend. All operations return fixed responses without touching a display. Used for unit and contract tests.

### `open_computer_use/backends/input_utils.py`
Clipboard preservation utilities (`preserve_clipboard`, `restore_clipboard`). Used by `type_text` and `set_value` handlers to restore the clipboard after paste-based input.

### `open_computer_use/types.py`
Shared types and element cache. `ELEMENT_CACHE` maps element index strings to `CachedElement` dataclass instances containing role, title, frame, and app metadata. `LAST_SCREENSHOT` stores the most recent screenshot bytes for diff operations.

### `open_computer_use/matcher.py`
Element matching engine for `visual_click` and `visual_locate`. Parses natural language descriptions into tokens and role hints, scores accessibility elements and OCR results, and returns ranked matches.

### `open_computer_use/vision.py`
Screenshot analysis utilities. OCR extraction via Tesseract, element annotation with labeled bounding boxes, screenshot diffing with change detection, and element description summarization.

### `open_computer_use/safety.py`
Safety middleware: action budgets, token-bucket rate limiting, and emergency stop file check. Runs before every tool execution.

### `open_computer_use/audit.py`
Structured JSONL audit logger. Records timestamp, tool name, arguments (with screenshot data stripped), and result summary for every tool call.

## Data Flow

### Standard Tool Call

```
MCP Client
    │ tools/call {name: "click", arguments: {element_index: "5"}}
    ▼
server.py: handle_request()
    │
    ├── get_backend() → lazy-init backend
    ├── safety.check_action_allowed() → budget + rate limit + emergency stop
    │       └── BLOCKED? → return error, log to audit
    ├── TOOL_HANDLERS["click"](args, backend)
    │       └── backend.click(element_index="5", ...)
    │               └── lookup in ELEMENT_CACHE → frame center → xdotool/pyautogui click
    ├── safety.record_action() → consume budget + rate token
    ├── audit.log_action("click", args, "ok")
    └── return result as MCP content
```

### Visual Click Pipeline

```
visual_click("the Submit button")
    │
    ├── capture screenshot
    ├── OCR extract → [{text: "Submit", x: 100, y: 200, ...}, ...]
    ├── flat_elements() → [{element_index: "5", role: "button", title: "Submit", ...}, ...]
    ├── matcher.find_elements(description, elements, ocr_results)
    │       ├── parse_description("the Submit button") → tokens=["submit","button"], role_hint="button"
    │       ├── score each element: role match (+30), title token match (+20), all tokens (+25)
    │       ├── score each OCR hit: text match (+20), confidence boost (+10*conf)
    │       └── return sorted, deduplicated matches
    ├── match_center(best_match) → (cx, cy)
    └── backend.click(x=cx, y=cy)
```

### Safety Middleware Flow

```
tools/call arrives
    │
    ▼
check_emergency_stop() ─── file exists? ── YES ──▶ BLOCKED
    │ NO
    ▼
budget.check() ─── count >= max? ── YES ──▶ BLOCKED
    │ NO
    ▼
rate_limiter.check() ─── window full? ── YES ──▶ BLOCKED
    │ NO
    ▼
execute tool
    │
    ▼
record_action() → budget.consume() + rate_limiter.consume()
    │
    ▼
audit.log_action()
```

## Element Caching

When `get_app_state` is called, the backend builds an accessibility tree. Each node is assigned a numeric index (e.g. `"0"`, `"1"`, `"42"`). These indexes are stored in `ELEMENT_CACHE` in `types.py` along with the element's role, title, frame coordinates, and app name.

Subsequent calls to `click`, `scroll`, `set_value`, and `perform_secondary_action` look up the element by index to retrieve its frame and compute the center point for the action.

The cache is cleared when `get_app_state` is called again for the same or a different app.

## Backend Selection

Controlled by the `OPEN_CU_BACKEND` environment variable:

- `fake` — deterministic test backend, no display needed
- `macos` — macOS native backend (AppKit, Quartz, pyautogui)
- `linux-x11` — Linux X11 backend (xdotool, scrot, AT-SPI)

If unset, auto-detected: `macos` on Darwin, `linux-x11` on Linux when `$DISPLAY` is set, otherwise `fake`.
