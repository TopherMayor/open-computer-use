from __future__ import annotations

from typing import Any


SERVER_NAME = "gsd-computer-use"
SERVER_VERSION = "1.0.0"
DEFAULT_MAX_DEPTH = 7
DEFAULT_MAX_ELEMENTS = 220


TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_app_state",
        "description": "Start an app use session if needed, then get the state of the app's key window and return a screenshot plus indexed accessibility tree.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "max_depth": {"type": "integer", "minimum": 1, "maximum": 12, "default": DEFAULT_MAX_DEPTH},
                "max_elements": {"type": "integer", "minimum": 10, "maximum": 1000, "default": DEFAULT_MAX_ELEMENTS},
                "include_screenshot": {"type": "boolean", "default": True},
            },
            "required": ["app"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_apps",
        "description": "List running desktop apps and optionally recently used apps.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_recent": {"type": "boolean", "default": True},
                "recent_days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 14},
                "include_installed": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "click",
        "description": "Click an element by index from get_app_state or by screenshot pixel coordinates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "x": {"type": "number", "description": "Screenshot x coordinate."},
                "y": {"type": "number", "description": "Screenshot y coordinate."},
                "click_count": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1},
                "mouse_button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
            },
            "required": ["app"],
            "additionalProperties": False,
        },
    },
    {
        "name": "drag",
        "description": "Drag from one screenshot coordinate to another.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "from_x": {"type": "number"},
                "from_y": {"type": "number"},
                "to_x": {"type": "number"},
                "to_y": {"type": "number"},
                "duration": {"type": "number", "minimum": 0, "default": 0.35},
            },
            "required": ["app", "from_x", "from_y", "to_x", "to_y"],
            "additionalProperties": False,
        },
    },
    {
        "name": "press_key",
        "description": "Press a key or key combination, such as ctrl+c, Return, Tab, Up, or KP_0.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "key": {"type": "string", "description": "Key or key combination."},
            },
            "required": ["app", "key"],
            "additionalProperties": False,
        },
    },
    {
        "name": "type_text",
        "description": "Type literal text into the active app.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "text": {"type": "string", "description": "Text to type."},
            },
            "required": ["app", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "scroll",
        "description": "Scroll an element from the latest get_app_state response.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                "pages": {"type": "number", "minimum": 0, "default": 1},
            },
            "required": ["app", "element_index", "direction"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_value",
        "description": "Set the value of an accessibility element from the latest get_app_state response.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "value": {"type": "string", "description": "Value to assign."},
            },
            "required": ["app", "element_index", "value"],
            "additionalProperties": False,
        },
    },
    {
        "name": "perform_secondary_action",
        "description": "Invoke an accessibility action exposed by an element, such as AXPress, AXShowMenu, AXIncrement, or AXDecrement.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "action": {"type": "string", "description": "Accessibility action name."},
            },
            "required": ["app", "element_index", "action"],
            "additionalProperties": False,
        },
    },
]