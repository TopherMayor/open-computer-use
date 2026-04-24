# GSD Computer Use

Self-hosted Computer Use MCP server for desktop automation. Provides 13 tools for inspecting and controlling desktop applications via the Model Context Protocol.

This is an independent local implementation. It does not launch, wrap, proxy, import, or depend on any bundled native Computer Use plugin.

## Tools

| Tool | Description |
|------|-------------|
| `get_app_state` | Activate an app, capture a screenshot, and return an indexed accessibility tree |
| `list_apps` | List running desktop apps and optionally recently used or installed apps |
| `click` | Click an element by accessibility index or screenshot coordinates |
| `drag` | Drag from one coordinate to another |
| `press_key` | Press a key or key combination (e.g. `ctrl+c`, `Return`, `Tab`) |
| `type_text` | Type literal text into the active app |
| `scroll` | Scroll an element by index in a given direction |
| `set_value` | Set the value of an accessibility element |
| `perform_secondary_action` | Invoke an accessibility action (AXPress, AXShowMenu, etc.) |
| `analyze_screenshot` | Capture and analyze the screen with OCR and element detection |
| `screenshot_diff` | Compare two screenshots and report changed regions |
| `visual_click` | Click an element described in natural language |
| `visual_locate` | Find elements matching a natural language description without clicking |

## Safety Features

- **Audit log**: Structured JSONL log of all tool calls, arguments, and results (`GSD_CU_AUDIT_LOG`)
- **Action budgets**: Limit total actions per session (`GSD_CU_MAX_ACTIONS`)
- **Rate limiting**: Token-bucket rate limiter for actions per minute (`GSD_CU_MAX_PER_MINUTE`)
- **Emergency stop**: Halt all actions by creating a file (`GSD_CU_EMERGENCY_STOP_FILE`)
- **Clipboard preservation**: Clipboard is saved and restored around paste-based text input

## Backends

| Backend | `GSD_CU_BACKEND` | Platform | Description |
|---------|-------------------|----------|-------------|
| macOS | `macos` | macOS | AppKit, Quartz, pyautogui |
| Linux X11 | `linux-x11` | Linux | Xvfb, xdotool, AT-SPI |
| Fake | `fake` | Any | Deterministic test backend |

Auto-detection: if `GSD_CU_BACKEND` is unset, uses `macos` on macOS and `linux-x11` on Linux when `$DISPLAY` is set, otherwise `fake`.

## Quick Start

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m computer_use.server --self-test
./.venv/bin/python -m computer_use.server --list-tools
```

macOS users: grant Accessibility and Screen Recording permissions to the process that launches the MCP server (Terminal, VS Code, etc.).

## MCP Client Configuration

### Claude Desktop / Cursor

Add to your MCP config:

```json
{
  "mcpServers": {
    "gsd-computer-use": {
      "command": "./scripts/run_computer_use_mcp.sh",
      "cwd": "/path/to/gsd-computer-use"
    }
  }
}
```

### Codex Plugin

The `.codex-plugin/` directory contains the Codex plugin manifest. The MCP server config is in `.mcp.json`.

## Docker Testing with Video Recording

Run desktop tests in a containerized Linux environment with video capture:

```bash
./docker/desktop-test/run-and-record.sh
```

This builds a Docker image with Xvfb, ffmpeg, and a fixture GTK desktop app, then runs smoke tests while recording the display. Video artifacts are saved to `test-recordings/`.

See [docs/TESTING.md](docs/TESTING.md) for details.

## Architecture

```
MCP Client (Claude, Cursor, Codex)
        │
        ▼
  server.py (JSON-RPC over stdio)
        │
        ▼
  TOOL_HANDLERS ──► safety.py (budget, rate limit, emergency stop)
        │
        ▼
  Backend (macOS / Linux X11 / Fake)
        │
        ├── capture_screenshot()
        ├── get_accessibility_tree()
        ├── click / drag / type_text / press_key / scroll
        └── audit.py (JSONL log)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full details.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - system design and data flow
- [Testing guide](docs/TESTING.md) - test tiers and how to run them
- [Docker test plan](docs/docker-desktop-test-plan.md) - containerized desktop test environment
- [Maturity roadmap](docs/maturity-roadmap.md) - project milestones and priorities

## License

MIT
