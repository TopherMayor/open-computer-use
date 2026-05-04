---
name: open-computer-use
description: Use the independent self-hosted OpenComputerUse plugin to inspect and control macOS apps through local screenshots, accessibility trees, mouse, keyboard, scrolling, value setting, and accessibility actions.
---

# OpenComputerUse

Use this skill when a task requires controlling macOS applications through the local self-hosted Computer Use MCP server.

This plugin is implemented in this repository. It does not call into any bundled native Computer Use plugin.

## Workflow

1. Call `list_apps` to discover running and recently used applications when the target app is unclear.
2. Call `get_app_state` before acting. It activates or launches the target app, captures a screenshot, and returns an indexed accessibility tree.
3. Prefer `element_index` actions when the target element appears in the tree. Use coordinates only when an element is not represented in Accessibility.
4. After each meaningful action, call `get_app_state` again to verify the new UI state.

## Tools

- `get_app_state`: activate an app, capture the screen, and return an indexed accessibility tree.
- `list_apps`: list running apps plus Spotlight-discovered recently used apps.
- `click`: click by `element_index` or screenshot coordinates.
- `drag`: drag between screenshot coordinates.
- `press_key`: press a single key or key combination such as `super+c`, `Return`, or `Tab`.
- `type_text`: type literal text into the active app.
- `scroll`: scroll an indexed element or the region under that element.
- `set_value`: set an accessibility value, falling back to click-select-type where possible.
- `perform_secondary_action`: invoke an accessibility action such as `AXPress` or `AXShowMenu`.

## Local Permissions

macOS may require Accessibility and Screen Recording permissions for the terminal or Codex host process that starts the MCP server.
