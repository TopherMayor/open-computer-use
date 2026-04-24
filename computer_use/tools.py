from __future__ import annotations

from typing import Any

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
                "annotate_screenshot": {"type": "boolean", "default": False, "description": "Draw numbered bounding boxes on the screenshot using accessibility tree elements."},
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
                "app": {"type": "string", "description": "App name or bundle identifier. Unused; app is activated by get_app_state."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "x": {"type": "number", "description": "Screenshot x coordinate."},
                "y": {"type": "number", "description": "Screenshot y coordinate."},
                "click_count": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1},
                "mouse_button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "drag",
        "description": "Drag from one screenshot coordinate to another.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier. Unused; app is activated by get_app_state."},
                "from_x": {"type": "number"},
                "from_y": {"type": "number"},
                "to_x": {"type": "number"},
                "to_y": {"type": "number"},
                "duration": {"type": "number", "minimum": 0, "default": 0.35},
            },
            "required": ["from_x", "from_y", "to_x", "to_y"],
            "additionalProperties": False,
        },
    },
    {
        "name": "press_key",
        "description": "Press a key or key combination, such as ctrl+c, Return, Tab, Up, or KP_0.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier. Unused; app is activated by get_app_state."},
                "key": {"type": "string", "description": "Key or key combination."},
            },
            "required": ["key"],
            "additionalProperties": False,
        },
    },
    {
        "name": "type_text",
        "description": "Type literal text into the active app.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier. Unused; app is activated by get_app_state."},
                "text": {"type": "string", "description": "Text to type."},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "scroll",
        "description": "Scroll an element from the latest get_app_state response.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier. Unused; app is activated by get_app_state."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                "pages": {"type": "number", "minimum": 0, "default": 1},
            },
            "required": ["element_index", "direction"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_value",
        "description": "Set the value of an accessibility element from the latest get_app_state response.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier. Unused; app is activated by get_app_state."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "value": {"type": "string", "description": "Value to assign."},
            },
            "required": ["element_index", "value"],
            "additionalProperties": False,
        },
    },
    {
        "name": "perform_secondary_action",
        "description": "Invoke an accessibility action exposed by an element, such as AXPress, AXShowMenu, AXIncrement, or AXDecrement.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or bundle identifier. Unused; app is activated by get_app_state."},
                "element_index": {"type": "string", "description": "Index from the latest get_app_state response."},
                "action": {"type": "string", "description": "Accessibility action name."},
            },
            "required": ["element_index", "action"],
            "additionalProperties": False,
        },
    },
    {
        "name": "analyze_screenshot",
        "description": "Capture and analyze the current screen. Returns OCR text, detected elements, and an annotated screenshot with numbered bounding boxes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ocr": {"type": "boolean", "default": True, "description": "Include OCR text extraction."},
                "annotate": {"type": "boolean", "default": True, "description": "Return annotated screenshot with element indices."},
                "app": {"type": "string", "description": "Optional app name to focus analysis on."},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "screenshot_diff",
        "description": "Compare the current screenshot with a previously captured one. Returns changed regions and a diff image.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "before": {"type": "string", "description": "Base64-encoded PNG of the before screenshot."},
                "after": {"type": "string", "description": "Base64-encoded PNG of the after screenshot. If omitted, captures current screen."},
                "threshold": {"type": "number", "minimum": 0, "maximum": 100, "default": 5, "description": "Minimum change percentage to report."},
            },
            "required": ["before"],
            "additionalProperties": False,
        },
    },
    {
        "name": "visual_click",
        "description": "Click an element described in natural language. Takes a screenshot, uses OCR + accessibility tree to locate the best match, then clicks the center of the matched element. Falls back to OCR text matching if no accessibility element matches. Returns the matched element info and coordinates clicked.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Natural language description of what to click, e.g. 'the Submit button', 'File menu', 'the username text field', 'OK'.",
                },
                "app": {
                    "type": "string",
                    "description": "Optional app name to scope the search to.",
                },
                "click_count": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1},
                "mouse_button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "match_strategy": {
                    "type": "string",
                    "enum": ["auto", "accessibility", "ocr", "combined"],
                    "default": "combined",
                    "description": "Matching strategy: 'accessibility' searches the a11y tree, 'ocr' searches OCR text, 'combined' tries both and picks the best match.",
                },
            },
            "required": ["description"],
            "additionalProperties": False,
        },
    },
    {
        "name": "visual_locate",
        "description": "Find screen elements matching a natural language description. Returns coordinates and metadata for all matches without clicking. Useful for verifying a target before acting, or finding multiple similar elements.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Natural language description of what to find.",
                },
                "app": {"type": "string", "description": "Optional app name."},
                "match_strategy": {
                    "type": "string",
                    "enum": ["auto", "accessibility", "ocr", "combined"],
                    "default": "combined",
                },
                "max_results": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["description"],
            "additionalProperties": False,
        },
    },
]
