# OpenComputerUse

Self-hosted Computer Use MCP server — an open alternative to proprietary computer use plugins.

## Overview

This repository implements an MCP (Model Context Protocol) server for controlling desktop applications on macOS and Linux. It does not launch, wrap, proxy, import, or depend on any bundled native Computer Use plugin.

The server supports two backends:

- **macOS** — PyObjC Quartz Accessibility, AppKit, AppleScript, pyautogui
- **Linux X11** — AT-SPI2, xdotool, wmctrl, Xvfb, pyautogui

Plus a deterministic **fake** backend for testing.

No remote API is called by the MCP server.

## Plugin Files

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `.mcp.json`: local MCP server launch configuration
- `scripts/run_open_computer_use_mcp.sh`: launcher that prefers the repo `.venv`
- `scripts/open_computer_use_mcp_server.py`: MCP server entrypoint

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

macOS users: grant Accessibility and Screen Recording permissions to the process that starts the MCP server.

Linux users: install AT-SPI2, xdotool, wmctrl, and tesseract-ocr via your package manager.

## MCP Tools

| Tool | Description |
| --- | --- |
| `get_app_state` | Activate or launch an app, capture a screenshot, and return an indexed accessibility tree. |
| `list_apps` | List running, recent, or installed apps. |
| `click` | Click by accessibility `element_index` or screenshot coordinates. |
| `drag` | Drag between screenshot coordinates. |
| `press_key` | Press a key or key combination such as `ctrl+c`, `Return`, or `Tab`. |
| `type_text` | Type literal text into the active app. |
| `scroll` | Scroll an indexed element. |
| `set_value` | Set an accessibility value or fall back to click/select/type. |
| `perform_secondary_action` | Invoke an accessibility action such as `AXPress` or `AXShowMenu`. |
| `analyze_screenshot` | Capture and analyze the screen with OCR and element detection. |
| `screenshot_diff` | Compare two screenshots and report changed regions. |
| `visual_click` | Click an element described in natural language. |
| `visual_locate` | Find elements matching a natural language description. |

## Validate

```bash
./.venv/bin/python scripts/open_computer_use_mcp_server.py --self-test
./.venv/bin/python scripts/open_computer_use_mcp_server.py --list-tools
```

## Optional Legacy CLI

`open_computer_use.py` is an older autonomous task loop that delegates screen interpretation to a vision model. It is not used by the MCP server. Install `requirements-agent.txt` only if you want that optional legacy path.
