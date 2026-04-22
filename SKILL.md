# GSD Computer Use

Independent self-hosted macOS Computer Use plugin for Codex.

## Overview

This repository implements a local Codex plugin and stdio MCP server for controlling macOS applications. It does not launch, wrap, proxy, import, or depend on the bundled native Computer Use plugin.

The plugin server lives in `scripts/computer_use_mcp_server.py` and uses local macOS/desktop automation APIs:

- PyObjC Quartz Accessibility for indexed UI trees and accessibility actions
- PyObjC Cocoa, CoreGraphics, AppleScript, process metadata, and app bundle scanning for app discovery
- `pyautogui` for mouse, keyboard, screenshots, scrolling, and drag operations
- `mss` as a screenshot fallback
- local clipboard commands as a text-entry fallback

No remote API is called by the plugin MCP server.

## Plugin Files

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `.mcp.json`: local MCP server launch configuration
- `scripts/run_computer_use_mcp.sh`: launcher that prefers the repo `.venv`
- `scripts/computer_use_mcp_server.py`: independent local MCP implementation
- `skills/computer-use/SKILL.md`: usage guidance for agents

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Grant macOS permissions to the process that starts the MCP server:

- Accessibility
- Screen Recording

## MCP Tools

| Tool | Description |
| --- | --- |
| `get_app_state` | Activate or launch an app, capture a screenshot, and return an indexed accessibility tree. |
| `list_apps` | List running, recent, or installed apps using local macOS discovery. |
| `click` | Click by accessibility `element_index` or screenshot coordinates. |
| `drag` | Drag between screenshot coordinates. |
| `press_key` | Press a key or key combination such as `super+c`, `Return`, or `Tab`. |
| `type_text` | Type literal text into the active app. |
| `scroll` | Scroll an indexed element. |
| `set_value` | Set an accessibility value or fall back to click/select/type. |
| `perform_secondary_action` | Invoke an accessibility action such as `AXPress` or `AXShowMenu`. |

## Validate

```bash
./.venv/bin/python scripts/computer_use_mcp_server.py --self-test
./.venv/bin/python scripts/computer_use_mcp_server.py --list-tools
```

## Optional Legacy CLI

`gsd_computer_use.py` is the older autonomous task loop that delegates screen interpretation to a Z.AI/OpenAI-compatible vision model. It is not used by the local plugin MCP server.

Install `requirements-agent.txt` only if you want that optional legacy CLI path.
