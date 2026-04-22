# GSD Computer Use

Self-hosted macOS Computer Use for Codex. This repository can be loaded as a local Codex plugin and exposes its own stdio MCP server for app inspection and OS-level control.

This is an independent local implementation. It does not launch, wrap, proxy, import, or depend on the bundled native Computer Use plugin.

## What It Implements

- Plugin manifest: `.codex-plugin/plugin.json`
- MCP server config: `.mcp.json`
- MCP stdio server: `scripts/computer_use_mcp_server.py`
- Plugin launcher: `scripts/run_computer_use_mcp.sh`
- Plugin skill instructions: `skills/computer-use/SKILL.md`

The local MCP server exposes these desktop-control tools:

- `get_app_state`
- `list_apps`
- `click`
- `drag`
- `press_key`
- `type_text`
- `scroll`
- `set_value`
- `perform_secondary_action`

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Grant macOS Accessibility and Screen Recording permissions to the process that launches the MCP server, such as Codex, Terminal, or your IDE.

## Local Architecture

- App discovery uses local macOS APIs and fallbacks: `NSWorkspace`, CoreGraphics window metadata, AppleScript, process paths, and `/Applications` scanning.
- Screenshots use `pyautogui` with an `mss` fallback.
- Accessibility trees use PyObjC's Quartz Accessibility APIs.
- Mouse and keyboard actions use `pyautogui`.
- Text entry uses keyboard input for short ASCII text and a local clipboard fallback for larger or Unicode text.
- No remote API is called by the plugin MCP server.

## Validate

```bash
./.venv/bin/python scripts/computer_use_mcp_server.py --self-test
./.venv/bin/python scripts/computer_use_mcp_server.py --list-tools
```

## Plans

- [Docker desktop test plan](docs/docker-desktop-test-plan.md)
- [Maturity roadmap](docs/maturity-roadmap.md)

## Notes

`get_app_state` activates or launches the requested app, captures a screenshot, and returns an indexed accessibility tree. The element indexes are cached in the running MCP process and can be used by `click`, `scroll`, `set_value`, and `perform_secondary_action`.
